from __future__ import annotations

import csv
import html
import io
import logging
import re
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from html.parser import HTMLParser
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from django.conf import settings
from django.db import transaction

from .models import Bank, BankProgram, MortgageProgram, MortgageProgramAlias
from .program_matching import normalize_mortgage_program_match_name

logger = logging.getLogger(__name__)

CBR_BANKS_URL = 'https://www.cbr.ru/banking_sector/credit/FullCoList/'
BANKI_MORTGAGE_URL = 'https://www.banki.ru/products/hypothec/?place=all_programm'
DOMRF_REFERENCE_MORTGAGE_PROGRAMS_URL = (
    'https://xn--h1alcedd.xn--d1aqf.xn--p1ai/catalog/'
    'program-is-lgoty-po-ipoteke/scope-is-federal/?filter=Y&'
)
FEDERAL_REFERENCE_MORTGAGE_PROGRAM_NAMES = (
    'Рыночная ипотека',
    'Вторичное жилье',
    'Траншевая ипотека',
    'Семейная ипотека',
    'Комбо семейная ипотека',
    'IT-ипотека',
    'Комбо IT-ипотека',
    'Дальневосточная ипотека',
    'Арктическая ипотека',
    'Сельская ипотека',
    'Военная ипотека',
    'Льготный период',
)
GOOGLE_SHEET_ID = '1or19DcE4LruFcb8WpDOpRLoTyvTc3T73HYBaUcp4Z9E'
GOOGLE_SHEET_CSV_URL_TEMPLATE = (
    'https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?'
    'tqx=out:csv&gid={gid}'
)
GOOGLE_SHEET_MORTGAGE_PROGRAM_SOURCES = (
    {
        'program_name': 'Семейная ипотека',
        'gid': '175597907',
        'bank_column_index': 2,
        'rate_column_index': 6,
        'initial_payment_column_index': 7,
    },
    {
        'program_name': 'IT-ипотека',
        'gid': '1390280621',
        'bank_column_index': 1,
        'rate_column_index': 5,
        'initial_payment_column_index': 6,
    },
)
BANKI_TIMEOUT_SECONDS = 30
DOMRF_TIMEOUT_SECONDS = 30
BANKI_MAX_PAGES = 20
DOMRF_REFERENCE_SOURCE_NAME = 'спроси.дом.рф'
FEDERAL_REFERENCE_SOURCE_NAME = 'федеральный справочник программ'
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
    'льгот',
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
class ReferenceMortgageProgramRecord:
    """Canonical mortgage program parsed from a reference source."""

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
        if pattern == r'\bбанк\b':
            continue
        normalized_value = re.sub(pattern, ' ', normalized_value)

    normalized_value = re.sub(r'[^a-zа-я0-9]+', '', normalized_value)
    if normalized_value.startswith('банк') and len(normalized_value) > 4:
        normalized_value = normalized_value[4:]

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


def _normalize_program_match_name(value):
    """Normalize a mortgage program name for duplicate-safe matching."""
    return normalize_mortgage_program_match_name(value)


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


def _looks_like_reference_mortgage_program_name(value):
    """Return whether reference source text can be a program name."""
    if not _looks_like_program_name(value):
        return False

    normalized_name = _normalize_name(value).replace('ё', 'е')
    skipped_names = {
        'льготы по ипотеке',
        'федеральные программы',
        'все программы',
    }
    if normalized_name in skipped_names:
        return False

    return 'ипотек' in normalized_name and _is_preferential_program(
        normalized_name
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


def parse_reference_mortgage_programs(raw_html):
    """Parse canonical mortgage program names from a reference HTML page."""
    parser = _MortgageOfferHtmlParser(DOMRF_REFERENCE_MORTGAGE_PROGRAMS_URL)
    parser.feed(raw_html or '')

    records = []
    seen_keys = set()
    for text in parser.text_items:
        program_name = re.sub(r'\s+', ' ', text or '').strip()
        program_key = _normalize_program_match_name(program_name)
        if (
            not program_key
            or program_key in seen_keys
            or not _looks_like_reference_mortgage_program_name(program_name)
        ):
            continue
        seen_keys.add(program_key)
        records.append(ReferenceMortgageProgramRecord(name=program_name))

    if not records:
        raise BankMortgageSyncError(
            'Не удалось распарсить эталонный справочник ипотечных программ.'
        )

    return records


def get_federal_reference_mortgage_programs():
    """Return built-in federal mortgage program reference records."""
    return [
        ReferenceMortgageProgramRecord(name=program_name)
        for program_name in FEDERAL_REFERENCE_MORTGAGE_PROGRAM_NAMES
    ]


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


def parse_google_sheet_mortgage_offers(
    raw_csv,
    program_name,
    bank_column_index,
    rate_column_index,
    initial_payment_column_index,
):
    """Parse mortgage offers from a Google Sheets CSV export."""
    rows = csv.reader(io.StringIO(raw_csv))
    offers = []
    minimum_columns_count = max(
        bank_column_index,
        rate_column_index,
        initial_payment_column_index,
    ) + 1

    for row in rows:
        if len(row) < minimum_columns_count:
            continue

        bank_name = normalize_bank_name_for_storage(row[bank_column_index])
        interest_rate = _parse_decimal(
            row[rate_column_index],
            use_maximum=True,
        )
        minimum_initial_payment_percent = _parse_decimal(
            row[initial_payment_column_index],
        )
        if (
            not _is_valid_bank_name(bank_name)
            or interest_rate is None
            or minimum_initial_payment_percent is None
        ):
            continue

        offers.append(
            BankMortgageOffer(
                bank_name=bank_name,
                program_name=program_name,
                interest_rate=interest_rate,
                minimum_initial_payment_percent=(
                    minimum_initial_payment_percent
                ),
            )
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


def _download_google_sheet_mortgage_payload(source_url):
    """Download a Google Sheets CSV export for mortgage offers."""
    return _download_payload(source_url)


def _download_reference_mortgage_programs_payload(source_url):
    """Download the reference mortgage program catalog page."""
    request = Request(
        source_url,
        headers={
            'User-Agent': (
                'Mozilla/5.0 (compatible; real-estate-investing/1.0)'
            ),
        },
    )
    with urlopen(request, timeout=DOMRF_TIMEOUT_SECONDS) as response:
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


def _download_banki_mortgage_payloads(source_url, sync_warnings=None):
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
        try:
            raw_html = _download_banki_mortgage_payload(current_url)
        except OSError as error:
            if payloads:
                message = (
                    f'Не загружена страница Banki.ru {current_url}: {error}'
                )
            else:
                message = (
                    'Banki.ru не обработан: не удалось загрузить '
                    'ипотечные предложения.'
                )
            if sync_warnings is not None:
                sync_warnings.append(message)
            logger.warning(
                'Could not download mortgage offers from %s: %s',
                current_url,
                error,
            )
            break
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
            _normalize_program_match_name(offer.program_name),
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


def _build_mortgage_program_lookup():
    """Build normalized lookup keys for canonical mortgage programs."""
    lookup = {}
    for alias in MortgageProgramAlias.objects.select_related(
        'mortgage_program'
    ).filter(is_active=True):
        if alias.normalized_name and alias.normalized_name not in lookup:
            lookup[alias.normalized_name] = alias.mortgage_program

    for mortgage_program in MortgageProgram.objects.order_by('pk'):
        key = _normalize_program_match_name(mortgage_program.name)
        if key and key not in lookup:
            lookup[key] = mortgage_program

    return lookup


def _ensure_mortgage_program_alias(
    mortgage_program,
    source_name,
    source='',
):
    """Ensure a source program name points to a canonical program."""
    normalized_name = _normalize_program_match_name(source_name)
    if not normalized_name:
        return False

    alias = MortgageProgramAlias.objects.filter(
        normalized_name=normalized_name
    ).first()
    if alias is not None:
        if alias.mortgage_program_id == mortgage_program.pk:
            changed_fields = []
            if source and not alias.source:
                alias.source = source
                changed_fields.append('source')
            if changed_fields:
                alias.save(update_fields=[*changed_fields, 'updated_at'])
            return False
        return False

    MortgageProgramAlias.objects.create(
        mortgage_program=mortgage_program,
        source_name=source_name,
        source=source,
    )
    return True


def _get_or_create_mapped_mortgage_program(
    program_name,
    program_lookup,
    source='',
):
    """Return a canonical mortgage program for a source program name."""
    program_key = _normalize_program_match_name(program_name)
    mortgage_program = program_lookup.get(program_key)
    if mortgage_program is None:
        mortgage_program, _ = MortgageProgram.objects.get_or_create(
            name=program_name,
            defaults={
                'condition': 'Программа импортирована из внешнего источника.',
                'is_preferential': _is_preferential_program(program_name),
            },
        )
        if program_key:
            program_lookup[program_key] = mortgage_program

    _ensure_mortgage_program_alias(
        mortgage_program,
        program_name,
        source=source,
    )
    return mortgage_program


def _remove_legacy_bank_program_link(bank, canonical_program, source_name):
    """Remove a bank-program link created under a duplicate program name."""
    legacy_program = MortgageProgram.objects.filter(name=source_name).exclude(
        pk=canonical_program.pk
    ).first()
    if legacy_program is None:
        return False

    deleted_count, _ = BankProgram.objects.filter(
        bank=bank,
        mortgage_program=legacy_program,
    ).delete()
    return bool(deleted_count)


def _sync_reference_mortgage_programs(
    records,
    program_lookup,
    source_name=DOMRF_REFERENCE_SOURCE_NAME,
):
    """Synchronize canonical mortgage programs from reference records."""
    created = 0
    aliases_created = 0
    updated = 0

    for record in records:
        program_key = _normalize_program_match_name(record.name)
        mortgage_program = program_lookup.get(program_key)
        if mortgage_program is None:
            mortgage_program = MortgageProgram.objects.create(
                name=record.name,
                condition=(
                    'Эталонная льготная программа импортирована '
                    'из внешнего источника.'
                ),
                is_preferential=True,
            )
            program_lookup[program_key] = mortgage_program
            created += 1
        elif not mortgage_program.is_preferential:
            mortgage_program.is_preferential = True
            mortgage_program.save(
                update_fields=['is_preferential', 'updated_at']
            )
            updated += 1

        if _ensure_mortgage_program_alias(
            mortgage_program,
            record.name,
            source=source_name,
        ):
            aliases_created += 1

    return {
        'created': created,
        'updated': updated,
        'aliases_created': aliases_created,
        'processed': len(records),
    }


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


def _sync_mortgage_offers_to_bank_programs(
    offers,
    bank_lookup,
    program_lookup,
    source='',
):
    """Synchronize normalized offers to BankProgram rows."""
    updated = 0
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

        mortgage_program = _get_or_create_mapped_mortgage_program(
            offer.program_name,
            program_lookup,
            source=source,
        )
        if _remove_legacy_bank_program_link(
            bank,
            mortgage_program,
            offer.program_name,
        ):
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
        'updated': updated,
        'processed': processed,
        'skipped': skipped,
    }


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


def _get_google_sheet_source_value(source, key, default=None):
    """Return a Google Sheets source setting from a dict or object."""
    if isinstance(source, dict):
        return source.get(key, default)
    return getattr(source, key, default)


def _build_google_sheet_csv_url(source):
    """Build a Google Sheets CSV export URL from source settings."""
    source_url = _get_google_sheet_source_value(source, 'source_url')
    if source_url:
        return source_url

    sheet_id = _get_google_sheet_source_value(
        source,
        'sheet_id',
        GOOGLE_SHEET_ID,
    )
    gid = _get_google_sheet_source_value(source, 'gid')
    return GOOGLE_SHEET_CSV_URL_TEMPLATE.format(sheet_id=sheet_id, gid=gid)


def _download_google_sheet_mortgage_offers(source):
    """Download and parse one Google Sheets mortgage program source."""
    source_url = _build_google_sheet_csv_url(source)
    return parse_google_sheet_mortgage_offers(
        _download_google_sheet_mortgage_payload(source_url),
        program_name=_get_google_sheet_source_value(source, 'program_name'),
        bank_column_index=_get_google_sheet_source_value(
            source,
            'bank_column_index',
        ),
        rate_column_index=_get_google_sheet_source_value(
            source,
            'rate_column_index',
        ),
        initial_payment_column_index=_get_google_sheet_source_value(
            source,
            'initial_payment_column_index',
        ),
    )


@transaction.atomic
def sync_bank_mortgage_offers(
    source_url=None,
    cbr_source_url=None,
    google_sheet_sources=None,
    update_bank_registry=True,
):
    """Synchronize CBR banks and Banki.ru mortgage program conditions."""
    resolved_source_url = (
        source_url
        or getattr(settings, 'BANK_MORTGAGE_OFFERS_URL', BANKI_MORTGAGE_URL)
    )
    sync_warnings = []
    if update_bank_registry:
        resolved_cbr_source_url = (
            cbr_source_url
            or getattr(settings, 'BANK_LIST_SOURCE_URL', CBR_BANKS_URL)
        )
        try:
            cbr_records = parse_cbr_bank_records(
                _download_cbr_bank_list_payload(resolved_cbr_source_url)
            )
            created, updated, banks = _sync_cbr_banks(cbr_records)
        except (BankMortgageSyncError, OSError, ValueError) as error:
            sync_warnings.append(
                f'Список банков ЦБ РФ не обновлен: {error}'
            )
            logger.warning('Could not parse CBR bank source: %s', error)
            cbr_records = []
            created = 0
            updated = 0
            banks = list(Bank.objects.filter(is_active=True))
    else:
        cbr_records = []
        created = 0
        updated = 0
        banks = list(Bank.objects.filter(is_active=True))

    bank_lookup = _build_bank_lookup(banks)
    program_lookup = _build_mortgage_program_lookup()
    reference_result = {
        'created': 0,
        'updated': 0,
        'aliases_created': 0,
        'processed': 0,
    }
    reference_records = []
    reference_source_name = DOMRF_REFERENCE_SOURCE_NAME
    resolved_reference_program_source_url = (
        getattr(
            settings,
            'BANK_MORTGAGE_REFERENCE_PROGRAM_SOURCE_URL',
            DOMRF_REFERENCE_MORTGAGE_PROGRAMS_URL,
        )
    )
    if resolved_reference_program_source_url:
        try:
            reference_records = parse_reference_mortgage_programs(
                _download_reference_mortgage_programs_payload(
                    resolved_reference_program_source_url
                )
            )
        except (BankMortgageSyncError, OSError, ValueError) as error:
            sync_warnings.append(
                f'Эталонный источник ипотечных программ не обработан: {error}'
            )
            logger.warning(
                'Could not parse reference mortgage program source: %s',
                error,
            )
    if not reference_records:
        reference_records = get_federal_reference_mortgage_programs()
        reference_source_name = FEDERAL_REFERENCE_SOURCE_NAME

    reference_result = _sync_reference_mortgage_programs(
        reference_records,
        program_lookup,
        source_name=reference_source_name,
    )
    resolved_google_sheet_sources = (
        google_sheet_sources
        if google_sheet_sources is not None
        else getattr(
            settings,
            'BANK_MORTGAGE_GOOGLE_SHEET_SOURCES',
            GOOGLE_SHEET_MORTGAGE_PROGRAM_SOURCES,
        )
    )

    all_offers = []
    banki_payloads = _download_banki_mortgage_payloads(
        resolved_source_url,
        sync_warnings=sync_warnings,
    )
    for page_url, raw_html in banki_payloads:
        try:
            all_offers.extend(
                parse_banki_mortgage_offers(
                    raw_html,
                    source_url=page_url,
                )
            )
        except BankMortgageSyncError as error:
            sync_warnings.append(
                f'Страница Banki.ru не обработана ({page_url}): {error}'
            )
            logger.warning(
                'Could not parse mortgage offers from %s: %s',
                page_url,
                error,
            )

    if banki_payloads and not all_offers:
        sync_warnings.append(
            'Banki.ru не дал пригодных ипотечных предложений.'
        )

    offers = _select_best_program_offers(all_offers)
    banki_result = _sync_mortgage_offers_to_bank_programs(
        offers,
        bank_lookup,
        program_lookup,
        source='banki.ru',
    )
    updated += banki_result['updated']

    google_sheet_offers = []
    for google_sheet_source in resolved_google_sheet_sources:
        try:
            google_sheet_offers.extend(
                _download_google_sheet_mortgage_offers(google_sheet_source)
            )
        except (BankMortgageSyncError, OSError, ValueError) as error:
            sync_warnings.append(
                f'Google Sheets источник не обработан: {error}'
            )
            logger.warning(
                'Could not parse Google Sheets mortgage source: %s',
                error,
            )

    google_sheet_offers = _select_best_program_offers(google_sheet_offers)
    google_sheet_result = _sync_mortgage_offers_to_bank_programs(
        google_sheet_offers,
        bank_lookup,
        program_lookup,
        source='google sheets',
    )
    updated += google_sheet_result['updated']

    return {
        'created': created,
        'updated': updated,
        'processed': (
            banki_result['processed'] + google_sheet_result['processed']
        ),
        'banks_processed': len(cbr_records),
        'offers_processed': len(offers) + len(google_sheet_offers),
        'reference_programs_processed': reference_result['processed'],
        'reference_programs_created': reference_result['created'],
        'reference_program_aliases_created': (
            reference_result['aliases_created']
        ),
        'google_sheet_offers_processed': len(google_sheet_offers),
        'skipped': banki_result['skipped'] + google_sheet_result['skipped'],
        'warnings': sync_warnings,
    }
