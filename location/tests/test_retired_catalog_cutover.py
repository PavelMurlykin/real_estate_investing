"""Exercise the removal guards and preservation of permanent registry rows."""

import pytest
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from location.models import LocationCompatibilityEntry, LocationIdentifier
from location.tests.legacy_fixtures import create_legacy_fixture, historical_geography_schema


RETIRED_TABLES = {'region', 'city', 'district', 'location_municipality', 'location_municipality_locations'}


@pytest.mark.django_db(transaction=True)
def test_preserves_registry_and_removes_only_retired_tables():
    """Round-trip geography and confirm that old source identifiers still resolve."""
    region = create_legacy_fixture('region', name='Область проверки', code='CHECK')
    city = create_legacy_fixture('city', name='Город проверки', region=region)
    original = list(LocationCompatibilityEntry.objects.order_by('pk').values())
    table = LocationCompatibilityEntry._meta.db_table
    with connection.cursor() as cursor:
        cursor.execute('SELECT %s::regclass::oid', [table])
        identity, = cursor.fetchone()
    with historical_geography_schema() as registry:
        old_city = registry.get_model('location', 'City').objects.get(pk=city.pk)
        assert old_city.name == city.name and old_city.region_id == region.pk
        assert RETIRED_TABLES <= set(connection.introspection.table_names())
    assert not RETIRED_TABLES.intersection(connection.introspection.table_names())
    with connection.cursor() as cursor:
        cursor.execute('SELECT %s::regclass::oid', [table])
        assert cursor.fetchone() == (identity,)
    assert list(LocationCompatibilityEntry.objects.order_by('pk').values()) == original
    assert LocationIdentifier.objects.get(provider='legacy', value=f'city/{city.pk}').location_id == city.entry.location_id
    for model_name in ('Region', 'City', 'District', 'Municipality', 'LegacyLocationMapping'):
        with pytest.raises(LookupError):
            apps.get_model('location', model_name)


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize('obstacle', ['municipality', 'unmapped', 'foreign_key'])
def test_cutover_stops_before_dropping_valuable_or_referenced_tables(obstacle):
    """Retain all original tables if a precondition fails."""
    region = create_legacy_fixture('region', name='Регион проверки', code='CHECK')
    with historical_geography_schema() as historical:
        if obstacle == 'municipality':
            municipality = historical.get_model('location', 'Municipality').objects.create(
                name='Проверка', identifier='test-municipality', region_id=region.entry.location_id,
                municipality_type='Проверка',
            )
            municipality.locations.add(region.entry.location_id)
            reason = 'Есть данные муниципальных образований'
        elif obstacle == 'unmapped':
            unmapped = historical.get_model('location', 'Region').objects.create(name='Без ID', code='MISSING')
            reason = 'есть ID без соответствия'
        else:
            with connection.cursor() as cursor:
                cursor.execute('CREATE TABLE cutover_test_reference (region_id bigint REFERENCES region(id))')
            reason = 'ещё имеют внешние ссылки'
        try:
            executor = MigrationExecutor(connection)
            with pytest.raises(RuntimeError, match=reason):
                executor.migrate(executor.loader.graph.leaf_nodes())
            assert RETIRED_TABLES <= set(connection.introspection.table_names())
            if obstacle == 'municipality':
                assert municipality.locations.get().pk == region.entry.location_id
        finally:
            if obstacle == 'municipality':
                municipality.delete()
            elif obstacle == 'unmapped':
                unmapped.delete()
            else:
                with connection.cursor() as cursor:
                    cursor.execute('DROP TABLE cutover_test_reference')
