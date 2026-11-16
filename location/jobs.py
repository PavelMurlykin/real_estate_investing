"""Run persistent national imports in small atomic, restartable batches."""

import logging
import time
from pathlib import Path

from django.apps import apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .import_service import (
    LocationImportError, LocationRecord, city_record, import_guard,
    region_record, unique_records, upsert_records,
)
from .models import City, District, LocationImportJob, Region
from .open_data import CityNotFoundError, OpenDataError, OpenLocationSource
from .gar_source import GarSource, GarSourceError, latest_snapshot
from .gar_import import load_region
from .migration_support import backfill_locations

logger = logging.getLogger(__name__)


def empty_counts():
    """Return independent summary counters for one dictionary."""
    return {'created': 0, 'updated': 0, 'unchanged': 0}


def start_import_job(kind='gar'):
    """Reuse an active job or resume a failed job without duplicate workers."""
    try:
        with transaction.atomic():
            active = LocationImportJob.objects.filter(status__in=['queued', 'running']).first()
            if active:
                return active
            previous = LocationImportJob.objects.select_for_update().first()
            if previous and previous.status == 'failed' and previous.kind == kind:
                previous.status = 'queued'
                previous.error_message = ''
                previous.save(update_fields=['status', 'error_message', 'updated_at'])
                return previous
            return LocationImportJob.objects.create(kind=kind)
    except IntegrityError:
        return LocationImportJob.objects.get(status__in=['queued', 'running'])


def serialize_import_job(job):
    """Expose public progress without sending source snapshots to the browser."""
    if job is None:
        return None
    return {
        'id': str(job.pk), 'status': job.status, 'phase': job.phase,
        'processedCities': job.processed_cities, 'totalCities': job.total_cities,
        'currentCity': job.current_city, 'counts': job.counts,
        'coverage': job.coverage, 'errorMessage': job.error_message,
        'updatedAt': job.updated_at.isoformat(),
        'kind': job.kind, 'sourceVersion': job.source_version,
        'processedRegions': job.processed_regions, 'totalRegions': job.total_regions,
    }


def add_counts(target, summary):
    """Accumulate the result of a committed batch."""
    for key in empty_counts():
        target[key] += summary[key]


def run_import_job(job, heartbeat=lambda: None):
    """Import all Russian cities, then districts with a per-city checkpoint."""
    if job.kind == 'gar':
        return run_gar_job(job, heartbeat)
    job.status = 'running'
    job.error_message = ''
    job.save(update_fields=['status', 'error_message', 'updated_at'])
    source = OpenLocationSource()
    try:
        if job.phase == 'catalog':
            rows = source.city_catalog()
            with transaction.atomic():
                regions, region_counts = upsert_records(Region, list({
                    row['region_code']: region_record(row) for row in rows
                }.values()))
                city_counts = empty_counts()
                for code, region in regions.items():
                    records = unique_records([
                        city_record(row, region) for row in rows
                        if f'kladr-region/{row["region_code"]}' == code
                    ])
                    _, summary = upsert_records(City, records, 'region_id', region.pk)
                    add_counts(city_counts, summary)
                job.catalog = rows
                job.counts = {
                    'regions': region_counts, 'cities': city_counts,
                    'districts': empty_counts(),
                }
                job.coverage = {'withoutDistricts': 0, 'unresolvedCities': []}
                job.total_cities = len(rows)
                job.phase = 'districts'
                job.save()
        rows = job.catalog
        remaining = rows[job.processed_cities:]
        job.phase = 'preparing'
        job.current_city = ''
        job.save(update_fields=['phase', 'current_city', 'updated_at'])

        def preparation_heartbeat():
            """Keep persistent progress fresh during batched source preparation."""
            heartbeat()
            LocationImportJob.objects.filter(pk=job.pk).update(updated_at=timezone.now())

        source.prime_cities(remaining, preparation_heartbeat)
        job.phase = 'districts'
        job.save(update_fields=['phase', 'updated_at'])
        cities = {
            city.source_identifier: city for city in
            City.objects.filter(source_identifier__in=[f'fias/{row["fias_id"]}' for row in rows])
        }
        for row in remaining:
            heartbeat()
            source.deadline = time.monotonic() + 45
            job.current_city = row['city_name']
            job.save(update_fields=['current_city', 'updated_at'])
            try:
                districts = source.districts(row)
            except CityNotFoundError:
                districts = []
                job.coverage['unresolvedCities'].append({
                    'name': row['city_name'], 'region': row['region_name'],
                })
            city = cities[f'fias/{row["fias_id"]}']
            with transaction.atomic():
                _, summary = upsert_records(District, unique_records([
                    LocationRecord(identifier, name, {'city_id': city.pk})
                    for identifier, name in districts
                ]), 'city_id', city.pk)
                add_counts(job.counts['districts'], summary)
                if not districts:
                    job.coverage['withoutDistricts'] += 1
                job.processed_cities += 1
                job.save(update_fields=[
                    'counts', 'coverage', 'processed_cities', 'updated_at',
                ])
        job.status = 'completed'
        job.phase = 'done'
        job.current_city = ''
        job.save(update_fields=['status', 'phase', 'current_city', 'updated_at'])
    except (OpenDataError, LocationImportError, IntegrityError) as error:
        job.refresh_from_db()
        job.status = 'failed'
        job.error_message = (
            str(error) if not isinstance(error, IntegrityError)
            else 'Конфликт записей. Исправьте дубли и продолжите импорт.'
        )
        job.save(update_fields=['status', 'error_message', 'updated_at'])
        logger.warning('National location import failed job=%s: %s', job.pk, job.error_message)
    except Exception:
        logger.exception('Unexpected national import error job=%s', job.pk)
        job.refresh_from_db()
        job.status = 'failed'
        job.error_message = 'Не удалось обработать данные. Прогресс сохранён.'
        job.save(update_fields=['status', 'error_message', 'updated_at'])


def run_gar_job(job, heartbeat=lambda: None):
    """Checkpoint each complete official subject; keep old dictionaries intact."""
    job.status, job.error_message = 'running', ''
    job.save(update_fields=['status', 'error_message', 'updated_at'])
    last_heartbeat = 0

    def pulse():
        nonlocal last_heartbeat
        if time.monotonic() - last_heartbeat > 5:
            heartbeat()
            LocationImportJob.objects.filter(pk=job.pk).update(updated_at=timezone.now())
            last_heartbeat = time.monotonic()

    try:
        if not job.source_version:
            job.source_version, job.source_url = latest_snapshot()
            job.save(update_fields=['source_version', 'source_url', 'updated_at'])
        source = GarSource(
            job.source_version, job.source_url,
            getattr(settings, 'GAR_CACHE_DIRECTORY', Path(settings.BASE_DIR) / 'outputs' / 'gar-cache'),
            pulse,
        )
        if not job.catalog:
            job.catalog = source.regions()
            job.total_regions = len(job.catalog)
            job.counts = {name: empty_counts() for name in ('regions', 'cities', 'districts')}
            job.coverage = {'source': 'ГАР ФНС', 'retiredRegions': [], 'unresolvedCities': []}
            job.save()
        # Also preserve manual records created after the initial migration.
        backfill_locations(apps)
        for code in job.catalog[job.processed_regions:]:
            job.phase, job.current_city = 'extracting', f'Регион {code}'
            job.save(update_fields=['phase', 'current_city', 'updated_at'])
            records = source.extract_region(code)
            pulse()
            with transaction.atomic():
                summary = load_region(records, code, job.source_version)
                for key in summary:
                    add_counts(job.counts[key], summary[key])
                if not records:
                    job.coverage['retiredRegions'].append(code)
                job.processed_regions += 1
                job.processed_cities += sum(row['level'] in {'5', '6'} for row in records)
                job.total_cities = job.processed_cities
                job.save()
        job.status, job.phase, job.current_city = 'completed', 'done', ''
        job.save(update_fields=['status', 'phase', 'current_city', 'updated_at'])
    except Exception as error:
        logger.exception('GAR import interrupted job=%s', job.pk)
        job.refresh_from_db()
        job.status = 'failed'
        job.error_message = (str(error) if isinstance(error, GarSourceError) else
                             'Импорт ГАР прерван. Сохранённые регионы не потеряны; повторите импорт для продолжения.')
        job.save(update_fields=['status', 'error_message', 'updated_at'])


def process_next_import(heartbeat=lambda: None):
    """Acquire a session lock and safely resume even a terminated worker job."""
    try:
        with import_guard():
            job = LocationImportJob.objects.filter(status__in=['queued', 'running']).last()
            if job:
                run_import_job(job, heartbeat)
                return job
    except LocationImportError:
        pass
    return False
