from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction

from .models import Bank, BankProgram, MortgageProgram

logger = logging.getLogger(__name__)

BANKI_MORTGAGE_URL = 'https://www.banki.ru/products/hypothec/?place=all_programm'
BANKI_TIMEOUT_SECONDS = 30
BANKI_MAX_PAGES = 20
BANK_NAME_MAX_LENGTH = Bank._meta.get_field('name').max_length
MARKET_MORTGAGE_PROGRAM_NAME = 'Рыночная ипотека'
MARKET_MORTGAGE_CONDITION = (
    'Классическая ипотечная программа без государственных субсидий.'
)
RATE_LABEL = 'Ставка'
INITIAL_PAYMENT_LABEL = 'Первоначальный взнос'
DISCOUNT_LABEL = 'Пониженная ставка'
TERM_LABEL = 'Срок'
DETAILS_LABEL = 'Подробнее'

MARKET_PROGRAM_KEYWORDS = (
    'вторич',
    'готовое жиль',
    'ипотека',
    'квартира',
    'новострой',
    'рыноч',
)
PREFERENTIAL_PROGRAM_KEYWORDS = (
    'аркти',
    'дальневост',
    'господдерж',
    'ит-',
    'it-',
    'семей',
    'сельск',
)


class BankMortgageSyncError(Exception):
    """Raised when bank mortgage offer synchronization cannot continue."""


@dataclass(frozen=True)
class BankMortgageOffer:
    """Normalized bank mortgage offer parsed from a source page."""

    bank_name: str
    program_name: str
    interest_rate: Decimal
    minimum_initial_payment_percent: Decimal
    salary_client_discount: Decimal
    maximum_loan_term_years: int | None = None
    logo_url: str = ''


def _extract_image_source(attrs_dict):
    """Return the best image source URL from regular and lazy attributes."""
    for attribute_name in ('src', 'data-src', 'data-lazy-src'):
        source_url = (attrs_dict.get(attribute_name) or '').strip()
        if source_url:
            return source_url

    for attribute_name in ('srcset', 'data-srcset', 'data-lazy-srcset'):
        source_set = (attrs_dict.get(attribute_name) or '').strip()
        if not source_set:
            continue

        first_source = source_set.split(',', 1)[0].strip()
        if first_source:
            return first_source.split()[0]

    return ''


class _MortgageOfferHtmlParser(HTMLParser):
    """Collect visible text and images from a mortgage offers HTML page."""

    def __init__(self, base_url):
        """Initialize parser state."""
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.text_items = []
        self.images = []
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        """Collect image data and skip invisible script/style blocks."""
        attrs_dict = dict(attrs)
        if tag in {'script', 'style', 'noscript'}:
            self._skip_depth += 1
            return

        if tag != 'img':
            return

        alt_text = (attrs_dict.get('alt') or '').strip()
        source_url = _extract_image_source(attrs_dict)

        if alt_text:
            self.images.append(
                {
                    'alt': alt_text,
                    'url': urljoin(self.base_url, source_url)
                    if source_url
                    else '',
                }
            )

    def handle_endtag(self, tag):
        """Track invisible script/style block endings."""
        if tag in {'script', 'style', 'noscript'} and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data):
        """Collect normalized visible text items."""
        if self._skip_depth:
            return

        text = ' '.join(data.split())
        if text:
            self.text_items.append(text)


def _normalize_name(value):
    """Normalize a bank or program name for comparisons."""
    return re.sub(r'\s+', ' ', value).strip().lower()


def _is_valid_bank_name(value):
    """Return whether a parsed bank name can be safely stored."""
    normalized_value = re.sub(r'\s+', ' ', value or '').strip()
    if not normalized_value:
        return False
    if len(normalized_value) > BANK_NAME_MAX_LENGTH:
        return False
    if '%' in normalized_value or '₽' in normalized_value:
        return False
    return True


def _parse_decimal_values(value):
    """Parse all decimal values from a Russian percent string."""
    decimal_values = []
    for match in re.finditer(r'-?\d+(?:[,.]\d+)?', value or ''):
        try:
            decimal_values.append(
                Decimal(match.group(0).replace(',', '.')).copy_abs()
            )
        except InvalidOperation:
            continue

    return decimal_values


def _parse_decimal(value, use_maximum=False):
    """Parse a decimal value from a Russian percent string."""
    decimal_values = _parse_decimal_values(value)
    if not decimal_values:
        return None

    if use_maximum:
        return max(decimal_values)
    return decimal_values[0]


def _parse_maximum_years(value):
    """Parse the maximum loan term in years from text."""
    years = []
    for match in re.finditer(
        r'(\d{1,2})\s*(?:лет|года|год)',
        value or '',
        flags=re.IGNORECASE,
    ):
        year = int(match.group(1))
        if 1 <= year <= 50:
            years.append(year)

    if years:
        return max(years)
    return None


def _is_market_mortgage_program(program_name):
    """Return whether a source program looks like market mortgage."""
    normalized_name = _normalize_name(program_name)
    if any(
        keyword in normalized_name
        for keyword in PREFERENTIAL_PROGRAM_KEYWORDS
    ):
        return False
    return any(keyword in normalized_name for keyword in MARKET_PROGRAM_KEYWORDS)


def _find_next_decimal(
    text_items,
    start_index,
    stop_index,
    use_maximum=False,
):
    """Find the next decimal value inside a text slice."""
    for text in text_items[start_index:stop_index]:
        decimal_value = _parse_decimal(text, use_maximum=use_maximum)
        if decimal_value is not None:
            return decimal_value
    return None


def _extract_discount(text_items, start_index, stop_index):
    """Extract a salary/client discount from offer text."""
    segment = ' '.join(text_items[start_index:stop_index])

    salary_discount = re.search(
        r'зарплатн.{0,120}?\+(\d+(?:[,.]\d+)?)\s*п',
        segment,
        flags=re.IGNORECASE,
    )
    if salary_discount:
        return Decimal(salary_discount.group(1).replace(',', '.'))

    for index in range(start_index, stop_index):
        if text_items[index] != DISCOUNT_LABEL:
            continue

        decimal_value = _find_next_decimal(
            text_items,
            index + 1,
            min(index + 4, stop_index),
        )
        if decimal_value is not None:
            return decimal_value

    return Decimal('0')


def _extract_maximum_loan_term_years(text_items, start_index, stop_index):
    """Extract a maximum loan term from offer text."""
    for index in range(start_index, stop_index):
        if text_items[index] != TERM_LABEL:
            continue

        for text in text_items[index + 1:min(index + 5, stop_index)]:
            maximum_years = _parse_maximum_years(text)
            if maximum_years is not None:
                return maximum_years

    segment = ' '.join(text_items[start_index:stop_index])
    for pattern in (
        r'(?:срок(?: кредита| ипотеки)?|период кредитования)[^.;]{0,120}?'
        r'(\d{1,2})\s*(?:лет|года|год)',
        r'(\d{1,2})\s*(?:лет|года|год)[^.;]{0,80}?'
        r'(?:срок|кредит|ипотек)',
    ):
        years = [
            int(match.group(1))
            for match in re.finditer(pattern, segment, flags=re.IGNORECASE)
            if 1 <= int(match.group(1)) <= 50
        ]
        if years:
            return max(years)

    return None


def _find_label_index(text_items, label, start_index, stop_index):
    """Find a label in a text slice."""
    for index in range(start_index, stop_index):
        if text_items[index] == label:
            return index
    return None


def _looks_like_offer_start(text_items, index):
    """Return whether text at index looks like the start of an offer card."""
    if index + 1 >= len(text_items):
        return False

    bank_name = text_items[index]
    program_name = text_items[index + 1]
    if not _is_valid_bank_name(bank_name) or not program_name:
        return False
    if bank_name in {
        RATE_LABEL,
        INITIAL_PAYMENT_LABEL,
        DISCOUNT_LABEL,
        TERM_LABEL,
        DETAILS_LABEL,
    }:
        return False
    if not _is_market_mortgage_program(program_name):
        return False

    stop_index = min(index + 40, len(text_items))
    has_rate = _find_label_index(
        text_items,
        RATE_LABEL,
        index + 2,
        stop_index,
    )
    has_initial_payment = _find_label_index(
        text_items,
        INITIAL_PAYMENT_LABEL,
        index + 2,
        stop_index,
    )
    if has_rate is None or has_initial_payment is None:
        return False

    return True


def _find_offer_card_indexes(text_items, images):
    """Return ordered source positions for bank offer cards."""
    indexes = set()

    for image in images:
        normalized_bank_name = _normalize_name(image['alt'])
        for index, text_item in enumerate(text_items):
            if _normalize_name(text_item) != normalized_bank_name:
                continue
            if _looks_like_offer_start(text_items, index):
                indexes.add(index)

    for index in range(len(text_items) - 1):
        if _looks_like_offer_start(text_items, index):
            indexes.add(index)

    return sorted(indexes)


def parse_banki_mortgage_offers(raw_html, source_url=BANKI_MORTGAGE_URL):
    """Parse market mortgage bank offers from Banki.ru HTML."""
    parser = _MortgageOfferHtmlParser(source_url)
    parser.feed(raw_html)

    text_items = parser.text_items
    bank_indexes = _find_offer_card_indexes(text_items, parser.images)
    logo_by_bank = {
        _normalize_name(image['alt']): image['url']
        for image in parser.images
        if image['url']
    }
    offers = []

    for item_number, bank_index in enumerate(bank_indexes):
        next_bank_index = (
            bank_indexes[item_number + 1]
            if item_number + 1 < len(bank_indexes)
            else len(text_items)
        )
        if bank_index + 1 >= next_bank_index:
            continue

        bank_name = text_items[bank_index]
        program_name = text_items[bank_index + 1]
        if not _is_valid_bank_name(bank_name):
            logger.warning(
                'Skipped mortgage offer with invalid bank name: %r',
                bank_name,
            )
            continue
        if not _is_market_mortgage_program(program_name):
            continue

        rate_label_index = _find_label_index(
            text_items,
            RATE_LABEL,
            bank_index + 1,
            next_bank_index,
        )
        initial_payment_index = _find_label_index(
            text_items,
            INITIAL_PAYMENT_LABEL,
            bank_index + 1,
            next_bank_index,
        )
        if rate_label_index is None or initial_payment_index is None:
            continue

        interest_rate = _find_next_decimal(
            text_items,
            rate_label_index + 1,
            min(rate_label_index + 4, next_bank_index),
            use_maximum=True,
        )
        minimum_initial_payment_percent = _find_next_decimal(
            text_items,
            initial_payment_index + 1,
            min(initial_payment_index + 4, next_bank_index),
        )
        if interest_rate is None or minimum_initial_payment_percent is None:
            continue

        offers.append(
            BankMortgageOffer(
                bank_name=bank_name,
                program_name=program_name,
                interest_rate=interest_rate,
                minimum_initial_payment_percent=(
                    minimum_initial_payment_percent
                ),
                salary_client_discount=_extract_discount(
                    text_items,
                    bank_index + 1,
                    next_bank_index,
                ),
                maximum_loan_term_years=_extract_maximum_loan_term_years(
                    text_items,
                    bank_index + 1,
                    next_bank_index,
                ),
                logo_url=logo_by_bank.get(_normalize_name(bank_name), ''),
            )
        )

    if not offers:
        raise BankMortgageSyncError(
            'Не удалось распарсить ипотечные предложения банков.'
        )

    return offers


def _download_banki_mortgage_payload(source_url):
    """Download a mortgage offers page from the configured source."""
    request = Request(
        source_url,
        headers={
            'User-Agent': (
                'Mozilla/5.0 (compatible; real-estate-investing/1.0)'
            ),
        },
    )
    with urlopen(request, timeout=BANKI_TIMEOUT_SECONDS) as response:
        return response.read().decode('utf-8', errors='ignore')


def _get_page_number(source_url):
    """Return a Banki.ru page number from URL query params."""
    parsed_url = urlparse(source_url)
    page_values = parse_qs(parsed_url.query).get('page')
    if not page_values:
        return 1
    if page_values[0].isdecimal():
        return int(page_values[0])
    return 1


def _extract_next_page_url(raw_html, current_url):
    """Find the next Banki.ru mortgage page URL in pagination links."""
    current_page = _get_page_number(current_url)
    candidates = []

    for match in re.finditer(r'href=[\'"]([^\'"]+)[\'"]', raw_html):
        absolute_url = urljoin(current_url, html.unescape(match.group(1)))
        parsed_url = urlparse(absolute_url)
        if 'banki.ru' not in parsed_url.netloc:
            continue
        if '/products/hypothec/' not in parsed_url.path:
            continue

        page_number = _get_page_number(absolute_url)
        if page_number > current_page:
            candidates.append((page_number, absolute_url))

    if not candidates:
        return None

    return min(candidates, key=lambda item: item[0])[1]


def _download_banki_mortgage_payloads(source_url):
    """Download all available paginated Banki.ru mortgage offer pages."""
    maximum_pages = getattr(
        settings,
        'BANK_MORTGAGE_OFFERS_MAX_PAGES',
        BANKI_MAX_PAGES,
    )
    payloads = []
    visited_urls = set()
    current_url = source_url

    for _ in range(maximum_pages):
        if current_url in visited_urls:
            break

        visited_urls.add(current_url)
        raw_html = _download_banki_mortgage_payload(current_url)
        payloads.append((current_url, raw_html))

        next_url = _extract_next_page_url(raw_html, current_url)
        if next_url is None:
            break
        current_url = next_url

    return payloads


def _select_best_offers(offers):
    """Select the best market mortgage offer per bank."""
    best_offers = {}
    for offer in offers:
        stored_offer = best_offers.get(offer.bank_name)
        if (
            stored_offer is None
            or offer.interest_rate < stored_offer.interest_rate
        ):
            best_offers[offer.bank_name] = offer
    return list(best_offers.values())


@transaction.atomic
def sync_bank_mortgage_offers(source_url=None):
    """Synchronize banks and market mortgage conditions from a source page."""
    resolved_source_url = (
        source_url
        or getattr(settings, 'BANK_MORTGAGE_OFFERS_URL', BANKI_MORTGAGE_URL)
    )
    all_offers = []
    for page_url, raw_html in _download_banki_mortgage_payloads(
        resolved_source_url
    ):
        try:
            all_offers.extend(
                parse_banki_mortgage_offers(
                    raw_html,
                    source_url=page_url,
                )
            )
        except BankMortgageSyncError:
            if not all_offers:
                raise
            logger.warning('Could not parse mortgage offers from %s', page_url)

    if not all_offers:
        raise BankMortgageSyncError(
            'Не удалось распарсить ипотечные предложения банков.'
        )

    offers = _select_best_offers(all_offers)

    mortgage_program, _ = MortgageProgram.objects.get_or_create(
        name=MARKET_MORTGAGE_PROGRAM_NAME,
        defaults={
            'condition': MARKET_MORTGAGE_CONDITION,
            'is_preferential': False,
        },
    )

    created = 0
    updated = 0

    for offer in offers:
        bank, was_created = Bank.objects.get_or_create(
            name=offer.bank_name,
            defaults={
                'interest_rate': offer.interest_rate,
                'salary_client_discount': offer.salary_client_discount,
                'logo_url': offer.logo_url,
                'maximum_loan_term_years': offer.maximum_loan_term_years,
            },
        )
        if was_created:
            created += 1
        else:
            changed_fields = []
            field_updates = (
                ('interest_rate', offer.interest_rate),
                ('salary_client_discount', offer.salary_client_discount),
            )
            for field_name, value in field_updates:
                if getattr(bank, field_name) != value:
                    setattr(bank, field_name, value)
                    changed_fields.append(field_name)

            if offer.logo_url and bank.logo_url != offer.logo_url:
                bank.logo_url = offer.logo_url
                changed_fields.append('logo_url')
            if (
                offer.maximum_loan_term_years is not None
                and bank.maximum_loan_term_years
                != offer.maximum_loan_term_years
            ):
                bank.maximum_loan_term_years = offer.maximum_loan_term_years
                changed_fields.append('maximum_loan_term_years')

            if changed_fields:
                bank.save(update_fields=[*changed_fields, 'updated_at'])
                updated += 1

        bank_program_defaults = {
            'interest_rate': offer.interest_rate,
            'minimum_initial_payment_percent': (
                offer.minimum_initial_payment_percent
            ),
        }
        if offer.maximum_loan_term_years is not None:
            bank_program_defaults['maximum_loan_term_years'] = (
                offer.maximum_loan_term_years
            )

        bank_program, _ = BankProgram.objects.update_or_create(
            bank=bank,
            mortgage_program=mortgage_program,
            defaults=bank_program_defaults,
        )
        logger.debug('Synced bank program %s', bank_program.pk)

    return {
        'created': created,
        'updated': updated,
        'processed': len(offers),
    }
