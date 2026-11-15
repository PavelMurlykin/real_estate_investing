"""Exercise Russian scope, stable updates, atomicity and bounded loading."""

import copy
import json
from pathlib import Path
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest
from django.db import connection

from location.models import City, District, Metro, MetroLine, Region
from location.osm_import import (
    IMPORT_LOCK_IDENTIFIER,
    LocationImportError,
    build_query,
    download_overpass,
    import_locations,
)


@pytest.fixture
def source_payload():
    """Read a small representative source fixture independent of the network."""
    fixture = Path(__file__).parent / 'data' / 'overpass.json'
    return json.loads(fixture.read_text(encoding='utf-8'))


@pytest.fixture
def imported_hierarchy(source_payload):
    """Create the imported Russian parent hierarchy used by child imports."""
    region = Region.objects.create(
        name='Москва', code='77', source_identifier='relation/2555133',
    )
    city = City.objects.create(
        name='Москва', region=region, source_identifier='relation/2555133',
    )
    return region, city


@pytest.mark.django_db
def test_regions_adopt_existing_and_refresh_by_source_identity(source_payload):
    """Preserve primary keys, local codes, status and children across renames."""
    region = Region.objects.create(name='Москва', code='77', is_active=False)
    city = City.objects.create(name='Москва', region=region)
    with patch('location.osm_import.download_overpass', return_value=source_payload['regions']):
        first = import_locations('regions')
        second = import_locations('regions')
        renamed = copy.deepcopy(source_payload['regions'])
        renamed[0]['tags']['name'] = 'Новое название Москвы'
    with patch('location.osm_import.download_overpass', return_value=renamed):
        third = import_locations('regions')
    region.refresh_from_db()
    city.refresh_from_db()
    assert first['created'] == 1
    assert first['updated'] == 1
    assert first['skipped'] == 1
    assert second['created'] == second['updated'] == 0
    assert second['unchanged'] == 2
    assert third['updated'] == 1
    assert region.name == 'Новое название Москвы'
    assert region.code == '77'
    assert region.is_active is False
    assert region.source_identifier == 'relation/2555133'
    assert city.region_id == region.pk
    assert not Region.objects.filter(name='Берлин').exists()


@pytest.mark.django_db
def test_city_places_deduplicate_nodes_and_boundaries(source_payload, imported_hierarchy):
    """Prefer city boundary IDs and retain one federal city per region."""
    region, city = imported_hierarchy
    elements = [source_payload['regions'][0], *source_payload['cities']]
    with patch('location.osm_import.download_overpass', return_value=elements):
        first = import_locations('cities', region)
        second = import_locations('cities', region)
    assert first['created'] == 2
    assert second['created'] == second['updated'] == 0
    assert City.objects.filter(region=region).count() == 3
    assert City.objects.get(name='Зеленоград').source_identifier == 'relation/102'
    assert City.objects.get(name='Киевский').source_identifier == 'way/105'
    assert City.objects.get(name='Москва').pk == city.pk
    assert not City.objects.filter(name='Деревня').exists()


@pytest.mark.django_db
def test_ambiguous_city_homonyms_are_reported_without_merging(
    source_payload, imported_hierarchy,
):
    """Skip indistinguishable names while importing other valid cities."""
    region, _ = imported_hierarchy
    elements = [source_payload['regions'][0], *source_payload['cities'],
        {'type': 'node', 'id': 500, 'tags': {'place': 'town', 'name': 'Одноимённый'}},
        {'type': 'node', 'id': 501, 'tags': {'place': 'town', 'name': 'Одноимённый'}},
    ]
    with patch('location.osm_import.download_overpass', return_value=elements):
        result = import_locations('cities', region)
    assert result['created'] == 2
    assert result['skipped'] == 2
    assert not City.objects.filter(name='Одноимённый').exists()


@pytest.mark.django_db
def test_districts_update_and_keep_existing_parent_links(source_payload, imported_hierarchy):
    """Import urban subdivisions, normalize whitespace and keep the city."""
    region, city = imported_hierarchy
    elements = [source_payload['regions'][0], *source_payload['districts']]
    with patch('location.osm_import.download_overpass', return_value=elements):
        first = import_locations('districts', region, city)
        second = import_locations('districts', region, city)
    assert first['created'] == 2
    assert second['unchanged'] == 2
    assert District.objects.get(source_identifier='relation/200').name == 'Тверской район'
    assert set(District.objects.values_list('city_id', flat=True)) == {city.pk}


@pytest.mark.django_db
def test_metro_groups_directions_updates_lines_and_preserves_stations(
    source_payload, imported_hierarchy,
):
    """Avoid direction/stop duplicates and update renamed stations and colors."""
    region, city = imported_hierarchy
    line = MetroLine.objects.create(line='Сокольническая', line_color='#000000', city=city)
    station = Metro.objects.create(station='Охотный Ряд', metro_line=line, is_active=False)
    elements = [source_payload['regions'][0], *source_payload['metro']]
    with patch('location.osm_import.download_overpass', return_value=elements):
        first = import_locations('metro', region, city)
        second = import_locations('metro', region, city)
    changed = copy.deepcopy(elements)
    changed[1]['tags']['colour'] = '#FFFFFF'
    changed[4]['tags']['name'] = 'Переименованная станция'
    changed[7]['tags']['name'] = 'Переименованная станция'
    with patch('location.osm_import.download_overpass', return_value=changed):
        third = import_locations('metro', region, city)
    station.refresh_from_db()
    line.refresh_from_db()
    assert first['created'] == 1
    assert first['updated'] == 1
    assert first['lines']['updated'] == 1
    assert second['created'] == second['updated'] == 0
    assert third['updated'] == 1
    assert third['lines']['updated'] == 1
    assert line.line_color == '#FFFFFF'
    assert station.station == 'Переименованная станция'
    assert station.is_active is False
    assert Metro.objects.count() == 2
    assert MetroLine.objects.count() == 1


@pytest.mark.django_db
def test_conflicting_region_rolls_back_entire_import(source_payload):
    """A late identity conflict must roll back earlier batch changes."""
    existing = Region.objects.create(
        name='Москва', code='77', source_identifier='relation/999999',
    )
    with patch('location.osm_import.download_overpass', return_value=source_payload['regions']):
        with pytest.raises(LocationImportError, match='Конфликт'):
            import_locations('regions')
    existing.refresh_from_db()
    assert existing.source_identifier == 'relation/999999'
    assert Region.objects.count() == 1


@pytest.mark.django_db
def test_station_conflict_rolls_back_a_saved_line(source_payload, imported_hierarchy):
    """Roll back an already written line when a later station conflicts."""
    region, city = imported_hierarchy
    line = MetroLine.objects.create(
        city=city, line='Сокольническая', line_color='#000000',
    )
    Metro.objects.create(
        station='Лубянка', metro_line=line, source_identifier='other-source',
    )
    elements = [source_payload['regions'][0], *source_payload['metro']]
    with patch('location.osm_import.download_overpass', return_value=elements):
        with pytest.raises(LocationImportError, match='Конфликт источника'):
            import_locations('metro', region, city)
    line.refresh_from_db()
    assert line.source_identifier is None
    assert line.line_color == '#000000'
    assert Metro.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_simultaneous_import_is_rejected_before_extraction():
    """Use a real second PostgreSQL session to verify the cross-worker lock."""
    other_connection = connection.copy(alias='location-import-lock')
    try:
        with other_connection.cursor() as cursor:
            cursor.execute(
                'SELECT pg_advisory_lock(%s)', [IMPORT_LOCK_IDENTIFIER],
            )
        with patch('location.osm_import.download_overpass') as download:
            with pytest.raises(LocationImportError, match='Другой импорт'):
                import_locations('regions')
        download.assert_not_called()
    finally:
        other_connection.close()


@pytest.mark.django_db
def test_import_releases_guard_after_source_failure(source_payload):
    """A failed download must not block the next administrator request."""
    with patch(
        'location.osm_import.download_overpass',
        side_effect=LocationImportError('Недоступен'),
    ):
        with pytest.raises(LocationImportError):
            import_locations('regions')
    with patch('location.osm_import.download_overpass', return_value=source_payload['regions']):
        assert import_locations('regions')['created'] == 2


@pytest.mark.django_db
def test_changed_city_region_updates_the_existing_identity(source_payload, imported_hierarchy):
    """Refresh a city parent without replacing its primary key or children."""
    region, _ = imported_hierarchy
    previous_region = Region.objects.create(name='Другой регион', code='TEST')
    city = City.objects.create(
        name='Зеленоград', region=previous_region,
        source_identifier='relation/102',
    )
    district = District.objects.create(name='Район', city=city)
    elements = [source_payload['regions'][0], *source_payload['cities']]
    with patch('location.osm_import.download_overpass', return_value=elements):
        assert import_locations('cities', region)['updated'] == 1
    city.refresh_from_db()
    district.refresh_from_db()
    assert city.region_id == region.pk
    assert district.city_id == city.pk


@pytest.mark.django_db
def test_missing_russian_scope_does_not_import_children(source_payload, imported_hierarchy):
    """An arbitrary or foreign parent cannot import places into Russia."""
    region, _ = imported_hierarchy
    with patch('location.osm_import.download_overpass', return_value=source_payload['cities']):
        with pytest.raises(LocationImportError, match='Россия'):
            import_locations('cities', region)
    assert City.objects.count() == 1


@pytest.mark.django_db
def test_missing_city_boundary_rejects_city_import(source_payload, imported_hierarchy):
    """Do not substitute region-wide districts for a missing city boundary."""
    region, city = imported_hierarchy
    city.source_identifier = 'node/100'
    city.name = 'Город без границы'
    elements = [*source_payload['districts'], source_payload['regions'][0]]
    with patch('location.osm_import.download_overpass', return_value=elements):
        with pytest.raises(LocationImportError, match='граница города'):
            import_locations('districts', region, city)
    assert not District.objects.exists()


@pytest.mark.django_db
def test_empty_urban_children_are_valid_without_deleting_existing(
    source_payload, imported_hierarchy,
):
    """Cities without metro can return zero without destructive synchronization."""
    region, city = imported_hierarchy
    elements = [source_payload['regions'][0]]
    with patch('location.osm_import.download_overpass', return_value=elements):
        result = import_locations('metro', region, city)
    assert result['created'] == result['updated'] == 0


@pytest.mark.django_db
def test_city_batch_query_count_is_bounded(
    source_payload, imported_hierarchy, django_assert_max_num_queries,
):
    """Hundreds of cities require a single preload and one bulk insert."""
    region, _ = imported_hierarchy
    elements = [source_payload['regions'][0], *[
        {'type': 'node', 'id': 1000 + index, 'tags': {'place': 'city', 'name': f'Город {index}'}}
        for index in range(200)
    ]]
    with patch('location.osm_import.download_overpass', return_value=elements):
        with django_assert_max_num_queries(7):
            result = import_locations('cities', region)
    assert result['created'] == 200


@pytest.mark.parametrize('payload', [
    {'elements': [], 'remark': 'runtime error: Query timed out'},
    {'elements': 'invalid'},
    {'elements': [None]},
    {'elements': [{'id': 1, 'type': 'relation', 'members': None}]},
    {'elements': [{'id': 1, 'type': 'relation', 'tags': {'ref': 1}}]},
    [],
])
def test_partial_or_malformed_responses_are_not_accepted(payload):
    """Never use partial Overpass results as a completed source snapshot."""
    response = MagicMock()
    response.__enter__.return_value.read.return_value = json.dumps(payload).encode()
    with patch('location.osm_import.urlopen', return_value=response):
        with pytest.raises(LocationImportError, match='неполные данные'):
            download_overpass('rel(1);out tags;')


def test_download_falls_back_after_unavailable_primary():
    """Use a fixed backup and preserve timeouts and bounded reads."""
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'{"elements": []}'
    with patch(
        'location.osm_import.urlopen',
        side_effect=[URLError('unavailable'), response],
    ) as download:
        assert download_overpass('rel(1);out tags;') == []
    assert download.call_count == 2
    assert download.call_args.kwargs['timeout'] == 20
    assert download.call_args.args[0].full_url.startswith('https://overpass.private.coffee/')


def test_query_cannot_inject_overpass_from_city_names():
    """Quote external/local names as QL string literals inside Russia scope."""
    region = Region(source_identifier='relation/1')
    city = City(source_identifier='node/2', name='Город";rel["ISO3166-1"="DE"]')
    query = build_query('districts', region, city)
    assert '["ISO3166-2"~"^RU-"]' in query
    assert '\\";rel[\\"ISO3166-1\\"=\\"DE\\"]' in query
