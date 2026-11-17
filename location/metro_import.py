"""Synchronize Russian metro networks independently of legacy city catalogs."""

import logging
import re

from django.db import IntegrityError, transaction

from .import_service import (
    LocationImportError, LocationRecord, import_guard, unique_records, upsert_records,
)
from .models import LocationIdentifier, Metro, MetroLine, MetroSystem
from .open_data import METRO_SCHEMES, OpenDataError, OpenLocationSource

logger = logging.getLogger(__name__)


def import_metro(system):
    """Fetch before locking rows; preserve IDs, manual geography and links."""
    if not system.location_id or system.location.name not in METRO_SCHEMES:
        raise LocationImportError('Выберите систему с российским центром, поддержанным источником.')
    identifier = LocationIdentifier.objects.filter(
        location_id=system.location_id, provider='fias',
    ).values_list('value', flat=True).first()
    if not identifier:
        raise LocationImportError('Для центра системы нужен подтверждённый идентификатор ФИАС.')
    with import_guard():
        source = OpenLocationSource()
        try:
            raw_lines, raw_stations = source.metro({
                'city_name': system.location.name, 'fias_id': identifier,
            })
            if not raw_lines or not raw_stations:
                raise LocationImportError('Источник не вернул линии и станции. Изменения не сохранены.')
            if any(not re.fullmatch(r'#[0-9A-Fa-f]{6}', color) for _, _, color in raw_lines):
                raise LocationImportError('Источник вернул некорректный цвет линии.')
            lines = unique_records([
                LocationRecord(source_identifier, name, {
                    'system_id': system.pk, 'line_color': color,
                }) for source_identifier, name, color in raw_lines
            ])
            known_lines = {line.source_identifier for line in lines}
            if any(line not in known_lines for _, _, line in raw_stations):
                raise LocationImportError('Источник содержит станции с неизвестной линией.')
            with transaction.atomic():
                # A concurrent manual move must never be silently undone by import.
                current = MetroSystem.objects.select_for_update().get(pk=system.pk)
                if current.location_id != system.location_id:
                    raise LocationImportError('Центр системы изменился. Повторите импорт.')
                conflicts = MetroLine.objects.filter(
                    source_identifier__in=known_lines,
                ).exclude(system_id=system.pk)
                if conflicts.exists():
                    raise LocationImportError('Линия источника уже относится к другой системе.')
                objects, line_counts = upsert_records(MetroLine, lines, 'system_id', system.pk)
                counts = {'created': 0, 'updated': 0, 'unchanged': 0}
                memberships = []
                for source_identifier, line in objects.items():
                    records = unique_records([
                        LocationRecord(station_identifier, name, {'metro_line_id': line.pk})
                        for station_identifier, name, parent in raw_stations
                        if parent == source_identifier
                    ])
                    stations, station_counts = upsert_records(
                        Metro, records, 'metro_line_id', line.pk,
                    )
                    memberships.extend(
                        Metro.lines.through(metro_id=station.pk, metroline_id=line.pk)
                        for station in stations.values()
                    )
                    for key in counts:
                        counts[key] += station_counts[key]
                Metro.lines.through.objects.bulk_create(memberships, ignore_conflicts=True)
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
