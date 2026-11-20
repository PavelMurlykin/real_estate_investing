"""Cover retirement of the legacy queue and continued recovery of GAR work."""

from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from location.gar_source import GarSourceError
from location.jobs import process_next_import, run_import_job, start_import_job
from location.legacy_catalog import legacy_catalog, legacy_dictionary_entries, retire_legacy_catalog_entry, save_legacy_catalog_entry
from location.models import LocationImportJob
from location.tests.test_gar import SPB


@pytest.mark.django_db(transaction=True)
def test_migration_retains_partial_legacy_import_and_original_allocator():
    """Recover committed mirror rows and preserve every existing checkpoint."""
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    previous = [
        ('location', '0017_detach_metro_line_city'),
        ('customer', '0009_detach_legacy_geography'),
        ('property', '0024_detach_complex_district'),
    ]
    executor.migrate(previous)
    try:
        historical = executor.loader.project_state(previous).apps
        region = historical.get_model('location', 'Region').objects.create(
            name='Регион незавершённого импорта', code='T7',
        )
        city = historical.get_model('location', 'City').objects.create(name='Город', region=region)
        district = historical.get_model('location', 'District').objects.create(name='Район', city=city)
        with connection.cursor() as cursor:
            cursor.execute('SELECT nextval(pg_get_serial_sequence(%s, %s))', ['region', 'id'])
            issued, = cursor.fetchone()
        old_jobs = historical.get_model('location', 'LocationImportJob').objects
        archived = [
            old_jobs.create(kind='legacy', status=status, phase='districts', catalog=[{'city_name': city.name}],
                            processed_cities=1, total_cities=3, counts={'districts': {'created': 1}},
                            coverage={'withoutDistricts': 1}, error_message='Прежний протокол')
            for status in ('completed', 'failed', 'running')
        ]
        expected = {job.pk: old_jobs.values().get(pk=job.pk) for job in archived}
        MigrationExecutor(connection).migrate(latest)
        for identifier, snapshot in expected.items():
            current = LocationImportJob.objects.values().get(pk=identifier)
            if snapshot['status'] == 'running':
                assert current['status'] == 'failed'
                assert 'Контрольная точка сохранена' in current['error_message']
                current.update(status=snapshot['status'], error_message=snapshot['error_message'])
            assert current == snapshot
        aliases = (
            ('region', region.pk, region.name), ('city', city.pk, city.name),
            ('district', district.pk, district.name),
        )
        for model_name, identifier, name in aliases:
            assert legacy_catalog(model_name).get(legacy_id=identifier).legacy_name == name
        created = save_legacy_catalog_entry('region', {'name': 'Новая область', 'code': 'NEW'})
        assert created.legacy_id > max(region.pk, issued)
        retained = legacy_catalog('region').get(legacy_id=region.pk)
        save_legacy_catalog_entry('region', {'name': 'Новое имя области'}, mapping=retained)
        retire_legacy_catalog_entry(legacy_dictionary_entries('district').get(legacy_id=district.pk))
        MigrationExecutor(connection).migrate(previous)
        MigrationExecutor(connection).migrate(latest)
        assert legacy_catalog('region').get(legacy_id=region.pk).legacy_name == 'Новое имя области'
        assert not legacy_catalog('district').filter(legacy_id=district.pk).exists()
    finally:
        MigrationExecutor(connection).migrate(latest)


@pytest.mark.django_db
@pytest.mark.parametrize('status', ['queued', 'running'])
def test_queue_releases_archived_import_without_accessing_its_source(status):
    """Archive any obsolete active job and leave its snapshot available."""
    previous = LocationImportJob.objects.create(
        kind='legacy', status=status, phase='districts', processed_cities=1, total_cities=3,
        catalog=[{'city_name': 'Город'}], counts={'districts': {'created': 1}},
    )
    with patch('location.open_data.OpenLocationSource.download') as download:
        job = start_import_job()
        assert start_import_job().pk == job.pk
        download.assert_not_called()
    previous.refresh_from_db()
    assert previous.status == 'failed'
    assert previous.processed_cities == 1 and previous.phase == 'districts'
    assert previous.catalog == [{'city_name': 'Город'}]
    assert previous.counts == {'districts': {'created': 1}}
    assert job.kind == 'gar' and job.pk != previous.pk


@pytest.mark.django_db
def test_running_gar_job_resumes_when_worker_restarts():
    """Process the GAR catalog at the next stored subject and ignore legacy jobs."""
    old_job = LocationImportJob.objects.create(kind='legacy', status='failed', error_message='Сохранённый отчёт')
    job = LocationImportJob.objects.create(
        status='running', catalog=['78'], total_regions=1, source_version='20261113',
        source_url='https://fias-file.nalog.ru/test.zip',
        counts={key: {'created': 0, 'updated': 0, 'unchanged': 0}
                for key in ('regions', 'cities', 'districts')},
    )
    with patch('location.jobs.GarSource') as source:
        source.return_value.extract_region.return_value = SPB
        assert process_next_import().pk == job.pk
        assert source.return_value.extract_region.call_count == 1
    job.refresh_from_db()
    old_job.refresh_from_db()
    assert job.status == 'completed' and job.processed_regions == 1
    assert old_job.status == 'failed' and old_job.error_message == 'Сохранённый отчёт'


@pytest.mark.django_db
def test_unexpected_error_releases_gar_job_for_retry():
    """Do not expose internal exception details through job progress."""
    job = start_import_job()
    with patch('location.jobs.latest_snapshot', side_effect=ValueError('private detail')):
        run_import_job(job)
    job.refresh_from_db()
    assert job.status == 'failed' and 'private detail' not in job.error_message
    assert start_import_job().pk == job.pk


@pytest.mark.django_db(transaction=True)
def test_single_worker_poll_reports_gar_failure_and_keeps_heartbeat(tmp_path, monkeypatch):
    """Return a CLI error for a failed GAR job and keep the worker heartbeat."""
    monkeypatch.setattr(
        'location.management.commands.process_location_imports.tempfile.gettempdir',
        lambda: str(tmp_path),
    )
    start_import_job()
    with patch('location.jobs.latest_snapshot', side_effect=GarSourceError('Источник недоступен')):
        with pytest.raises(CommandError, match='Источник недоступен'):
            call_command('process_location_imports', once=True)
    assert (tmp_path / 'location-import-worker-heartbeat').exists()
