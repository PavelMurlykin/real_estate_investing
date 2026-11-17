"""Atomically synchronize Russian location dictionaries from open data APIs."""

import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field

from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from .models import City, District, Metro, MetroLine, MetroSystem, Region
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


def upsert_records(model, records, parent_field=None, parent_identifier=None):
    """Match stable source IDs, adopt natural keys, then bulk write changes."""
    queryset = model.objects.all()
    if parent_field:
        queryset = queryset.filter(
            Q(**{parent_field: parent_identifier})
            | Q(source_identifier__in=[row.source_identifier for row in records])
        )
    existing = list(queryset)
    by_source = {row.source_identifier: row for row in existing if row.source_identifier}
    name_field = 'station' if model is Metro else 'line' if model is MetroLine else 'name'
    by_name = {}
    for row in existing:
        if parent_field and getattr(row, parent_field) != parent_identifier:
            continue
        key = location_key(getattr(row, name_field), model._meta.model_name)
        if key in by_name:
            raise LocationImportError('Сначала устраните дубли названий в справочнике.')
        by_name[key] = row
    by_code = {row.code: row for row in existing} if model is Region else {}
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
        if row is None and model is Region:
            row = by_code.get(record.attributes['code']) or by_code.get(
                record.attributes.get('legacy_code'),
            )
        if (
            row and row.source_identifier not in (None, record.source_identifier)
            and not re.fullmatch(
                r'(node|way|relation)/\d+(?:/subway/[^/]+(?:/(node|way|relation)/\d+)?)?',
                row.source_identifier,
            )
        ):
            raise LocationImportError(f'Конфликт источника: {record.name}.')
        attributes = {
            key: value for key, value in record.attributes.items()
            if key != 'legacy_code'
        }
        if model is Region and row:
            attributes['code'] = row.code
        attributes.update({
            name_field: record.name,
            'source_identifier': record.source_identifier,
        })
        changed_fields.update(attributes)
        if row is None:
            row = model(**attributes)
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


def region_record(row):
    """Build a Russian region identity from its official KLADR prefix."""
    return LocationRecord(
        f'kladr-region/{row["region_code"]}', row['region_name'],
        {'code': row['region_code']},
    )


def city_record(row, region):
    """Keep city identity stable across renames using its FIAS identifier."""
    return LocationRecord(
        f'fias/{row["fias_id"]}', row['city_name'], {'region_id': region.pk},
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
    if dictionary == 'metro' and city is not None:
        from .models import LegacyLocationMapping
        from .metro_import import import_metro

        location_id = LegacyLocationMapping.objects.filter(
            model_name='city', legacy_id=city.pk,
        ).values_list('location_id', flat=True).first()
        system = MetroSystem.objects.select_related('location').filter(
            location_id=location_id,
        ).first() if location_id else None
        if system:
            return import_metro(system)
    if dictionary not in ('regions', 'cities', 'districts', 'metro'):
        raise LocationImportError('Неизвестный справочник импорта.')
    with import_guard():
        source = OpenLocationSource()
        try:
            rows = source.city_catalog()
            selected_rows = select_region(rows, region) if region else rows
            selected_city = select_city(selected_rows, city) if city else None
            if dictionary == 'regions':
                records = list({row['region_code']: region_record(row) for row in rows}.values())
            elif dictionary == 'cities':
                records = unique_records([city_record(row, region) for row in selected_rows])
            elif dictionary == 'districts':
                records = unique_records([
                    LocationRecord(identifier, name, {'city_id': city.pk})
                    for identifier, name in source.districts(selected_city)
                ])
            else:
                raw_lines, raw_stations = source.metro(selected_city)
                lines = unique_records([
                    LocationRecord(identifier, name, {'city_id': city.pk, 'line_color': color})
                    for identifier, name, color in raw_lines
                ])
                records = [
                    LocationRecord(identifier, name, {'line_source_identifier': line_identifier})
                    for identifier, name, line_identifier in raw_stations
                ]
            with transaction.atomic():
                if region:
                    parents, _ = upsert_records(Region, [region_record(selected_rows[0])])
                    if next(iter(parents.values())).pk != region.pk:
                        raise LocationImportError('Конфликт существующего региона.')
                if city:
                    parents, _ = upsert_records(
                        City, [city_record(selected_city, region)], 'region_id', region.pk,
                    )
                    if next(iter(parents.values())).pk != city.pk:
                        raise LocationImportError('Конфликт существующего города.')
                line_counts = {'created': 0, 'updated': 0, 'unchanged': 0}
                if dictionary == 'metro':
                    system, _ = MetroSystem.objects.get_or_create(
                        name=f'Метрополитен: {city.name}',
                    )
                    lines = [LocationRecord(row.source_identifier, row.name, {
                        **row.attributes, 'system_id': system.pk,
                    }) for row in lines]
                    line_objects, line_counts = upsert_records(
                        MetroLine, lines, 'city_id', city.pk,
                    )
                    counts = {'created': 0, 'updated': 0, 'unchanged': 0}
                    for identifier, line in line_objects.items():
                        stations = unique_records([
                            LocationRecord(
                                row.source_identifier, row.name, {'metro_line_id': line.pk},
                            )
                            for row in records
                            if row.attributes['line_source_identifier'] == identifier
                        ])
                        station_objects, station_counts = upsert_records(
                            Metro, stations, 'metro_line_id', line.pk,
                        )
                        Metro.lines.through.objects.bulk_create([
                            Metro.lines.through(metro_id=row.pk, metroline_id=line.pk)
                            for row in station_objects.values()
                        ], ignore_conflicts=True)
                        for key in counts:
                            counts[key] += station_counts[key]
                else:
                    model = {'regions': Region, 'cities': City, 'districts': District}[dictionary]
                    parent_field = {'cities': 'region_id', 'districts': 'city_id'}.get(dictionary)
                    parent_identifier = (
                        region.pk if dictionary == 'cities' else city.pk if city else None
                    )
                    _, counts = upsert_records(model, records, parent_field, parent_identifier)
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
