"""Verify durable national imports, repeat runs and recovery checkpoints."""

from copy import deepcopy
from functools import partial
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from location.jobs import process_next_import, run_import_job, start_import_job
from location.models import City, District, LocationImportJob, Region
from location.open_data import OpenDataError
from location.tests.source_fixtures import load_sources, source_reply


@pytest.fixture
def source_transport():
    """Exercise real CSV and district parsers without live network requests."""
    data = load_sources()
    data['entities']['Q205'] = deepcopy(data['entities']['Q201'])
    data['entities']['Q205']['id'] = 'Q205'
    data['entities']['Q205']['labels']['ru']['value'] = 'Центральный район'
    data['entities']['Q656']['claims']['P150'][0]['mainsnak']['datavalue']['value']['id'] = 'Q205'
    with patch(
        'location.open_data.OpenLocationSource.download', side_effect=partial(source_reply, data),
    ):
        with patch('location.open_data.OpenLocationSource.prime_cities'):
            yield data


@pytest.mark.django_db
def test_national_import_creates_all_cities_and_repeats_without_changes(source_transport):
    """Import across regions independently of a selected parent and rerun."""
    first = start_import_job()
    assert start_import_job().pk == first.pk
    assert process_next_import()
    first.refresh_from_db()
    assert first.status == 'completed'
    assert first.total_cities == first.processed_cities == 3
    assert first.counts['cities']['created'] == 3
    assert Region.objects.count() == City.objects.count() == 3
    second = start_import_job()
    assert second.pk != first.pk
    run_import_job(second)
    second.refresh_from_db()
    assert second.status == 'completed'
    for counts in second.counts.values():
        assert counts['created'] == counts['updated'] == 0


@pytest.mark.django_db
def test_failed_job_resumes_after_last_committed_city(source_transport):
    """Keep earlier cities and resume a failed upstream request after reload."""
    job = start_import_job()
    with patch('location.open_data.OpenLocationSource.districts', side_effect=[
        [('wikidata/Q201', 'Тверской район')], OpenDataError('Временная ошибка'),
    ]):
        run_import_job(job)
    job.refresh_from_db()
    assert job.status == 'failed'
    assert job.processed_cities == 1
    assert District.objects.count() == 1
    assert start_import_job().pk == job.pk
    with patch('location.open_data.OpenLocationSource.districts', return_value=[]) as districts:
        process_next_import()
    job.refresh_from_db()
    assert districts.call_count == 2
    assert job.status == 'completed'
    assert job.processed_cities == 3
    assert District.objects.count() == 1


@pytest.mark.django_db
def test_running_job_is_resumed_when_worker_restarts(source_transport):
    """Persist progress across process death rather than leave a blocked button."""
    job = LocationImportJob.objects.create(status='running')
    assert process_next_import()
    job.refresh_from_db()
    assert job.status == 'completed'


@pytest.mark.django_db
def test_unexpected_error_releases_job_for_retry(source_transport):
    """Expose a recoverable failure without leaking an internal exception."""
    job = start_import_job()
    with patch(
        'location.open_data.OpenLocationSource.city_catalog', side_effect=ValueError('private'),
    ):
        run_import_job(job)
    job.refresh_from_db()
    assert job.status == 'failed'
    assert 'private' not in job.error_message
    assert start_import_job().pk == job.pk


@pytest.mark.django_db(transaction=True)
def test_single_worker_poll_reports_failure_and_uses_platform_temp_directory(
    source_transport, tmp_path, monkeypatch,
):
    """Keep the Windows command usable and return a failure for a failed job."""
    monkeypatch.setattr(
        'location.management.commands.process_location_imports.tempfile.gettempdir',
        lambda: str(tmp_path),
    )
    start_import_job()
    with patch('location.open_data.OpenLocationSource.city_catalog',
               side_effect=OpenDataError('Источник недоступен')):
        with pytest.raises(CommandError, match='Источник недоступен'):
            call_command('process_location_imports', once=True)
    assert (tmp_path / 'location-import-worker-heartbeat').exists()
