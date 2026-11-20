"""Run persistent national imports in small atomic, restartable batches."""

import logging
import time
from pathlib import Path

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from .import_service import LocationImportError, import_guard
from .models import LocationImportJob
from .gar_source import GarSource, GarSourceError, latest_snapshot
from .gar_import import load_region

logger = logging.getLogger(__name__)
RETIRED_IMPORT_MESSAGE = 'Прежний общероссийский импорт закрыт. Контрольная точка сохранена. Запустите импорт ГАР.'


def close_retired_jobs():
    """Release the queue without clearing historical progress or summaries."""
    LocationImportJob.objects.exclude(kind='gar').filter(status__in=['queued', 'running']).update(
        status='failed', error_message=RETIRED_IMPORT_MESSAGE, updated_at=timezone.now(),
    )


def empty_counts():
    """Return independent summary counters for one dictionary."""
    return {'created': 0, 'updated': 0, 'unchanged': 0}


def start_import_job():
    """Reuse an active job or resume a failed job without duplicate workers."""
    try:
        with transaction.atomic():
            close_retired_jobs()
            active = LocationImportJob.objects.filter(kind='gar', status__in=['queued', 'running']).first()
            if active:
                return active
            previous = LocationImportJob.objects.filter(kind='gar').select_for_update().first()
            if previous and previous.status == 'failed':
                previous.status = 'queued'
                previous.error_message = ''
                previous.save(update_fields=['status', 'error_message', 'updated_at'])
                return previous
            return LocationImportJob.objects.create()
    except IntegrityError:
        return LocationImportJob.objects.get(kind='gar', status__in=['queued', 'running'])


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
    """Process GAR jobs and archive obsolete work without reading its source."""
    if job.kind == 'gar':
        return run_gar_job(job, heartbeat)
    if job.status in ('queued', 'running'):
        job.status = 'failed'
        job.error_message = RETIRED_IMPORT_MESSAGE
        job.save(update_fields=['status', 'error_message', 'updated_at'])
    return None


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
            close_retired_jobs()
            job = LocationImportJob.objects.filter(kind='gar', status__in=['queued', 'running']).last()
            if job:
                run_import_job(job, heartbeat)
                return job
    except LocationImportError:
        pass
    return False
