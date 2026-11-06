"""Validate and apply the shared bank catalog exchange format."""

import json
from decimal import Decimal

from django.db import connection, transaction
from rest_framework import serializers

from .models import Bank, BankProgram, MortgageProgram


MAX_CATALOG_BYTES = 1024 * 1024


class CatalogImportError(ValueError):
    """An invalid catalog file or a reference that cannot be resolved."""


def _unique_json_object(pairs):
    """Reject repeated JSON properties rather than silently dropping values."""
    result = {}
    for name, value in pairs:
        if name in result:
            raise CatalogImportError(f'Повторяющееся поле JSON: {name[:80]}.')
        result[name] = value
    return result


def _invalid_json_constant(value):
    """Reject numeric tokens outside the JSON specification."""
    raise CatalogImportError(f'Недопустимое число JSON: {value}.')


def read_catalog_file(upload):
    """Read one bounded UTF-8 upload into the source-independent payload."""
    if not upload or not upload.name.lower().endswith('.json'):
        raise CatalogImportError('Выберите файл с расширением .json.')
    if upload.size > MAX_CATALOG_BYTES:
        raise CatalogImportError('Размер файла должен быть не больше 1 МБ.')
    try:
        return json.loads(
            upload.read().decode('utf-8-sig'),
            object_pairs_hook=_unique_json_object,
            parse_float=Decimal,
            parse_constant=_invalid_json_constant,
        )
    except CatalogImportError:
        raise
    except (ValueError, RecursionError) as error:
        raise CatalogImportError('Загрузите корректный JSON в кодировке UTF-8.') from error


class CatalogNameField(serializers.CharField):
    """Normalize spacing while retaining the display spelling."""

    def __init__(self):
        """Limit names to the catalog model field length."""
        super().__init__(max_length=255)

    def to_internal_value(self, data):
        """Accept only text for canonical names and references."""
        if not isinstance(data, str):
            self.fail('invalid')
        return ' '.join(super().to_internal_value(data).split())


class CatalogBankSerializer(serializers.Serializer):
    """Validate a canonical bank record."""

    name = CatalogNameField()
    logo_url = serializers.URLField(max_length=1000, allow_blank=True)

    def validate_logo_url(self, value):
        """Allow browser-safe HTTP and HTTPS image URLs."""
        if value and not value.lower().startswith(('https://', 'http://')):
            raise serializers.ValidationError('Укажите ссылку HTTP или HTTPS.')
        return value


class CatalogProgramSerializer(serializers.Serializer):
    """Validate a canonical mortgage program record."""

    name = CatalogNameField()
    condition = serializers.CharField(max_length=10000)
    is_preferential = serializers.BooleanField()
    credit_limit = serializers.DecimalField(
        max_digits=15, decimal_places=2, min_value=0,
        allow_null=True, required=False,
    )


class CatalogOfferSerializer(serializers.Serializer):
    """Validate terms for one bank and program pair."""

    bank = CatalogNameField()
    program = CatalogNameField()
    interest_rate = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100,
    )
    minimum_initial_payment_percent = serializers.DecimalField(
        max_digits=5, decimal_places=2, min_value=0, max_value=100,
    )
    maximum_loan_term_years = serializers.IntegerField(
        min_value=1, max_value=32767, allow_null=True,
    )


class CatalogPayloadSerializer(serializers.Serializer):
    """Validate the versioned file or a payload obtained from a future API."""

    version = serializers.ChoiceField(choices=(1,))
    banks = CatalogBankSerializer(many=True, required=False, max_length=500)
    programs = CatalogProgramSerializer(many=True, required=False, max_length=500)
    offers = CatalogOfferSerializer(many=True, required=False, max_length=5000)
    metadata = serializers.DictField(required=False)


def _first_error(errors, path=''):
    """Return the first validation error with its field and row number."""
    if isinstance(errors, dict):
        for field, value in errors.items():
            if value:
                return _first_error(value, f'{path}.{field}' if path else field)
    if isinstance(errors, list):
        for index, value in enumerate(errors, start=1):
            if value:
                location = f'{path}[{index}]' if isinstance(value, (dict, list)) else path
                return _first_error(value, location)
    return f'{path}: {errors}' if path else str(errors)


def _name_key(value):
    """Match canonical names regardless of letter case and extra whitespace."""
    return ' '.join(value.split()).casefold()


def _check_duplicates(rows, fields, section):
    """Reject repeated normalized keys before making any writes."""
    seen = set()
    for row_number, row in enumerate(rows, start=1):
        key = tuple(_name_key(row[field]) for field in fields)
        if key in seen:
            raise CatalogImportError(f'{section}[{row_number}]: повторяющаяся запись.')
        seen.add(key)


def _named_records(model, names):
    """Resolve existing catalog names and reject ambiguous legacy matches."""
    names = {_name_key(name) for name in names}
    if not names:
        return {}
    records = {}
    for record in model.objects.order_by().iterator():
        key = _name_key(record.name)
        if key in names:
            if key in records:
                raise CatalogImportError(f'В справочнике несколько записей «{record.name}».')
            records[key] = record
    return records


def _save_rows(model, rows, existing, key_fields, update_fields, summary):
    """Bulk upsert changed rows while keeping manually managed fields."""
    changed = []
    for key, values in rows.items():
        record = existing.get(key)
        if record is None:
            record = model(**values)
            summary['created'] += 1
        elif any(getattr(record, field) != values[field] for field in update_fields):
            for field in update_fields:
                setattr(record, field, values[field])
            summary['updated'] += 1
        else:
            summary['unchanged'] += 1
            continue
        changed.append(record)
        existing[key] = record

    model.objects.bulk_create(
        changed,
        update_conflicts=True,
        unique_fields=key_fields,
        update_fields=(*update_fields, 'updated_at'),
    )


def import_catalog(payload, section):
    """Validate decoded data and load the selected catalog in one transaction."""
    serializer = CatalogPayloadSerializer(data=payload)
    if not serializer.is_valid():
        raise CatalogImportError(_first_error(serializer.errors))
    data = serializer.validated_data
    banks = data.get('banks', [])
    programs = data.get('programs', [])
    offers = data.get('offers', [])

    _check_duplicates(banks, ('name',), 'banks')
    _check_duplicates(programs, ('name',), 'programs')
    _check_duplicates(offers, ('bank', 'program'), 'offers')

    if section not in {'bank', 'mortgage_program'} or not data.get(
        'banks' if section == 'bank' else 'programs'
    ):
        raise CatalogImportError('В файле нет записей для выбранного раздела.')
    return _load_catalog(section, banks, programs, offers)


@transaction.atomic
def _load_catalog(section, banks, programs, offers):
    """Serialize catalog imports so normalized names have one owner."""
    with connection.cursor() as cursor:
        # All catalog uploads share this transaction-scoped PostgreSQL lock.
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [0x42414E4B])
    summary = {'created': 0, 'updated': 0, 'unchanged': 0}
    if section == 'bank':
        existing = _named_records(Bank, (row['name'] for row in banks))
        _save_rows(
            Bank, {_name_key(row['name']): row for row in banks}, existing,
            ('name',), ('logo_url',), summary,
        )
    else:
        _import_programs(programs, offers, summary)
    return summary


def _import_programs(programs, offers, summary):
    """Load canonical programs and bank terms without replacing other rows."""
    bank_records = _named_records(Bank, (offer['bank'] for offer in offers))
    program_rows = {_name_key(row['name']): row for row in programs}
    for offer in offers:
        if _name_key(offer['bank']) not in bank_records:
            raise CatalogImportError(
                f'Банк «{offer["bank"]}» отсутствует. Сначала импортируйте банки.'
            )
        if _name_key(offer['program']) not in program_rows:
            raise CatalogImportError(f'Программа «{offer["program"]}» отсутствует в programs.')

    program_records = _named_records(MortgageProgram, (row['name'] for row in programs))
    for key, row in program_rows.items():
        existing = program_records.get(key)
        row.setdefault('credit_limit', existing.credit_limit if existing else None)

    _save_rows(
        MortgageProgram, program_rows, program_records, ('name',),
        ('condition', 'is_preferential', 'credit_limit'), summary,
    )

    offer_rows = {}
    for offer in offers:
        bank_id = bank_records[_name_key(offer['bank'])].pk
        program_id = program_records[_name_key(offer['program'])].pk
        offer_rows[bank_id, program_id] = {
            'bank_id': bank_id,
            'mortgage_program_id': program_id,
            **{field: value for field, value in offer.items() if field not in {'bank', 'program'}},
        }
    existing_offers = {
        (row.bank_id, row.mortgage_program_id): row
        for row in BankProgram.objects.filter(
            bank_id__in={bank_id for bank_id, _ in offer_rows},
            mortgage_program_id__in={program_id for _, program_id in offer_rows},
        ).order_by()
    }
    _save_rows(
        BankProgram, offer_rows, existing_offers, ('bank', 'mortgage_program'),
        ('interest_rate', 'minimum_initial_payment_percent', 'maximum_loan_term_years'),
        summary,
    )
