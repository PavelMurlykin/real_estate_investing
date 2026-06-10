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

CBR_BANKS_URL = 'https://www.cbr.ru/banking_sector/credit/FullCoList/'
BANKI_MORTGAGE_URL = 'https://www.banki.ru/products/hypothec/?place=all_programm'
BANKI_TIMEOUT_SECONDS = 30
BANKI_MAX_PAGES = 20
BANK_NAME_MAX_LENGTH = Bank._meta.get_field('name').max_length
RATE_LABEL = 'Ставка'
INITIAL_PAYMENT_LABEL = 'Первоначальный взнос'
TERM_LABEL = 'Срок'
DETAILS_LABEL = 'Подробнее'

PREFERENTIAL_PROGRAM_KEYWORDS = (
    'аркти',
    'дальневост',
    'господдерж',
    'ит-',
    'it-',
    'it ',
    'семей',
    'сельск',
)
SKIPPED_OFFER_TEXTS = {
    RATE_LABEL,
    INITIAL_PAYMENT_LABEL,
    TERM_LABEL,
    DETAILS_LABEL,
    'ПСК',
    'Платёж',
    'Пониженная ставка',
    'Отправить заявку',
}
LEGAL_NAME_PATTERNS = (
    r'публичное акционерное общество',
    r'акционерное общество',
    r'непубличное акционерное общество',
    r'общество с ограниченной ответственностью',
    r'общество с дополнительной ответственностью',
    r'коммерческий банк',
    r'кредитный банк',
    r'\bпао\b',
    r'\bоао\b',
    r'\bао\b',
    r'\bзао\b',
    r'\bнпао\b',
    r'\bооо\b',
    r'\bодо\b',
    r'\bтоо\b',
    r'\bкб\b',
    r'\bакб\b',
    r'\bбанк\b',
)
STORAGE_LEGAL_FORM_PATTERNS = (
    r'публичное акционерное общество',
    r'акционерное общество',
    r'непубличное акционерное общество',
    r'общество с ограниченной ответственностью',
    r'общество с дополнительной ответственностью',
    r'\bпао\b',
    r'\bоао\b',
    r'\bао\b',
    r'\bзао\b',
    r'\bнпао\b',
    r'\bооо\b',
    r'\bодо\b',
    r'\bтоо\b',
)
QUOTE_CHARACTERS_PATTERN = r'[«»"\'„“”‟‹›‚‘’′″＂]'
BRACKET_CHARACTERS_PATTERN = r'[\(\)\[\]\{\}<>〈〉《》「」『』【】〔〕]'


class BankMortgageSyncError(Exception):
    """Raised when bank mortgage offer synchronization cannot continue."""


@dataclass(frozen=True)
class CbrBankRecord:
    """Normalized active bank row from the Bank of Russia registry."""

    name: str


@dataclass(frozen=True)
class BankMortgageOffer:
    """Normalized bank mortgage offer parsed from a source page."""

    bank_name: str
    program_name: str
    interest_rate: Decimal
    minimum_initial_payment_percent: Decimal
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

        sources = [
            source.strip()
            for source in source_set.split(',')
            if source.strip()
        ]
        if sources:
            return sources[-1].split()[0]

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

        alt_text = (
            attrs_dict.get('alt')
            or attrs_dict.get('title')
            or attrs_dict.get('aria-label')
            or ''
        ).strip()
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


class _CbrBankListHtmlParser(HTMLParser):
    """Collect table cells from the Bank of Russia bank registry page."""

    def __init__(self):
        """Initialize parser state."""
        super().__init__(convert_charrefs=True)
        self.rows = []
        self._current_row = None
        self._current_cell = None
        self._skip_depth = 0

    def handle_starttag(self, tag, attrs):
        """Start collecting table rows and cells."""
        if tag in {'script', 'style', 'noscript'}:
            self._skip_depth += 1
            return
        if self._skip_depth:
            return
        if tag == 'tr':
            self._current_row = []
            return
        if tag in {'td', 'th'} and self._current_row is not None:
            self._current_cell = []

    def handle_endtag(self, tag):
        """Finish collecting table rows and cells."""
        if tag in {'script', 'style', 'noscript'} and self._skip_depth:
            self._skip_depth -= 1
            return
        if self._skip_depth:
            return
        if tag in {'td', 'th'} and self._current_cell is not None:
            self._current_row.append(
                ' '.join(' '.join(self._current_cell).split())
            )
            self._current_cell = None
            return
        if tag == 'tr' and self._current_row is not None:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = None

    def handle_data(self, data):
        """Collect table cell text."""
        if self._skip_depth or self._current_cell is None:
            return
        text = ' '.join(data.split())
        if text:
            self._current_cell.append(text)


def _normalize_name(value):
    """Normalize a bank or program name for exact text comparisons."""
    return re.sub(r'\s+', ' ', value).strip().lower()


def normalize_bank_name_for_storage(value):
    """Normalize an imported bank name before saving it."""
    normalized_value = re.sub(QUOTE_CHARACTERS_PATTERN, '', value or '')
    normalized_value = re.sub(BRACKET_CHARACTERS_PATTERN, ' ', normalized_value)

    for pattern in STORAGE_LEGAL_FORM_PATTERNS:
        normalized_value = re.sub(
            pattern,
            ' ',
            normalized_value,
            flags=re.IGNORECASE,
        )

    return re.sub(r'\s+', ' ', normalized_value).strip()


def _normalize_bank_match_name(value):
    """Normalize a bank name for CBR-to-Banki.ru matching."""
    normalized_value = _normalize_name(value).replace('ё', 'е')
    normalized_value = normalized_value.replace('&quot;', '').replace(
        '&nbsp;',
        ' ',
    )
    normalized_value = re.sub(r'[«»"“”„]', '', normalized_value)
    normalized_value = re.sub(r'\([^)]*\)', ' ', normalized_value)

    for pattern in LEGAL_NAME_PATTERNS:
        normalized_value = re.sub(pattern, ' ', normalized_value)

    normalized_value = re.sub(r'[^a-zа-я0-9]+', '', normalized_value)
    aliases = {
        'сбер': 'сбербанк',
        'сбербанкроссии': 'сбербанк',
        'тбанк': 'тбанк',
        'тинькофф': 'тбанк',
        'тинькоффбанк': 'тбанк',
        'домрф': 'домрф',
        'россельхоз': 'россельхозбанк',
    }
    return aliases.get(normalized_value, normalized_value)


def _is_valid_bank_name(value):
    """Return whether a parsed bank name can be safely stored."""
    normalized_value = re.sub(r'\s+', ' ', value or '').strip()
    if not normalized_value:
        return False
    normalized_lower_value = normalized_value.lower()
    if normalized_lower_value.startswith(('от ', 'до ')):
        return False
    if re.search(
        r'\b(?:лет|года|год|дней|дня|день)\b',
        normalized_lower_value,
    ):
        return False
    if len(normalized_value) > BANK_NAME_MAX_LENGTH:
        return False
    if '%' in normalized_value or '₽' in normalized_value:
        return False
    return True


def _looks_like_program_name(value):
    """Return whether a text fragment can be a mortgage program name."""
    normalized_value = re.sub(r'\s+', ' ', value or '').strip()
    if not normalized_value:
        return False
    if normalized_value in SKIPPED_OFFER_TEXTS:
        return False
    if len(normalized_value) > 140:
        return False
    if '%' in normalized_value or '₽' in normalized_value:
        return False
    if re.fullmatch(r'[\d\s.,–—-]+', normalized_value):
        return False
    if normalized_value.lower().startswith('ещё '):
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


def _is_preferential_program(program_name):
    """Return whether a source program looks like a preferential mortgage."""
    normalized_name = _normalize_name(program_name).replace('ё', 'е')
    return any(
        keyword in normalized_name
        for keyword in PREFERENTIAL_PROGRAM_KEYWORDS
    )


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
    if index + 2 >= len(text_items):
        return False

    bank_name = text_items[index]
    program_name = text_items[index + 1]
    if not _is_valid_bank_name(bank_name):
        return False
    if bank_name in SKIPPED_OFFER_TEXTS:
        return False
    if not _looks_like_program_name(program_name):
        return False

    stop_index = min(index + 45, len(text_items))
    details_index = _find_label_index(
        text_items,
        DETAILS_LABEL,
        index + 2,
        min(index + 8, stop_index),
    )
    if details_index is None:
        return False

    rate_index = _find_label_index(
        text_items,
        RATE_LABEL,
        index + 2,
        stop_index,
    )
    initial_payment_index = _find_label_index(
        text_items,
        INITIAL_PAYMENT_LABEL,
        index + 2,
        stop_index,
    )
    return rate_index is not None and initial_payment_index is not None


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


def parse_cbr_bank_records(raw_html):
    """Parse active bank records from the Bank of Russia registry page."""
    parser = _CbrBankListHtmlParser()
    parser.feed(raw_html)
    records = []

    for cells in parser.rows:
        if len(cells) < 8:
            continue
        if cells[0] == '№ п/п' or cells[4] == 'Наименование':
            continue

        credit_organization_type = cells[1]
        name = cells[4]
        license_status = cells[7]
        if credit_organization_type:
            continue
        if license_status not in {'', 'Действующая'}:
            continue
        if not _is_valid_bank_name(name):
            continue

        normalized_name = normalize_bank_name_for_storage(name)
        if not _is_valid_bank_name(normalized_name):
            continue
        records.append(CbrBankRecord(name=normalized_name))

    if not records:
        raise BankMortgageSyncError(
            'Не удалось распарсить список банков Банка России.'
        )

    unique_records = []
    seen_names = set()
    for record in records:
        if record.name in seen_names:
            continue
        unique_records.append(record)
        seen_names.add(record.name)

    return unique_records


def parse_banki_mortgage_offers(raw_html, source_url=BANKI_MORTGAGE_URL):
    """Parse mortgage bank offers from Banki.ru HTML."""
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


def _download_payload(source_url):
    """Download an HTML page from an external source."""
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


def _download_cbr_bank_list_payload(source_url):
    """Download the Bank of Russia bank registry page."""
    return _download_payload(source_url)


def _download_banki_mortgage_payload(source_url):
    """Download a mortgage offers page from the configured source."""
    return _download_payload(source_url)


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


def _select_best_program_offers(offers):
    """Select the best offer per bank and mortgage program."""
    best_offers = {}
    for offer in offers:
        key = (
            _normalize_bank_match_name(offer.bank_name),
            _normalize_name(offer.program_name),
        )
        stored_offer = best_offers.get(key)
        if (
            stored_offer is None
            or offer.interest_rate < stored_offer.interest_rate
        ):
            best_offers[key] = offer
    return list(best_offers.values())


def _build_bank_lookup(banks):
    """Build normalized lookup keys for active banks."""
    lookup = {}
    for bank in banks:
        key = _normalize_bank_match_name(bank.name)
        if key and key not in lookup:
            lookup[key] = bank
    return lookup


def _find_matching_bank(bank_name, bank_lookup):
    """Find a CBR bank by a Banki.ru bank name."""
    bank_key = _normalize_bank_match_name(bank_name)
    if bank_key in bank_lookup:
        return bank_lookup[bank_key]

    if len(bank_key) < 4:
        return None

    matching_banks = [
        bank
        for cbr_key, bank in bank_lookup.items()
        if (
            len(cbr_key) >= 4
            and (bank_key in cbr_key or cbr_key in bank_key)
        )
    ]
    if len(matching_banks) == 1:
        return matching_banks[0]
    return None


def _sync_cbr_banks(records):
    """Create and reactivate banks from the Bank of Russia registry."""
    created = 0
    updated = 0
    synced_banks = []
    existing_banks_by_normalized_name = {}

    for bank in Bank.objects.all():
        normalized_name = normalize_bank_name_for_storage(bank.name)
        if not normalized_name:
            continue
        if bank.name == normalized_name:
            existing_banks_by_normalized_name[normalized_name] = bank
        elif normalized_name not in existing_banks_by_normalized_name:
            existing_banks_by_normalized_name[normalized_name] = bank

    for record in records:
        bank = existing_banks_by_normalized_name.get(record.name)
        if bank is None:
            bank = Bank.objects.create(name=record.name)
            created += 1
            existing_banks_by_normalized_name[record.name] = bank
        else:
            changed_fields = []
            if bank.name != record.name:
                bank.name = record.name
                changed_fields.append('name')
            if not bank.is_active:
                bank.is_active = True
                changed_fields.append('is_active')
            if changed_fields:
                bank.save(update_fields=[*changed_fields, 'updated_at'])
                updated += 1

        if not bank.is_active:
            bank.is_active = True
            bank.save(update_fields=['is_active', 'updated_at'])
            updated += 1
        synced_banks.append(bank)

    return created, updated, synced_banks


@transaction.atomic
def sync_bank_mortgage_offers(source_url=None, cbr_source_url=None):
    """Synchronize CBR banks and Banki.ru mortgage program conditions."""
    resolved_source_url = (
        source_url
        or getattr(settings, 'BANK_MORTGAGE_OFFERS_URL', BANKI_MORTGAGE_URL)
    )
    resolved_cbr_source_url = (
        cbr_source_url
        or getattr(settings, 'BANK_LIST_SOURCE_URL', CBR_BANKS_URL)
    )

    cbr_records = parse_cbr_bank_records(
        _download_cbr_bank_list_payload(resolved_cbr_source_url)
    )
    created, updated, cbr_banks = _sync_cbr_banks(cbr_records)
    bank_lookup = _build_bank_lookup(cbr_banks)

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

    offers = _select_best_program_offers(all_offers)
    processed = 0
    skipped = 0

    for offer in offers:
        bank = _find_matching_bank(offer.bank_name, bank_lookup)
        if bank is None:
            skipped += 1
            logger.warning(
                'Skipped mortgage offer for bank absent from CBR list: %s',
                offer.bank_name,
            )
            continue

        if offer.logo_url and bank.logo_url != offer.logo_url:
            bank.logo_url = offer.logo_url
            bank.save(update_fields=['logo_url', 'updated_at'])
            updated += 1

        mortgage_program, _ = MortgageProgram.objects.get_or_create(
            name=offer.program_name,
            defaults={
                'condition': 'Программа импортирована с Banki.ru.',
                'is_preferential': _is_preferential_program(
                    offer.program_name
                ),
            },
        )

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

        bank_program, was_created = BankProgram.objects.update_or_create(
            bank=bank,
            mortgage_program=mortgage_program,
            defaults=bank_program_defaults,
        )
        if not was_created:
            updated += 1
        logger.debug('Synced bank program %s', bank_program.pk)
        processed += 1

    return {
        'created': created,
        'updated': updated,
        'processed': processed,
        'banks_processed': len(cbr_records),
        'offers_processed': len(offers),
        'skipped': skipped,
    }
