"""Verify additive metro migration and idempotent canonical imports."""

from functools import partial
from unittest.mock import patch

import pytest
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from location.import_service import LocationImportError
from location.metro_import import import_metro
from location.metro_migration import backfill_metro
from location.migration_support import backfill_locations
from location.models import (
    City, Location, LocationIdentifier, LocationType,
    Metro, MetroLine, MetroSystem, Region,
)
from location.tests.source_fixtures import load_sources, source_reply
from property.models import (
    Developer, RealEstateClass, RealEstateComplex, RealEstateComplexLocation,
    RealEstateComplexMetroAvailability, RealEstateType, TransportAccessibilityType,
)


@pytest.fixture
def metro_geography():
    """Use a network center and suburban localities in distinct regions."""
    kind = LocationType.objects.create(code='metro-region', category='region', name='Город', abbreviation='г.')
    center = Location.objects.create(name='Москва', location_type=kind)
    center.region = center
    center.save()
    LocationIdentifier.objects.create(location=center, provider='fias', value='0c5b2444-70a0-4932-980c-b4dc0d3f02b5')
    locality_kind = LocationType.objects.create(code='metro-locality', category='locality', name='Город')
    suburb = Location.objects.create(name='Котельники', location_type=locality_kind)
    system = MetroSystem.objects.create(name='Московский метрополитен', location=center)
    line = MetroLine.objects.create(line='Сокольническая', line_color='#000000', system=system)
    station = Metro.objects.create(station='Охотный Ряд', metro_line=line, location=suburb,
                                   location_is_inferred=False, is_active=False)
    return system, line, station, suburb


def create_complex_link(station, locality):
    """Retain the exact availability row, time and transport across imports."""
    complex_object = RealEstateComplex.objects.create(
        name='Проверка метро', developer=Developer.objects.create(name='Застройщик метро'),
        real_estate_class=RealEstateClass.objects.create(name='Комфорт', weight=1),
        real_estate_type=RealEstateType.objects.create(name='Квартиры'),
    )
    RealEstateComplexLocation.objects.create(real_estate_complex=complex_object, location=locality, is_primary=True)
    return RealEstateComplexMetroAvailability.objects.create(
        real_estate_complex=complex_object, metro=station, walking_time_minutes=25,
        transport_accessibility_type=TransportAccessibilityType.objects.create(name='Транспорт'),
    )


@pytest.mark.django_db
def test_canonical_import_adopts_preserves_and_repeats(metro_geography):
    """Run real parsers twice without legacy cities, replacing only HTTP transport."""
    system, line, station, suburb = metro_geography
    link = create_complex_link(station, suburb)
    link_values = RealEstateComplexMetroAvailability.objects.values().get(pk=link.pk)
    sources = load_sources()
    with patch('location.open_data.OpenLocationSource.download', side_effect=partial(source_reply, sources)):
        first = import_metro(system)
        repeat = import_metro(system)
    assert first['lines']['created'] == 0 and first['created'] == 1
    assert repeat['created'] == repeat['updated'] == 0
    assert repeat['lines']['created'] == repeat['lines']['updated'] == 0
    station.refresh_from_db()
    assert station.location_id == suburb.pk and not station.location_is_inferred
    assert not station.is_active and station.metro_line_id == line.pk
    assert station.lines.filter(pk=line.pk).exists()
    assert City.objects.count() == Region.objects.count() == 0
    assert RealEstateComplexMetroAvailability.objects.values().get(pk=link.pk) == link_values
    backfill_locations(apps)
    station.refresh_from_db()
    assert station.location_id == suburb.pk


@pytest.mark.django_db
def test_incomplete_or_conflicting_source_is_atomic(metro_geography):
    """Reject an empty response and a station with an unknown line before writes."""
    system, line, _, _ = metro_geography
    original = list(MetroLine.objects.values())
    for payload in [([], []), ([('line/1', 'Новая', '#123456')], [('station/1', 'Станция', 'absent')])]:
        with patch('location.metro_import.OpenLocationSource.metro', return_value=payload):
            with pytest.raises(LocationImportError):
                import_metro(system)
        assert list(MetroLine.objects.values()) == original
    assert line.city_id is None


@pytest.mark.django_db(transaction=True)
def test_actual_metro_migration_preserves_ids_links_and_repeat():
    """Migrate old rows forward, reverse and reapply without replacing references."""
    previous = [('location', '0009_locationtype_locationimportjob_kind_and_more')]
    target = [('location', '0015_metro_legacy_geography')]
    try:
        MigrationExecutor(connection).migrate(previous)
        registry = MigrationExecutor(connection).loader.project_state(previous).apps
        old_region = registry.get_model('location', 'Region').objects.create(name='Санкт-Петербург', code='78')
        old_city = registry.get_model('location', 'City').objects.create(name='Санкт-Петербург', region_id=old_region.pk)
        line = registry.get_model('location', 'MetroLine').objects.create(line='Первая', line_color='#123456', city_id=old_city.pk)
        station = registry.get_model('location', 'Metro').objects.create(station='Автово', metro_line_id=line.pk)
        old_fields = [field.attname for field in station._meta.concrete_fields]
        snapshot = registry.get_model('location', 'Metro').objects.values(*old_fields).get(pk=station.pk)
        MigrationExecutor(connection).migrate(target)
        current = Metro.objects.get(pk=station.pk)
        assert Metro.objects.values(*old_fields).get(pk=station.pk) == snapshot
        assert current.location_is_inferred
        assert current.lines.filter(pk=line.pk).exists()
        assert current.metro_line.system_id is not None
        assert current.metro_line.legacy_city_name == old_city.name
        assert current.metro_line.legacy_region_id == old_region.pk
        kind = LocationType.objects.create(code='migration-town', category='locality', name='Город')
        locality = Location.objects.create(name='Стрельна', location_type=kind)
        link = create_complex_link(current, locality)
        link_snapshot = RealEstateComplexMetroAvailability.objects.values().get(pk=link.pk)
        backfill_metro(apps, connection.schema_editor())
        assert current.lines.count() == 1
        MigrationExecutor(connection).migrate(previous)
        MigrationExecutor(connection).migrate(target)
        assert Metro.objects.values(*old_fields).get(pk=station.pk) == snapshot
        assert RealEstateComplexMetroAvailability.objects.values().get(pk=link.pk) == link_snapshot
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
