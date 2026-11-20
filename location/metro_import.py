"""Synchronize Russian metro networks independently of legacy city catalogs."""

import logging
import re

from django.db import IntegrityError, transaction

from .catalog_service import lock_location_catalog
from .import_service import (
    LocationImportError, LocationRecord, import_guard, select_city, select_region, unique_records, upsert_records,
)
from .metro_geography import legacy_metro_city
from .models import LocationIdentifier, Metro, MetroLine, MetroSystem
from .open_data import METRO_SCHEMES, OpenDataError, OpenLocationSource

logger = logging.getLogger(__name__)


def import_metro(system):
    """Fetch before locking rows; preserve IDs, manual geography and links."""
    if not system.location_id or system.location.name not in METRO_SCHEMES:
        raise LocationImportError('Выберите систему с российским центром, поддержанным источником.')
    identifier = _fias_identifier(system.location_id)
    if not identifier:
        raise LocationImportError('Для центра системы нужен подтверждённый идентификатор ФИАС.')
    return _run_metro_import(system.location.name, identifier, system=system)


def import_legacy_metro(city):
    """Import by network while retaining the original API city identity."""
    return _run_metro_import(city.center_name, legacy=city)


def _fias_identifier(location_id):
    """Keep provider line IDs stable when switching between import entry points."""
    if location_id:
        return LocationIdentifier.objects.filter(location_id=location_id, provider='fias').order_by('pk').values_list(
            'value', flat=True,
        ).first()
    return None


def _run_metro_import(center_name, identifier=None, *, system=None, legacy=None):
    """Read and validate the source before applying one atomic metro update."""
    with import_guard():
        source = OpenLocationSource()
        try:
            if legacy:
                identifier = _fias_identifier(legacy.location_id)
                if not identifier:
                    row = select_city(select_region(source.city_catalog(), legacy.region), legacy.city)
                    center_name, identifier = row['city_name'], row['fias_id']
            raw_lines, raw_stations = source.metro({'city_name': center_name, 'fias_id': identifier})
            if not raw_lines or not raw_stations:
                raise LocationImportError('Источник не вернул линии и станции. Изменения не сохранены.')
            if any(not re.fullmatch(r'#[0-9A-Fa-f]{6}', color) for _, _, color in raw_lines):
                raise LocationImportError('Источник вернул некорректный цвет линии.')
            known_lines = {source_identifier for source_identifier, _, _ in raw_lines}
            if any(line not in known_lines for _, _, line in raw_stations):
                raise LocationImportError('Источник содержит станции с неизвестной линией.')
            with transaction.atomic():
                if legacy:
                    lock_location_catalog()
                    current_scope = legacy_metro_city(legacy.region.pk, legacy.city.pk)
                    if current_scope is None or current_scope.location_id != legacy.location_id:
                        raise LocationImportError('Привязка города изменилась. Повторите импорт.')
                    legacy = current_scope
                    system = _resolve_legacy_system(legacy, center_name, identifier)
                else:
                    current = MetroSystem.objects.select_for_update().get(pk=system.pk)
                    if current.location_id != system.location_id:
                        raise LocationImportError('Центр системы изменился. Повторите импорт.')
                conflicts = MetroLine.objects.filter(
                    source_identifier__in=known_lines,
                ).exclude(system_id=system.pk)
                if conflicts.exists():
                    raise LocationImportError('Линия источника уже относится к другой системе.')
                counts, line_counts = _save_network(system, raw_lines, raw_stations, legacy)
        except OpenDataError as error:
            raise LocationImportError(str(error)) from error
        except IntegrityError as error:
            raise LocationImportError('Конфликт записей. Изменения импорта отменены.') from error
    result = {
        **counts, 'lines': line_counts, 'skipped': source.skipped,
        'source': 'Wikimedia', 'sourceUrl': 'https://ru.wikipedia.org/',
    }
    logger.info('Metro import system=%s summary=%s', system.pk, result)
    return result


def _resolve_legacy_system(scope, name, identifier):
    """Recover historical lines in place and require explicit choice on ambiguity."""
    location_id = scope.location_id
    if identifier:
        source, _ = LocationIdentifier.objects.get_or_create(
            provider='fias', value=identifier, defaults={'location_id': location_id},
        )
        if source.location_id != location_id:
            raise LocationImportError('Идентификатор города уже сопоставлен с другой локацией.')
    systems = MetroSystem.objects.all()
    identifiers = list(systems.filter(metroline__legacy_city_id=scope.city.pk)
                       .order_by('pk').values_list('pk', flat=True).distinct()[:2])
    if not identifiers:
        identifiers = list(systems.filter(location_id=location_id).values_list('pk', flat=True)[:2])
    if len(identifiers) > 1:
        raise LocationImportError('Для города найдено несколько сетей. Выберите систему метро.')
    locked = systems.select_for_update()
    if identifiers:
        system = locked.get(pk=identifiers[0])
    else:
        system, _ = locked.get_or_create(name=f'Метрополитен: {name}', defaults={'location_id': location_id})
    if system.location_id is None:
        system.location_id = location_id
        system.save(update_fields=['location'])
    elif system.location_id != location_id:
        raise LocationImportError('Город соответствует другому центру. Выберите систему метро.')
    MetroLine.objects.filter(legacy_city_id=scope.city.pk, system_id=None).update(system_id=system.pk)
    return system


def _save_network(system, raw_lines, raw_stations, legacy):
    """Match by network and source while preserving manual and legacy associations."""
    lines = unique_records([
        LocationRecord(identifier, name, {'system_id': system.pk, 'line_color': color})
        for identifier, name, color in raw_lines
    ])
    legacy_defaults = {
        'legacy_city_id': legacy.city.pk, 'legacy_city_name': legacy.city.name,
        'legacy_region_id': legacy.region.pk, 'legacy_region_name': legacy.region.name,
    } if legacy else None
    objects, line_counts = upsert_records(MetroLine, lines, 'system_id', system.pk, create_defaults=legacy_defaults)
    counts = {'created': 0, 'updated': 0, 'unchanged': 0}
    memberships = []
    for source_identifier, line in objects.items():
        records = unique_records([
            LocationRecord(identifier, name, {'metro_line_id': line.pk})
            for identifier, name, parent in raw_stations if parent == source_identifier
        ])
        stations, station_counts = upsert_records(Metro, records, 'metro_line_id', line.pk)
        memberships.extend(Metro.lines.through(metro_id=station.pk, metroline_id=line.pk) for station in stations.values())
        for key in counts:
            counts[key] += station_counts[key]
    Metro.lines.through.objects.bulk_create(memberships, ignore_conflicts=True)
    return counts, line_counts
