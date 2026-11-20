"""Preserve developer associations while switching region identity domains."""

from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext

from api_v1.test_complex_localities import complex_catalog, import_user, locality_catalog  # noqa: F401
from bank.models import MortgageProgramRegionalCreditLimit
from location.tests.legacy_fixtures import create_legacy_fixture
from location.tests.legacy_fixtures import historical_geography_schema
from location.legacy_catalog import legacy_catalog, reserve_legacy_ids
from location.models import LocationCompatibilityEntry, Location, LocationClosure, LocationType
from property.models import Developer, DeveloperRegion
from property.services.developer_registry_upload import import_developer_registry_uploaded_file
from property.services.developer_registry_importer import import_dom_rf_developers
from property.services.developer_registry_file_client import FileDeveloperRegistryClient


def uploaded_regions(name='Регионы ЕРЗ', region='78'):
    """Build a real parser input with one declared working region."""
    return SimpleUploadedFile('regions.csv', (
        f'Застройщик;ИНН;Регион\n{name};7812345678;{region}\n'
    ).encode('utf-8'), content_type='text/csv')


@pytest.mark.django_db
def test_canonical_create_edit_legacy_api_and_filters(client, locality_catalog):
    """New and old ID domains return the same developer without changing project links."""
    developer = locality_catalog['developer']
    region = Location.objects.get(name='Пушкин').region
    old = locality_catalog['region']
    response = client.patch(f'/api/v1/developers/{developer.pk}/', {
        'regionLocationIds': [region.pk, region.pk],
    }, content_type='application/json')
    assert response.status_code == 200, response.content
    assert response.json()['regionLocations'] == [{'id': region.pk, 'name': region.name}]
    assert response.json()['regions'] == [{'id': old.pk, 'name': old.name}]
    link = DeveloperRegion.objects.get(developer=developer)
    original = DeveloperRegion.objects.values().get(pk=link.pk)
    for _ in range(2):
        with CaptureQueriesContext(connection) as queries:
            response = client.patch(f'/api/v1/developers/{developer.pk}/', {
                'regionIds': [old.pk],
            }, content_type='application/json')
        assert response.status_code == 200
        assert not any(f'{operation} "region"' in query['sql'] for query in queries for operation in ('FROM', 'JOIN'))
        assert DeveloperRegion.objects.values().get(pk=link.pk) == original
    for parameter, identifier in [('regionLocationId', region.pk), ('regionId', old.pk)]:
        rows = client.get('/api/v1/developers/', {parameter: identifier}).json()['results']
        assert developer.pk in {row['id'] for row in rows}
    assert locality_catalog['complex'].developer_id == developer.pk
    assert client.get('/api/v1/developers/', {'regionLocationId': Location.objects.get(name='Пушкин').pk}).status_code == 400


@pytest.mark.django_db
def test_new_subject_without_legacy_region_and_preserved_unmapped_links(client, locality_catalog):
    """Canonical-only subjects work; unidentified legacy associations stay visible."""
    region_type = LocationType.objects.filter(category='region').first()
    subject = Location.objects.create(name='Новый субъект', location_type=region_type)
    subject.region = subject
    subject.save(update_fields=['region'])
    LocationClosure.objects.create(ancestor=subject, descendant=subject, depth=0)
    developer = locality_catalog['developer']
    unresolved_id, = reserve_legacy_ids('region', 1)
    old_link = DeveloperRegion.objects.create(
        developer=developer, region_id=unresolved_id, legacy_region_name='Не сопоставлен',
    )
    for _ in range(2):
        response = client.patch(f'/api/v1/developers/{developer.pk}/', {
            'regionLocationIds': [subject.pk],
        }, content_type='application/json')
        assert response.status_code == 200, response.content
        assert response.json()['unmappedRegions'] == [{'id': unresolved_id, 'name': old_link.legacy_region_name}]
    assert DeveloperRegion.objects.filter(developer=developer, location=subject).count() == 1
    canonical_link = DeveloperRegion.objects.get(developer=developer, location=subject)
    assert canonical_link.region_id is None
    assert client.patch(f'/api/v1/developers/{developer.pk}/', {
        'description': 'Другие сведения',
    }, content_type='application/json').status_code == 200
    assert DeveloperRegion.objects.filter(pk=old_link.pk).exists()
    assert client.patch(f'/api/v1/developers/{developer.pk}/', {
        'regionLocationIds': [],
    }, content_type='application/json').status_code == 200
    assert DeveloperRegion.objects.filter(pk=old_link.pk).exists()
    assert not DeveloperRegion.objects.filter(pk=canonical_link.pk).exists()


@pytest.mark.django_db
def test_invalid_categories_and_mixed_domains_do_not_write(client, locality_catalog):
    """Reject city/district IDs and mixed contracts before changing a developer."""
    developer = locality_catalog['developer']
    before = Developer.objects.values().get(pk=developer.pk)
    locality = Location.objects.get(name='Стрельна')
    for payload in [
        {'regionLocationIds': [locality.pk]}, {'regionLocationIds': [locality.parent_id]},
        {'regionLocationIds': [locality.region_id], 'regionIds': [locality_catalog['region'].pk]},
    ]:
        response = client.patch(f'/api/v1/developers/{developer.pk}/', {
            'name': 'Не сохранять', **payload,
        }, content_type='application/json')
        assert response.status_code == 400
        assert Developer.objects.values().get(pk=developer.pk) == before


@pytest.mark.django_db
def test_import_repeat_and_dry_run_keep_links(client, locality_catalog, tmp_path):
    """Run the real registry parser twice and keep manual and imported associations."""
    with CaptureQueriesContext(connection) as queries:
        first = import_developer_registry_uploaded_file(uploaded_regions())
    legacy_queries = [
        query['sql'] for query in queries
        if any(f'{verb} "{table}"' in query['sql'] for verb in ('FROM', 'JOIN', 'UPDATE', 'INTO')
               for table in ('region', 'city', 'district'))
    ]
    assert not legacy_queries
    assert first.created_developer_region_links == 1 and not first.errors
    developer = Developer.objects.get(name='Регионы ЕРЗ')
    link = DeveloperRegion.objects.get(developer=developer)
    assert link.region_id == locality_catalog['region'].pk
    assert link.location_id == Location.objects.get(name='Стрельна').region_id
    before = DeveloperRegion.objects.values().get(pk=link.pk)
    second = import_developer_registry_uploaded_file(uploaded_regions())
    assert second.created_developer_region_links == 0
    assert DeveloperRegion.objects.values().get(pk=link.pk) == before
    mixed = import_developer_registry_uploaded_file(uploaded_regions(region='Санкт-Петербург (78)'))
    assert not mixed.errors and mixed.created_developer_region_links == 0
    counts = (Developer.objects.count(), DeveloperRegion.objects.count())
    source = tmp_path / 'dry.csv'
    source.write_bytes(uploaded_regions('Другой застройщик').read())
    dry = import_dom_rf_developers(client=FileDeveloperRegistryClient(source), dry_run=True)
    assert dry.dry_run
    assert counts == (Developer.objects.count(), DeveloperRegion.objects.count())


@pytest.mark.django_db
def test_import_canonical_name_and_unknown_reference(client, locality_catalog):
    """Resolve a unique canonical subject name and report unresolved locality names."""
    first = import_developer_registry_uploaded_file(uploaded_regions(region='Санкт-Петербург'))
    assert first.created_developer_region_links == 1
    before = list(DeveloperRegion.objects.values())
    invalid = import_developer_registry_uploaded_file(uploaded_regions(region='Пушкин'))
    assert invalid.errors and 'не сопоставлен' in invalid.errors[0]
    assert list(DeveloperRegion.objects.values()) == before


@pytest.mark.django_db
def test_import_can_use_a_canonical_subject_without_creating_a_legacy_region(client, locality_catalog):
    """A unique Location subject name works without fabricating Region records."""
    subject = Location.objects.create(
        name='Новый регион реестра', location_type=LocationType.objects.filter(category='region').first(),
    )
    before = legacy_catalog('region').count()
    summary = import_developer_registry_uploaded_file(uploaded_regions(region=subject.name))
    assert summary.created_developer_region_links == 1 and not summary.errors
    link = DeveloperRegion.objects.get(developer__name='Регионы ЕРЗ')
    assert link.location_id == subject.pk and link.region_id is None
    assert legacy_catalog('region').count() == before


@pytest.mark.django_db
def test_developer_list_queries_are_bounded(client, locality_catalog):
    """Do not add per-developer location or unresolved-association queries."""
    subject = Location.objects.get(name='Пушкин').region
    for index in range(24):
        developer = Developer.objects.create(name=f'Проверка регионов {index}')
        DeveloperRegion.objects.create(developer=developer, location=subject)
    with CaptureQueriesContext(connection) as queries:
        response = client.get('/api/v1/developers/', {'q': 'Проверка регионов', 'pageSize': 20, 'ordering': 'regions'})
    assert response.status_code == 200
    assert len(response.json()['results']) == 20
    assert len(queries) <= 9
    assert not any(f'{operation} "region"' in query['sql'] for query in queries for operation in ('FROM', 'JOIN'))
    options = client.get('/api/v1/developers/options/', {'canonicalLocations': 'true'}).json()
    assert options['regions'] == []
    assert client.get('/api/v1/developers/options/').json()['regions']


@pytest.mark.django_db(transaction=True)
def test_filters_find_a_mapped_legacy_link_alongside_another_location(client, locality_catalog):
    """Match a mapped fallback per link and keep old writes from removing Location-only links."""
    developer = locality_catalog['developer']
    old = locality_catalog['region']
    subject = Location.objects.get(name='Стрельна').region
    other = Location.objects.create(name='Другой субъект', location_type=subject.location_type)
    legacy_link = DeveloperRegion.objects.create(developer=developer, region_id=old.pk, is_active=False)
    canonical_link = DeveloperRegion.objects.create(developer=developer, location=other)
    for parameters in ({'regionId': old.pk}, {'regionLocationId': subject.pk}, {'regionLocationId': other.pk}):
        with CaptureQueriesContext(connection) as queries:
            response = client.get('/api/v1/developers/', {**parameters, 'ordering': 'regions'})
        assert response.status_code == 200, response.content
        row, = response.json()['results']
        assert row['id'] == developer.pk
        assert {region['id'] for region in row['regionLocations']} == {subject.pk, other.pk}
        assert row['regions'] == [{'id': old.pk, 'name': old.name}]
        assert row['unmappedRegions'] == []
        assert not any(f'{operation} "region"' in query['sql'] for query in queries for operation in ('FROM', 'JOIN'))
    migration = import_module('property.migrations.0022_complete_developer_regions')
    editor = SimpleNamespace(connection=connection)
    with historical_geography_schema() as historical_apps:
        for _ in range(2):
            migration.complete_developer_regions(historical_apps, editor)
    legacy_link.refresh_from_db()
    assert (legacy_link.location_id, legacy_link.region_id, legacy_link.legacy_region_name, legacy_link.is_active) == (
        subject.pk, old.pk, old.name, False,
    )
    detail = f'/api/v1/developers/{developer.pk}/'
    response = client.patch(detail, {'regionIds': [old.pk]}, content_type='application/json')
    assert response.status_code == 200, response.content
    assert DeveloperRegion.objects.filter(pk=canonical_link.pk, location=other).exists()
    assert set(DeveloperRegion.objects.filter(developer=developer).values_list('id', flat=True)) == {
        canonical_link.pk, legacy_link.pk,
    }


@pytest.mark.django_db
def test_legacy_region_writes_and_delete_protection_use_only_the_alias(client, locality_catalog):
    """Keep both legacy write paths working when the alias has no Region row."""
    subject = Location.objects.get(name='Стрельна').region
    another_subject = Location.objects.create(name='Новый субъект', location_type=subject.location_type)
    alias = LocationCompatibilityEntry.objects.create(
        model_name='region', legacy_id=900001, legacy_name='Наследуемый регион', location=another_subject,
    )
    assert 'region' not in connection.introspection.table_names()
    developer = locality_catalog['developer']
    with CaptureQueriesContext(connection) as queries:
        response = client.patch(
            f'/api/v1/developers/{developer.pk}/', {'regionIds': [alias.legacy_id]},
            content_type='application/json',
        )
        assert response.status_code == 200, response.content
        assert response.json()['regions'] == [{'id': alias.legacy_id, 'name': alias.legacy_name}]
        response = client.post('/api/v1/mortgage-programs/', {
            'name': 'Программа с прежним ID', 'condition': 'Условия',
            'regionalCreditLimits': [{'regionId': alias.legacy_id, 'creditLimit': '8500000.70'}],
        }, content_type='application/json')
        assert response.status_code == 201, response.content
        region_limit, = response.json()['regionalCreditLimits']
        assert (region_limit['regionId'], region_limit['regionName'], region_limit['creditLimit']) == (
            alias.legacy_id, alias.legacy_name, '8500000.70',
        )
    assert not any(f'{operation} "region"' in query['sql'] for query in queries for operation in ('FROM', 'JOIN'))
    link = DeveloperRegion.objects.get(developer=developer, region_id=alias.legacy_id)
    limit = MortgageProgramRegionalCreditLimit.objects.get(pk=region_limit['id'])
    assert link.location_id == limit.region_location_id == another_subject.pk
    route = f'/api/v1/location-dictionaries/regions/{alias.legacy_id}/'
    assert client.delete(route).status_code == 409
    link.delete()
    assert client.delete(route).status_code == 409
    limit.delete()
    assert client.delete(route).status_code == 204


@pytest.mark.django_db(transaction=True)
def test_migration_preserves_ids_and_repeats_safely():
    """Apply the actual migration twice without replacing original association rows."""
    old_target = [('property', '0019_realestatecomplexlocation_is_historical_and_more')]
    new_target = [('property', '0020_developer_region_locations')]
    executor = MigrationExecutor(connection)
    executor.migrate(old_target)
    try:
        old_apps = executor.loader.project_state(old_target).apps
        region = old_apps.get_model('location', 'Region').objects.create(name='Проверка миграции', code='78')
        location_type = old_apps.get_model('location', 'LocationType').objects.create(code='test-region', name='Субъект', category='region')
        location = old_apps.get_model('location', 'Location').objects.create(name=region.name, location_type=location_type)
        old_apps.get_model('location', 'LegacyLocationMapping').objects.create(model_name='region', legacy_id=region.pk, location=location)
        developer = old_apps.get_model('property', 'Developer').objects.create(name='Миграция')
        old_link = old_apps.get_model('property', 'DeveloperRegion').objects.create(developer=developer, region=region, is_active=False)
        original = old_apps.get_model('property', 'DeveloperRegion').objects.values().get(pk=old_link.pk)
        executor = MigrationExecutor(connection)
        executor.migrate(new_target)
        apps = executor.loader.project_state(new_target).apps
        migration = import_module('property.migrations.0020_developer_region_locations')
        with connection.schema_editor() as editor:
            migration.backfill_regions(apps, editor)
        current = apps.get_model('property', 'DeveloperRegion').objects.values().get(pk=old_link.pk)
        assert current.pop('location_id') == location.pk
        assert current == original
        assert apps.get_model('location', 'LocationIdentifier').objects.filter(provider='ru-region-code', value='78', location_id=location.pk).count() == 1
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_region_foreign_keys_detach_without_changing_links_and_amounts():
    """Round-trip both schema migrations without replacing or merging historical rows."""
    before = [
        ('bank', '0018_complete_limit_locations'),
        ('location', '0017_detach_metro_line_city'),
        ('property', '0022_complete_developer_regions'),
    ]
    after = [
        ('bank', '0019_detach_mortgage_limit_region'),
        ('property', '0023_detach_developer_region'),
    ]
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    executor.migrate(before)
    try:
        apps = executor.loader.project_state(before).apps
        region_model = apps.get_model('location', 'Region')
        first_region = region_model.objects.create(name='Прежний регион', code='T1')
        second_region = region_model.objects.create(name='Регион с конфликтом', code='T2')
        location_type = apps.get_model('location', 'LocationType').objects.create(
            code='test-stage-three-subject', name='Субъект', category='region',
        )
        subject = apps.get_model('location', 'Location').objects.create(
            name='Субъект ГАР', location_type=location_type,
        )
        for region in (first_region, second_region):
            apps.get_model('location', 'LegacyLocationMapping').objects.create(
                model_name='region', legacy_id=region.pk, location=subject, legacy_name=region.name,
            )
        developer = apps.get_model('property', 'Developer').objects.create(name='Застройщик')
        program = apps.get_model('bank', 'MortgageProgram').objects.create(
            name='Проверка отсоединения', credit_limit=Decimal('6000000'),
        )
        expected = {}
        for region, location in ((first_region, subject), (second_region, None)):
            link = apps.get_model('property', 'DeveloperRegion').objects.create(
                developer=developer, region=region, location=location,
                legacy_region_name=region.name, is_active=False,
            )
            limit = apps.get_model('bank', 'MortgageProgramRegionalCreditLimit').objects.create(
                mortgage_program=program, region=region, region_location=location, is_active=location is None,
                credit_limit=Decimal('9000000.35') if location else Decimal('8500000.80'),
            )
            for row in (link, limit):
                identity = (row._meta.app_label, row._meta.object_name, row.pk)
                expected[identity] = type(row).objects.values().get(pk=row.pk), region.name

        for targets in (after, before, after):
            executor = MigrationExecutor(connection)
            executor.migrate(targets)
            apps = executor.loader.project_state(targets).apps
            for (app_label, model_name, identifier), (saved, label) in expected.items():
                model = apps.get_model(app_label, model_name)
                current = model.objects.values().get(pk=identifier)
                if app_label == 'bank' and targets == after:
                    assert current.pop('legacy_region_name') == label
                assert current == saved
                with connection.cursor() as cursor:
                    constraints = connection.introspection.get_constraints(cursor, model._meta.db_table)
                has_old_key = any(details['foreign_key'] == ('region', 'id') for details in constraints.values())
                assert has_old_key == (targets == before)
    finally:
        MigrationExecutor(connection).migrate(latest)
