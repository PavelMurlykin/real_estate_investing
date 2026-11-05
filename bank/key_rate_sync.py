from __future__ import annotations

import logging
import re
from bisect import bisect_right
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from html import unescape
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone
from django.utils.html import strip_tags

from .models import KeyRate

logger = logging.getLogger(__name__)

CBR_ORIGIN = 'https://www.cbr.ru'
CBR_KEY_RATE_URL = f'{CBR_ORIGIN}/hd_base/keyrate/'
CBR_DECISIONS_URL = f'{CBR_ORIGIN}/dkp/mp_dec/'
CBR_DATE_FORMAT = '%d.%m.%Y'
CBR_START_DATE = date(2013, 9, 17)
CBR_TIMEOUT_SECONDS = 30

ROW_PATTERN = re.compile(
    r'<tr>\s*<td>\s*(\d{2}\.\d{2}\.\d{4})\s*</td>\s*<td>\s*([\d\s,]+)\s*</td>\s*</tr>',
    flags=re.IGNORECASE,
)
RELEASE_PATTERN = re.compile(
    r'<div class="previews_item-title">\s*<a href="'
    r'(?P<path>/press/pr/\?file=(?P<date>\d{8}|\d{6})_[^"]+)">'
    r'(?P<title>.*?)</a>',
    re.IGNORECASE | re.DOTALL,
)
NEXT_PAGE_PATTERN = re.compile(
    r'data-cross-ajax-url=["\']'
    r'(?P<path>/Crosscut/NewsList/LoadMore/\d+\?intOffset=\d+&extOffset=\d+)'
    r'["\']',
    re.IGNORECASE,
)
UNCHANGED_RATE_PATTERN = re.compile(
    r'(?:сохранить|сохранил|оставить|оставил) ключевую ставку '
    r'(?:Банка России )?на уровне (\d{1,3}(?:[,.]\d{1,2})?)\s*%',
    re.IGNORECASE,
)


class KeyRateSyncError(Exception):
    """Report an unavailable or unrecognized Central Bank source."""


def _download_cbr_html(url: str) -> str:
    """Fetch a public page from the Central Bank with a bounded timeout."""
    request = Request(
        url,
        headers={
            'User-Agent': (
                'Mozilla/5.0 (compatible; real-estate-investing/1.0)'
            ),
        },
    )
    try:
        with urlopen(request, timeout=CBR_TIMEOUT_SECONDS) as response:
            return response.read().decode('utf-8')
    except (URLError, TimeoutError, HTTPException, UnicodeError) as error:
        logger.warning('Could not read CBR source %s: %s', url, error)
        raise KeyRateSyncError(
            'Источник Банка России временно недоступен.'
        ) from error


def _download_cbr_payload(from_date: date, to_date: date) -> str:
    """Fetch the effective daily rates for the requested date range."""
    parameters = urlencode({
        'UniDbQuery.Posted': 'True',
        'UniDbQuery.From': from_date.strftime(CBR_DATE_FORMAT),
        'UniDbQuery.To': to_date.strftime(CBR_DATE_FORMAT),
    })
    return _download_cbr_html(f'{CBR_KEY_RATE_URL}?{parameters}')


def _parse_daily_rates(raw_html: str) -> dict[date, Decimal]:
    """Normalize published business-day rates by date."""
    rates = {}
    for date_raw, rate_raw in ROW_PATTERN.findall(raw_html):
        try:
            effective_date = datetime.strptime(
                date_raw, CBR_DATE_FORMAT,
            ).date()
            rate = Decimal(''.join(rate_raw.split()).replace(',', '.'))
        except (ValueError, InvalidOperation):
            logger.warning(
                'CBR key rate row skipped: date=%s rate=%s', date_raw, rate_raw,
            )
            continue
        rates[effective_date] = rate

    if not rates:
        raise KeyRateSyncError(
            'Не удалось прочитать таблицу ключевой ставки Банка России.'
        )
    return rates


def _plain_text(raw_html: str) -> str:
    """Normalize whitespace and HTML entities in release text."""
    return ' '.join(unescape(strip_tags(raw_html)).split())


def _download_unchanged_decisions(
    from_date: date, to_date: date,
) -> dict[date, Decimal]:
    """Read confirmed decisions to retain the rate from the press archive."""
    raw_html = _download_cbr_html(CBR_DECISIONS_URL)
    _, archive_marker, archive_html = raw_html.partition('id="tab_content_t1"')
    if archive_marker:
        archive_html = re.split(
            r'<div\s+role="tabpanel"', archive_html, maxsplit=1,
        )[0]

    decisions = {}
    visited_pages = set()
    while True:
        releases = list(RELEASE_PATTERN.finditer(archive_html))
        if not releases:
            raise KeyRateSyncError(
                'Не удалось прочитать архив решений Банка России.'
            )
        oldest_release = to_date
        for release in releases:
            published = release['date']
            date_format = '%d%m%Y' if len(published) == 8 else '%y%m%d'
            try:
                decision_date = datetime.strptime(published, date_format).date()
            except ValueError:
                continue
            oldest_release = min(oldest_release, decision_date)
            if not from_date <= decision_date <= to_date:
                continue

            title = _plain_text(release['title'])
            unchanged_rate = UNCHANGED_RATE_PATTERN.search(title)
            if unchanged_rate is None and title.startswith(
                'О ключевой ставке Банка России'
            ):
                # Older releases put the actual decision in the article.
                article = _download_cbr_html(
                    f'{CBR_ORIGIN}{unescape(release['path'])}'
                )
                unchanged_rate = UNCHANGED_RATE_PATTERN.search(_plain_text(article))
            if unchanged_rate:
                decisions[decision_date] = Decimal(
                    unchanged_rate[1].replace(',', '.')
                )

        next_page = NEXT_PAGE_PATTERN.search(unescape(archive_html))
        if oldest_release < from_date or next_page is None:
            return decisions
        next_path = next_page['path']
        if next_path in visited_pages:
            raise KeyRateSyncError('Архив решений Банка России повторяет страницу.')
        visited_pages.add(next_path)
        archive_html = _download_cbr_html(f'{CBR_ORIGIN}{next_path}')


@transaction.atomic
def _save_rates(rates: dict[date, Decimal]) -> dict[str, int]:
    """Apply the source values without duplicating dates on concurrent imports."""
    existing_rates = dict(KeyRate.objects.filter(
        meeting_date__in=rates,
    ).values_list('meeting_date', 'key_rate'))
    created = 0
    updated = 0

    for rate_date, key_rate in sorted(rates.items()):
        if rate_date not in existing_rates:
            stored_rate, was_created = KeyRate.objects.get_or_create(
                meeting_date=rate_date, defaults={'key_rate': key_rate},
            )
            if was_created:
                created += 1
                continue
            existing_rates[rate_date] = stored_rate.key_rate
        if existing_rates[rate_date] != key_rate:
            updated += KeyRate.objects.filter(meeting_date=rate_date).exclude(
                key_rate=key_rate,
            ).update(key_rate=key_rate, updated_at=timezone.now())

    return {'created': created, 'updated': updated, 'processed': len(rates)}


def sync_key_rates(
    from_date: date | None = None, to_date: date | None = None
) -> dict[str, int]:
    """Import effective rate changes and published decisions to retain a rate."""
    sync_from = from_date or CBR_START_DATE
    sync_to = to_date or timezone.localdate()
    if sync_from > sync_to:
        raise KeyRateSyncError(
            'Дата начала периода больше даты окончания периода.'
        )

    # A preceding observation distinguishes a real change from a range boundary.
    lookback_start = max(sync_from, CBR_START_DATE) - timedelta(days=14)
    daily_rates = _parse_daily_rates(_download_cbr_payload(
        from_date=max(CBR_START_DATE, lookback_start),
        to_date=sync_to,
    ))
    observation_dates = sorted(daily_rates)
    rates = {}
    previous_rate = None
    for effective_date in observation_dates:
        key_rate = daily_rates[effective_date]
        if sync_from <= effective_date <= sync_to and key_rate != previous_rate:
            rates[effective_date] = key_rate
        previous_rate = key_rate

    for decision_date, key_rate in _download_unchanged_decisions(
        sync_from, sync_to,
    ).items():
        previous_observation = bisect_right(observation_dates, decision_date) - 1
        if (
            previous_observation >= 0
            and daily_rates[observation_dates[previous_observation]] == key_rate
        ):
            rates.setdefault(decision_date, key_rate)
        else:
            logger.warning(
                'CBR decision on %s disagrees with the effective rate series.',
                decision_date,
            )
    return _save_rates(rates)
