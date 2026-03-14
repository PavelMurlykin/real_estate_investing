from __future__ import annotations

import logging
import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.db import transaction
from django.utils import timezone

from .models import KeyRate

logger = logging.getLogger(__name__)

CBR_KEY_RATE_URL = 'https://www.cbr.ru/hd_base/keyrate/'
CBR_DATE_FORMAT = '%d.%m.%Y'
CBR_START_DATE = date(2013, 9, 17)
CBR_TIMEOUT_SECONDS = 30

ROW_PATTERN = re.compile(
    r'<tr>\s*<td>\s*(\d{2}\.\d{2}\.\d{4})\s*</td>\s*<td>\s*([\d\s,]+)\s*</td>\s*</tr>',
    flags=re.IGNORECASE,
)


class KeyRateSyncError(Exception):
    pass


def _build_request_url(from_date: date, to_date: date) -> str:
    params = {
        'UniDbQuery.Posted': 'True',
        'UniDbQuery.From': from_date.strftime(CBR_DATE_FORMAT),
        'UniDbQuery.To': to_date.strftime(CBR_DATE_FORMAT),
    }
    return f'{CBR_KEY_RATE_URL}?{urlencode(params)}'


def _download_cbr_payload(from_date: date, to_date: date) -> str:
    request_url = _build_request_url(from_date=from_date, to_date=to_date)
    request = Request(
        request_url,
        headers={
            'User-Agent': 'Mozilla/5.0 (compatible; real-estate-investing/1.0)',
        },
    )

    with urlopen(request, timeout=CBR_TIMEOUT_SECONDS) as response:
        return response.read().decode('utf-8', errors='ignore')


def _parse_daily_rates(raw_html: str) -> list[tuple[date, Decimal]]:
    rows: list[tuple[date, Decimal]] = []

    for date_raw, rate_raw in ROW_PATTERN.findall(raw_html):
        try:
            meeting_date = datetime.strptime(
                date_raw.strip(), CBR_DATE_FORMAT).date()
            normalized_rate = rate_raw.replace(
                '\xa0', '').replace(' ', '').replace(',', '.')
            key_rate = Decimal(normalized_rate)
        except (ValueError, InvalidOperation):
            logger.warning(
                'CBR key rate row skipped: date=%s rate=%s', date_raw, rate_raw)
            continue

        rows.append((meeting_date, key_rate))

    if not rows:
        raise KeyRateSyncError(
            'Не удалось распарсить данные ключевой ставки из ответа ЦБ РФ.')

    return rows


def _extract_meeting_rates(daily_rates: Iterable[tuple[date, Decimal]]) -> list[tuple[date, Decimal]]:
    rates = list(daily_rates)
    if not rates:
        return []

    meeting_rates: list[tuple[date, Decimal]] = []
    last_rate: Decimal | None = None

    for meeting_date, key_rate in reversed(rates):
        if last_rate is None or key_rate != last_rate:
            meeting_rates.append((meeting_date, key_rate))
            last_rate = key_rate

    meeting_rates.sort(key=lambda item: item[0], reverse=True)
    return meeting_rates


@transaction.atomic
def sync_key_rates(from_date: date | None = None, to_date: date | None = None) -> dict[str, int]:
    sync_from = from_date or CBR_START_DATE
    sync_to = to_date or timezone.localdate()

    if sync_from > sync_to:
        raise KeyRateSyncError(
            'Дата начала периода больше даты окончания периода.')

    raw_html = _download_cbr_payload(from_date=sync_from, to_date=sync_to)
    daily_rates = _parse_daily_rates(raw_html)
    meeting_rates = _extract_meeting_rates(daily_rates)

    existing_by_date = {
        item.meeting_date: item.key_rate
        for item in KeyRate.objects.filter(meeting_date__in=[meeting_date for meeting_date, _ in meeting_rates])
    }

    created = 0
    updated = 0

    for meeting_date, key_rate in meeting_rates:
        stored_rate = existing_by_date.get(meeting_date)
        if stored_rate is None:
            KeyRate.objects.create(
                meeting_date=meeting_date, key_rate=key_rate)
            created += 1
            continue

        if stored_rate != key_rate:
            KeyRate.objects.filter(
                meeting_date=meeting_date).update(key_rate=key_rate)
            updated += 1

    return {
        'created': created,
        'updated': updated,
        'processed': len(meeting_rates),
    }
