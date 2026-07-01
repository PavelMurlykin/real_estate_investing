"""Import developers and company groups from the DOM.RF registry."""

import re
from dataclasses import dataclass, field

from django.db import transaction

from location.models import Region
from property.models import CompanyGroup, Developer, DeveloperRegion

from .developer_registry_client import (
    DEFAULT_DEVELOPER_REGISTRY_REGIONS,
    DeveloperRegistryClientError,
    DomRfDeveloperRegistryClient,
)


TEXT_WHITESPACE_PATTERN = re.compile(r'\s+')
DIGIT_PATTERN = re.compile(r'\D+')

DEVELOPER_NAME_ALIASES = (
    'name',
    'developerName',
    'developer.name',
    'developer.shortName',
    'developer.fullName',
    'devName',
    'devShortCleanNm',
    'devFullCleanNm',
    'devId.devShortCleanNm',
    'devId.devFullCleanNm',
    'shortName',
    'fullName',
    'orgName',
    'organizationName',
)
LEGAL_ADDRESS_ALIASES = (
    'legalAddress',
    'developer.legalAddress',
    'devLegalAddr',
    'devId.devLegalAddr',
    'addressLegal',
    'jurAddress',
    'juridicalAddress',
)
ACTUAL_ADDRESS_ALIASES = (
    'actualAddress',
    'developer.actualAddress',
    'devFactAddr',
    'devId.devFactAddr',
    'addressActual',
    'factAddress',
    'factualAddress',
)
TAXPAYER_IDENTIFICATION_NUMBER_ALIASES = (
    'inn',
    'developer.inn',
    'devInn',
    'devId.devInn',
    'developerInn',
)
TAX_REGISTRATION_REASON_CODE_ALIASES = (
    'kpp',
    'developer.kpp',
    'devKpp',
    'devId.devKpp',
    'developerKpp',
)
PRIMARY_STATE_REGISTRATION_NUMBER_ALIASES = (
    'ogrn',
    'developer.ogrn',
    'devOgrn',
    'devId.devOgrn',
    'developerOgrn',
)
COMPANY_GROUP_NAME_ALIASES = (
    'companyGroupName',
    'companyGroup.name',
    'developer.companyGroupName',
    'developer.companyGroup.name',
    'developerGroupName',
    'developerGroup.name',
    'devGroupName',
    'devId.devGroupName',
    'groupName',
    'group.name',
    'holdingName',
)
REGION_ALIASES = (
    'region',
    'regionCode',
    'regionName',
    'region.code',
    'region.name',
    'developer.region',
    'developer.regionCode',
    'developer.regionName',
)
IGNORED_SOURCE_REGION_REFERENCES = {'file'}


class DeveloperRegistryImportError(Exception):
    """Raised when the developer registry import cannot be completed."""


@dataclass(frozen=True)
class DeveloperRegistryRecord:
    """Normalized developer registry row."""

    name: str
    company_group_name: str = ''
    legal_address: str = ''
    actual_address: str = ''
    taxpayer_identification_number: str = ''
    tax_registration_reason_code: str = ''
    primary_state_registration_number: str = ''
    source_regions: tuple[str, ...] = ()


@dataclass
class DeveloperRegistryImportSummary:
    """Counters returned after a developer registry import."""

    source_records: int = 0
    normalized_records: int = 0
    created_developers: int = 0
    updated_developers: int = 0
    unchanged_developers: int = 0
    created_company_groups: int = 0
    created_developer_region_links: int = 0
    skipped_records: int = 0
    errors: list[str] = field(default_factory=list)
    dry_run: bool = False

    def to_message(self):
        """Return a concise human-readable import summary."""
        prefix = 'Проверка импорта' if self.dry_run else 'Импорт'
        return (
            f'{prefix} ЕРЗ завершен: '
            f'создано застройщиков {self.created_developers}, '
            f'обновлено {self.updated_developers}, '
            f'без изменений {self.unchanged_developers}, '
            f'создано ГК {self.created_company_groups}, '
            f'добавлено связей с регионами '
            f'{self.created_developer_region_links}, '
            f'пропущено {self.skipped_records}.'
        )


def import_dom_rf_developers(
    region_codes=DEFAULT_DEVELOPER_REGISTRY_REGIONS,
    dry_run=False,
    limit=None,
    client=None,
):
    """Import DOM.RF developer registry data into local catalogs."""
    importer = DeveloperRegistryImporter(client=client)
    return importer.import_developers(
        region_codes=region_codes,
        dry_run=dry_run,
        limit=limit,
    )


class DeveloperRegistryImporter:
    """Normalize and load DOM.RF developer registry data."""

    def __init__(self, client=None):
        """Store importer dependencies."""
        self.client = client or DomRfDeveloperRegistryClient()

    def import_developers(self, region_codes, dry_run=False, limit=None):
        """Fetch, normalize, deduplicate, and load developer records."""
        summary = DeveloperRegistryImportSummary(dry_run=dry_run)

        try:
            source_items = list(
                self.client.fetch_developers(
                    region_codes=region_codes,
                    limit=limit,
                )
            )
        except DeveloperRegistryClientError as exception:
            raise DeveloperRegistryImportError(str(exception)) from exception

        summary.source_records = len(source_items)
        deduplicated_records = {}

        for source_item in source_items:
            record = normalize_developer_registry_item(
                source_item.payload,
                region_code=source_item.region_code,
            )
            if not record.name:
                summary.skipped_records += 1
                continue

            key = get_developer_registry_record_key(record)
            existing_record = deduplicated_records.get(key)
            if existing_record:
                deduplicated_records[key] = merge_developer_registry_records(
                    existing_record,
                    record,
                )
                continue

            deduplicated_records[key] = record

        summary.normalized_records = len(deduplicated_records)
        self.load_records(
            deduplicated_records.values(),
            summary=summary,
            dry_run=dry_run,
        )
        return summary

    def load_records(self, records, summary, dry_run=False):
        """Load normalized records into CompanyGroup and Developer models."""
        with transaction.atomic():
            for record in records:
                self.load_record(record, summary)

            if dry_run:
                transaction.set_rollback(True)

    def load_record(self, record, summary):
        """Create or update one developer and its company group."""
        company_group = self.get_or_create_company_group(record, summary)
        developer = find_existing_developer(record)

        if developer is None:
            developer = Developer.objects.create(
                name=record.name,
                company_group=company_group,
                legal_address=record.legal_address or None,
                actual_address=record.actual_address or None,
                taxpayer_identification_number=(
                    record.taxpayer_identification_number or None
                ),
                tax_registration_reason_code=(
                    record.tax_registration_reason_code or None
                ),
                primary_state_registration_number=(
                    record.primary_state_registration_number or None
                ),
            )
            summary.created_developers += 1
            summary.created_developer_region_links += (
                sync_developer_regions(developer, record.source_regions)
            )
            return

        changed_fields = apply_developer_registry_record(
            developer,
            record,
            company_group,
        )
        created_region_links = sync_developer_regions(
            developer,
            record.source_regions,
        )
        summary.created_developer_region_links += created_region_links
        if changed_fields:
            developer.save(update_fields=[*changed_fields, 'updated_at'])
            summary.updated_developers += 1
            return
        if created_region_links:
            summary.updated_developers += 1
            return

        summary.unchanged_developers += 1

    def get_or_create_company_group(self, record, summary):
        """Return the company group from the record, creating it if needed."""
        if not record.company_group_name:
            return None

        company_group = CompanyGroup.objects.filter(
            name__iexact=record.company_group_name
        ).first()
        if company_group:
            return company_group

        company_group, created = CompanyGroup.objects.get_or_create(
            name=record.company_group_name
        )
        if created:
            summary.created_company_groups += 1
        return company_group


def normalize_developer_registry_item(payload, region_code=''):
    """Normalize one raw DOM.RF registry row into a typed record."""
    taxpayer_identification_number = normalize_digits(
        read_first_payload_value(
            payload,
            TAXPAYER_IDENTIFICATION_NUMBER_ALIASES,
        ),
        max_length=12,
    )
    tax_registration_reason_code = normalize_digits(
        read_first_payload_value(
            payload,
            TAX_REGISTRATION_REASON_CODE_ALIASES,
        ),
        max_length=9,
    )
    primary_state_registration_number = normalize_digits(
        read_first_payload_value(
            payload,
            PRIMARY_STATE_REGISTRATION_NUMBER_ALIASES,
        ),
        max_length=15,
    )
    region_references = normalize_region_references(
        read_first_payload_value(payload, REGION_ALIASES),
        region_code,
    )

    return DeveloperRegistryRecord(
        name=normalize_text(
            read_first_payload_value(payload, DEVELOPER_NAME_ALIASES)
        ),
        company_group_name=normalize_text(
            read_first_payload_value(payload, COMPANY_GROUP_NAME_ALIASES)
        ),
        legal_address=normalize_text(
            read_first_payload_value(payload, LEGAL_ADDRESS_ALIASES)
        ),
        actual_address=normalize_text(
            read_first_payload_value(payload, ACTUAL_ADDRESS_ALIASES)
        ),
        taxpayer_identification_number=taxpayer_identification_number,
        tax_registration_reason_code=tax_registration_reason_code,
        primary_state_registration_number=primary_state_registration_number,
        source_regions=region_references,
    )


def normalize_text(value):
    """Normalize textual source values."""
    if value in (None, ''):
        return ''
    text = str(value).replace('\xa0', ' ').strip()
    if text.casefold() in {'-', '—', 'null', 'none', 'nan', 'n/a'}:
        return ''
    return TEXT_WHITESPACE_PATTERN.sub(' ', text)


def normalize_digits(value, max_length=None):
    """Normalize registry number values to digits only."""
    if value in (None, ''):
        return ''
    digits = DIGIT_PATTERN.sub('', str(value))
    if max_length:
        return digits[:max_length]
    return digits


def normalize_region_references(*values):
    """Normalize source region references from row values and source filters."""
    references = []
    seen_references = set()

    for value in values:
        text = normalize_text(value)
        if not text:
            continue
        if text.casefold() in IGNORED_SOURCE_REGION_REFERENCES:
            continue
        if text in seen_references:
            continue
        seen_references.add(text)
        references.append(text)

    return tuple(references)


def read_first_payload_value(payload, aliases):
    """Return the first non-empty payload value from alias paths."""
    for alias in aliases:
        value = read_payload_value(payload, alias)
        if value not in (None, ''):
            return value
    return ''


def read_payload_value(payload, alias):
    """Read a nested value from a source row using case-insensitive keys."""
    value = payload
    for key in alias.split('.'):
        if not isinstance(value, dict):
            return ''
        value = read_dictionary_key(value, key)
    if isinstance(value, dict):
        return ''
    return value


def read_dictionary_key(dictionary, target_key):
    """Read one dictionary key with case-insensitive fallback."""
    if target_key in dictionary:
        return dictionary[target_key]

    target_key_lower = target_key.lower()
    for key, value in dictionary.items():
        if str(key).lower() == target_key_lower:
            return value
    return ''


def get_developer_registry_record_key(record):
    """Return a stable deduplication key for a normalized record."""
    if record.taxpayer_identification_number:
        return ('inn', record.taxpayer_identification_number)
    if record.primary_state_registration_number:
        return ('ogrn', record.primary_state_registration_number)
    return ('name', record.name.casefold())


def merge_developer_registry_records(first_record, second_record):
    """Merge duplicate normalized records from different region filters."""
    source_regions = tuple(
        sorted(set(first_record.source_regions + second_record.source_regions))
    )
    return DeveloperRegistryRecord(
        name=first_record.name or second_record.name,
        company_group_name=(
            first_record.company_group_name
            or second_record.company_group_name
        ),
        legal_address=first_record.legal_address or second_record.legal_address,
        actual_address=(
            first_record.actual_address or second_record.actual_address
        ),
        taxpayer_identification_number=(
            first_record.taxpayer_identification_number
            or second_record.taxpayer_identification_number
        ),
        tax_registration_reason_code=(
            first_record.tax_registration_reason_code
            or second_record.tax_registration_reason_code
        ),
        primary_state_registration_number=(
            first_record.primary_state_registration_number
            or second_record.primary_state_registration_number
        ),
        source_regions=source_regions,
    )


def find_existing_developer(record):
    """Find an existing developer by INN, OGRN, or exact name."""
    lookup_order = (
        (
            'taxpayer_identification_number',
            record.taxpayer_identification_number,
        ),
        (
            'primary_state_registration_number',
            record.primary_state_registration_number,
        ),
        ('name', record.name),
    )
    for field_name, value in lookup_order:
        if not value:
            continue
        developer = Developer.objects.filter(**{field_name: value}).first()
        if developer:
            return developer
    return None


def sync_developer_regions(developer, source_region_codes):
    """Create missing region links for the developer from source references."""
    source_region_references = set(
        normalize_region_references(*source_region_codes)
    )
    if not source_region_references:
        return 0

    region_codes = set()
    region_names = set()
    for region_reference in source_region_references:
        region_codes.update(get_region_code_lookup_values(region_reference))
        if not normalize_text(region_reference).isdigit():
            region_names.add(normalize_region_name(region_reference))

    region_ids = set()
    if region_codes:
        region_ids.update(
            Region.objects.filter(code__in=region_codes).values_list(
                'pk',
                flat=True,
            )
        )
    if region_names:
        region_ids.update(
            region.pk
            for region in Region.objects.all()
            if normalize_region_name(region.name) in region_names
        )

    if not region_ids:
        return 0

    existing_region_ids = set(
        DeveloperRegion.objects.filter(
            developer=developer,
            region_id__in=region_ids,
        ).values_list('region_id', flat=True)
    )
    new_region_ids = region_ids - existing_region_ids
    if not new_region_ids:
        return 0

    DeveloperRegion.objects.bulk_create(
        [
            DeveloperRegion(developer=developer, region_id=region_id)
            for region_id in sorted(new_region_ids)
        ],
        ignore_conflicts=True,
    )
    return len(new_region_ids)


def get_region_code_lookup_values(region_reference):
    """Return possible region code forms for a source region reference."""
    digits = normalize_digits(region_reference)
    if not digits:
        return set()

    codes = {digits}
    stripped_digits = digits.lstrip('0')
    if stripped_digits:
        codes.add(stripped_digits)
        codes.add(stripped_digits.zfill(2))
    return codes


def normalize_region_name(region_name):
    """Normalize a region name for case-insensitive matching."""
    return normalize_text(region_name).replace('ё', 'е').casefold()


def apply_developer_registry_record(developer, record, company_group):
    """Apply non-empty source values to an existing developer."""
    changed_fields = []
    field_updates = {
        'name': record.name,
        'legal_address': record.legal_address,
        'actual_address': record.actual_address,
        'taxpayer_identification_number': (
            record.taxpayer_identification_number
        ),
        'tax_registration_reason_code': record.tax_registration_reason_code,
        'primary_state_registration_number': (
            record.primary_state_registration_number
        ),
    }

    for field_name, value in field_updates.items():
        if not value:
            continue
        if (
            field_name == 'name'
            and Developer.objects.exclude(pk=developer.pk)
            .filter(name=value)
            .exists()
        ):
            continue
        if getattr(developer, field_name) == value:
            continue
        setattr(developer, field_name, value)
        changed_fields.append(field_name)

    if company_group and developer.company_group_id != company_group.pk:
        developer.company_group = company_group
        changed_fields.append('company_group')

    return changed_fields
