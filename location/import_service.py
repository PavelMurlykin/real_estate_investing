"""Atomically synchronize Russian location dictionaries from open data APIs."""

import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field

from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from .catalog_service import lock_location_catalog
from .compatibility import register_legacy_mappings
from .legacy_catalog import LEGACY_GEOGRAPHY_KEYS, invalidate_legacy_options, legacy_catalog, reserve_legacy_ids
from .models import LocationAlias, Metro
from .open_data import OpenDataError, OpenLocationSource, location_key

logger = logging.getLogger(__name__)
IMPORT_LOCK_IDENTIFIER = 77391042
SOURCE_NAME = 'Wikimedia / HFLabs'
SOURCE_URL = 'https://www.wikidata.org/wiki/Wikidata:Data_access'


class LocationImportError(Exception):
    """Report unavailable, malformed or conflicting location imports."""


@dataclass(frozen=True)
class LocationRecord:
    """Represent one normalized record before entering a transaction."""

    source_identifier: str
    name: str
    attributes: dict = field(default_factory=dict)

    def __post_init__(self):
        """Require values that fit the persistent location schema."""
        if not self.name or len(self.name) > 100 or len(self.source_identifier) > 200:
            raise LocationImportError('Некорректная запись открытого справочника.')


@contextmanager
def import_guard():
    """Serialize extraction and loading across all workers without a transaction."""
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT pg_try_advisory_lock(%s)', [IMPORT_LOCK_IDENTIFIER],
        )
        acquired = cursor.fetchone()[0]
    if not acquired:
        raise LocationImportError('Другой импорт ещё выполняется. Повторите позже.')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT pg_advisory_unlock(%s)', [IMPORT_LOCK_IDENTIFIER],
            )


def upsert_records(model, records, parent_field=None, parent_identifier=None, *, create_defaults=None):
    """Match stable source IDs, adopt natural keys, then bulk write changes."""
    queryset = model.objects.all()
    if parent_field:
        queryset = queryset.filter(
            Q(**{parent_field: parent_identifier})
            | Q(source_identifier__in=[row.source_identifier for row in records])
        )
    existing = list(queryset)
    by_source = {row.source_identifier: row for row in existing if row.source_identifier}
    name_field = 'station' if model is Metro else 'line'
    by_name = {}
    for row in existing:
        if parent_field and getattr(row, parent_field) != parent_identifier:
            continue
        key = location_key(getattr(row, name_field), model._meta.model_name)
        if key in by_name:
            raise LocationImportError('Сначала устраните дубли названий в справочнике.')
        by_name[key] = row
    created = []
    updated = []
    unchanged = 0
    result = {}
    timestamp = timezone.now()
    changed_fields = {name_field, 'source_identifier', 'updated_at'}
    for record in records:
        row = by_source.get(record.source_identifier)
        natural_match = by_name.get(location_key(record.name, model._meta.model_name))
        if row and natural_match and row.pk != natural_match.pk:
            raise LocationImportError(f'Конфликт переименования: {record.name}.')
        if row is None:
            row = natural_match
        if row and not compatible_source(row.source_identifier, record.source_identifier):
            raise LocationImportError(f'Конфликт источника: {record.name}.')
        attributes = {
            key: value for key, value in record.attributes.items()
            if key != 'legacy_code'
        }
        attributes.update({
            name_field: record.name,
            'source_identifier': record.source_identifier,
        })
        changed_fields.update(attributes)
        if row is None:
            row = model(**((create_defaults or {}) | attributes))
            created.append(row)
        elif any(getattr(row, key) != value for key, value in attributes.items()):
            for key, value in attributes.items():
                setattr(row, key, value)
            row.updated_at = timestamp
            updated.append(row)
        else:
            unchanged += 1
        result[record.source_identifier] = row
    if created:
        model.objects.bulk_create(created, batch_size=500)
    if updated:
        model.objects.bulk_update(updated, sorted(changed_fields), batch_size=500)
    return result, {
        'created': len(created), 'updated': len(updated), 'unchanged': unchanged,
    }


def compatible_source(current, incoming):
    """Allow the same source or adoption of an old OpenStreetMap identity."""
    return not current or current == incoming or re.fullmatch(
        r'(node|way|relation)/\d+(?:/subway/[^/]+(?:/(node|way|relation)/\d+)?)?', current,
    ) is not None


def upsert_geography_records(model_name, records, *, parent=None, required_id=None):
    """Match one registry namespace and load new/changed entries in batches."""
    catalog = legacy_catalog(model_name)
    scope = {}
    ancestry = {}
    if model_name == 'city':
        scope = {'legacy_region_id': parent.legacy_id}
        ancestry = scope
    elif model_name == 'district':
        scope = {'legacy_city_id': parent.legacy_id}
        ancestry = {**scope, 'legacy_region_id': parent.legacy_region_id}
    source_ids = {record.source_identifier for record in records}
    existing = catalog.select_related('location')
    if scope:
        existing = existing.filter(Q(**scope) | Q(legacy_source_identifier__in=source_ids))
    by_source, by_name, by_code = {}, {}, {}
    for alias in existing:
        source = alias.legacy_source_identifier
        if source in source_ids:
            if source in by_source:
                raise LocationImportError(f'Неоднозначный идентификатор источника: {alias.legacy_name}.')
            by_source[source] = alias
        if all(getattr(alias, field) == value for field, value in scope.items()):
            name = location_key(alias.legacy_name, model_name)
            if name in by_name:
                raise LocationImportError('Сначала устраните дубли названий в справочнике.')
            by_name[name] = alias
        if model_name == 'region':
            by_code[alias.legacy_code] = alias

    result, changed, pending, renamed = {}, [], [], []
    updated_city_parents = []
    used_ids = set()
    timestamp = timezone.now()
    for record in records:
        sourced = by_source.get(record.source_identifier)
        named = by_name.get(location_key(record.name, model_name))
        if sourced and named and sourced.pk != named.pk:
            raise LocationImportError(f'Конфликт переименования: {record.name}.')
        alias = sourced or named or by_code.get(record.attributes.get('code'))
        if required_id is not None and (alias is None or alias.legacy_id != required_id):
            raise LocationImportError('Конфликт существующей родительской территории.')
        reference = {
            'legacy_name': record.name, 'legacy_source_identifier': record.source_identifier, **ancestry,
        }
        if alias is None:
            pending.append((record, reference))
            continue
        if alias.pk in used_ids or not compatible_source(alias.legacy_source_identifier, record.source_identifier):
            raise LocationImportError(f'Конфликт источника: {record.name}.')
        used_ids.add(alias.pk)
        result[record.source_identifier] = alias
        if any(getattr(alias, field) != value for field, value in reference.items()):
            if alias.legacy_name != record.name:
                renamed.append(LocationAlias(location_id=alias.location_id, name=record.name))
            if model_name == 'city' and alias.legacy_region_id != parent.legacy_id:
                updated_city_parents.append(alias.legacy_id)
            for field, value in reference.items():
                setattr(alias, field, value)
            alias.legacy_updated_at = timestamp
            changed.append(alias)

    if changed:
        catalog.bulk_update(changed, ['legacy_name', 'legacy_source_identifier', 'legacy_updated_at', *ancestry], batch_size=500)
        LocationAlias.objects.bulk_create(renamed, batch_size=500, ignore_conflicts=True)
    if updated_city_parents:
        legacy_catalog('district').filter(legacy_city_id__in=updated_city_parents).update(legacy_region_id=parent.legacy_id)
    identifiers = reserve_legacy_ids(model_name, len(pending))
    created = register_legacy_mappings(model_name, (
        (identifier, {**reference, 'legacy_code': record.attributes.get('code', ''),
                      'legacy_created_at': timestamp, 'legacy_updated_at': timestamp})
        for identifier, (record, reference) in zip(identifiers, pending)
    ), parent=parent)
    result.update((record.source_identifier, alias) for (record, _), alias in zip(pending, created))
    return result, {'created': len(created), 'updated': len(changed), 'unchanged': len(records) - len(created) - len(changed)}


def region_record(row):
    """Build a Russian region identity from its official KLADR prefix."""
    return LocationRecord(
        f'kladr-region/{row["region_code"]}', row['region_name'],
        {'code': row['region_code']},
    )


def city_record(row):
    """Keep city identity stable across renames using its FIAS identifier."""
    return LocationRecord(
        f'fias/{row["fias_id"]}', row['city_name'],
    )


def select_region(rows, region):
    """Resolve existing Russian regions without consulting foreign catalogs."""
    matched = [row for row in rows if (
        region.source_identifier == f'kladr-region/{row["region_code"]}'
        or region.code == row['region_code']
        or location_key(region.name, 'region') == location_key(row['region_name'], 'region')
    )]
    codes = {row['region_code'] for row in matched}
    if len(codes) != 1:
        raise LocationImportError('Регион не найден однозначно в справочнике России.')
    code = codes.pop()
    return [row for row in rows if row['region_code'] == code]


def select_city(rows, city):
    """Resolve an existing city only inside its selected Russian region."""
    matched = [row for row in rows if (
        city.source_identifier == f'fias/{row["fias_id"]}'
        or location_key(city.name) == location_key(row['city_name'])
    )]
    if len(matched) != 1:
        raise LocationImportError('Город не найден однозначно в выбранном регионе России.')
    return matched[0]


def unique_records(records):
    """Collapse repeated source mentions and reject ambiguous names."""
    result = {}
    by_name = {}
    for record in records:
        key = location_key(record.name)
        previous = by_name.get(key)
        if previous and previous != record.source_identifier:
            raise LocationImportError(f'Неоднозначные названия в источнике: {record.name}.')
        by_name[key] = record.source_identifier
        result[record.source_identifier] = record
    return list(result.values())


def import_locations(dictionary, region=None, city=None):
    """Fetch open data before atomically preserving and refreshing locations."""
    if dictionary == 'metro':
        from .metro_geography import legacy_metro_city
        from .metro_import import import_legacy_metro

        reference = legacy_metro_city(region.pk, city.pk) if region and city else None
        if reference is None:
            raise LocationImportError('Выберите город этого региона.')
        return import_legacy_metro(reference)
    model_name = LEGACY_GEOGRAPHY_KEYS.get(dictionary)
    if model_name is None:
        raise LocationImportError('Неизвестный справочник импорта.')
    if dictionary != 'regions' and region is None:
        raise LocationImportError('Выберите регион России.')
    if dictionary == 'districts' and city is None:
        raise LocationImportError('Выберите город этого региона.')
    with import_guard():
        source = OpenLocationSource()
        try:
            rows = source.city_catalog()
            selected_rows = select_region(rows, region) if region else rows
            selected_city = select_city(selected_rows, city) if city else None
            if dictionary == 'regions':
                records = list({row['region_code']: region_record(row) for row in rows}.values())
            elif dictionary == 'cities':
                records = unique_records([city_record(row) for row in selected_rows])
            else:
                records = unique_records([
                    LocationRecord(identifier, name)
                    for identifier, name in source.districts(selected_city)
                ])
            with transaction.atomic():
                lock_location_catalog()
                parent = None
                if region:
                    parents, _ = upsert_geography_records(
                        'region', [region_record(selected_rows[0])], required_id=region.pk,
                    )
                    parent = next(iter(parents.values()))
                if city:
                    parents, _ = upsert_geography_records(
                        'city', [city_record(selected_city)], parent=parent, required_id=city.pk,
                    )
                    parent = next(iter(parents.values()))
                line_counts = {'created': 0, 'updated': 0, 'unchanged': 0}
                _, counts = upsert_geography_records(model_name, records, parent=parent)
                invalidate_legacy_options()
        except OpenDataError as error:
            raise LocationImportError(str(error)) from error
        except IntegrityError as error:
            raise LocationImportError(
                'Конфликт записей. Изменения текущего импорта отменены.',
            ) from error
        result = {
            **counts, 'skipped': source.skipped, 'lines': line_counts,
            'source': SOURCE_NAME, 'sourceUrl': SOURCE_URL,
        }
        logger.info('Location import dictionary=%s summary=%s', dictionary, result)
        return result
