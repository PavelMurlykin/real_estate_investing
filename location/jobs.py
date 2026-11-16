"""Run persistent national imports in small atomic, restartable batches."""

import logging
import time

from django.db import IntegrityError, transaction
from django.utils import timezone

from .import_service import (
    LocationImportError, LocationRecord, city_record, import_guard,
    region_record, unique_records, upsert_records,
)
from .models import City, District, LocationImportJob, Region
from .open_data import CityNotFoundError, OpenDataError, OpenLocationSource

logger = logging.getLogger(__name__)


def empty_counts():
    """Return independent summary counters for one dictionary."""
    return {'created': 0, 'updated': 0, 'unchanged': 0}


def start_import_job():
    """Reuse an active job or resume a failed job without duplicate workers."""
    try:
        with transaction.atomic():
            active = LocationImportJob.objects.filter(status__in=['queued', 'running']).first()
            if active:
                return active
            previous = LocationImportJob.objects.select_for_update().first()
            if previous and previous.status == 'failed':
                previous.status = 'queued'
                previous.error_message = ''
                previous.save(update_fields=['status', 'error_message', 'updated_at'])
                return previous
            return LocationImportJob.objects.create()
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
    }


def add_counts(target, summary):
    """Accumulate the result of a committed batch."""
    for key in empty_counts():
        target[key] += summary[key]


def run_import_job(job, heartbeat=lambda: None):
    """Import all Russian cities, then districts with a per-city checkpoint."""
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
