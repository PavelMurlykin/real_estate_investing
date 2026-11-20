"""Verify open location imports, legacy adoption and atomic synchronization."""

from copy import deepcopy
from functools import partial
from unittest.mock import MagicMock, patch
from urllib.error import URLError

import pytest
from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

from location.catalog_service import lock_location_catalog
from location.tests.legacy_fixtures import canonical_legacy_location
from location.import_service import (
    IMPORT_LOCK_IDENTIFIER,
    LocationImportError,
    LocationRecord,
    import_locations,
    upsert_geography_records,
)
from location.legacy_catalog import LegacyImportScope, legacy_catalog, save_legacy_catalog_entry
from location.models import City, District, Metro, MetroLine, Region
from location.open_data import (
    CITY_CATALOG_URL,
    OpenDataError,
    OpenLocationSource,
    current_claims,
)
from location.tests.source_fixtures import load_sources, source_reply


@pytest.fixture
def sources():
    """Replace only HTTP transport while exercising the actual parsers."""
    data = load_sources()
    with patch(
        'location.open_data.OpenLocationSource.download', side_effect=partial(source_reply, data),
    ):
        yield data


@pytest.fixture
def hierarchy():
    """Create existing OSM records whose primary keys must survive replacement."""
    region = Region.objects.create(name='Москва', code='77', source_identifier='relation/102269')
    city = City.objects.create(name='Москва', region=region, source_identifier='relation/102269')
    canonical_legacy_location(city)
    return region, city


@pytest.mark.django_db
def test_regions_preserve_legacy_keys_codes_status_and_links(sources, hierarchy):
    """Replace source identities without duplicating or deleting existing data."""
    region, city = hierarchy
    region.is_active = False
    region.save()
    canonical_legacy_location(region)
    first = import_locations('regions')
    second = import_locations('regions')
    region.refresh_from_db()
    city.refresh_from_db()
    assert first['created'] == 2
    assert first['updated'] == 1
    assert first['skipped'] == 1
    assert second['created'] == second['updated'] == 0
    assert second['unchanged'] == 3
    alias = legacy_catalog('region').get(legacy_id=region.pk)
    assert alias.legacy_source_identifier == 'kladr-region/77'
    assert alias.legacy_code == '77' and not alias.legacy_is_active
    assert region.source_identifier == 'relation/102269'
    assert region.code == '77'
    assert region.is_active is False
    assert city.region_id == region.pk
    assert not legacy_catalog('region').filter(legacy_name='Берлин').exists()


@pytest.mark.django_db
def test_city_import_adopts_manual_and_osm_parents(sources, hierarchy):
    """Import children without forcing a separate parent reimport first."""
    region, city = hierarchy
    assert import_locations('cities', region)['updated'] == 1
    assert legacy_catalog('city').get(legacy_id=city.pk).legacy_source_identifier == 'fias/11111111-1111-1111-1111-111111111111'
    assert legacy_catalog('region').get(legacy_id=region.pk).legacy_source_identifier == 'kladr-region/77'
    assert import_locations('cities', region)['unchanged'] == 1
    assert legacy_catalog('city').filter(legacy_region_id=region.pk).count() == 1


@pytest.mark.django_db
def test_districts_filter_historical_units_and_keep_existing_links(sources, hierarchy):
    """Import actual urban districts and exclude obsolete and municipal units."""
    region, city = hierarchy
    existing = District.objects.create(name='Тверской', city=city, is_active=False)
    canonical_legacy_location(existing)
    first = import_locations('districts', region, city)
    repeated = import_locations('districts', region, city)
    assert first['created'] == first['updated'] == 1
    assert repeated['created'] == repeated['updated'] == 0
    alias = legacy_catalog('district').get(legacy_id=existing.pk)
    assert alias.legacy_name == 'Тверской район'
    assert alias.legacy_source_identifier == 'wikidata/Q201'
    assert alias.legacy_is_active is False
    assert legacy_catalog('district').count() == 2


@pytest.mark.django_db
def test_metro_import_and_updates_preserve_station_identity(sources, hierarchy):
    """Refresh real names and colors while retaining manual state and keys."""
    region, city = hierarchy
    line = MetroLine.objects.create(line='Сокольническая', line_color='#000000', legacy_city_id=city.pk)
    station = Metro.objects.create(station='Охотный Ряд', metro_line=line, is_active=False)
    first = import_locations('metro', region, city)
    second = import_locations('metro', region, city)
    sources['page_ids'] = {
        'Лубянка (станция метро)': 100,
        'Новое имя (станция метро)': 101,
    }
    sources['metro']['lines'][0]['stations'][0]['article'] = 'Новое имя (станция метро)'
    sources['metro']['lines'][0]['color']['fillStyle'] = 'rgba(1, 2, 3, 0.36)'
    third = import_locations('metro', region, city)
    assert first['created'] == first['updated'] == 1
    assert first['skipped'] == 2
    assert second['created'] == second['updated'] == 0
    assert third['lines']['updated'] == 1
    assert third['created'] == 0
    station.refresh_from_db()
    line.refresh_from_db()
    assert third['updated'] == 1
    assert station.station == 'Новое имя'
    assert station.is_active is False
    assert station.metro_line_id == line.pk
    assert line.line_color == '#010203'


@pytest.mark.django_db
def test_conflict_rolls_back_parent_and_line_changes(sources, hierarchy):
    """A later station conflict must undo already written parent metadata."""
    region, city = hierarchy
    line = MetroLine.objects.create(line='Сокольническая', line_color='#000000', legacy_city_id=city.pk)
    Metro.objects.create(station='Лубянка', metro_line=line, source_identifier='unknown-source')
    with pytest.raises(LocationImportError, match='Конфликт источника'):
        import_locations('metro', region, city)
    line.refresh_from_db()
    city.refresh_from_db()
    region.refresh_from_db()
    assert line.source_identifier is None
    assert line.line_color == '#000000'
    assert region.source_identifier == city.source_identifier == 'relation/102269'
    assert Metro.objects.count() == 1


@pytest.mark.django_db
def test_metro_branches_of_one_line_are_merged(sources, hierarchy):
    """Handle the Moscow 4/4A scheme without duplicating its common stations."""
    region, city = hierarchy
    branch = deepcopy(sources['metro']['lines'][0])
    branch['number'] = '1A'
    sources['metro']['lines'].append(branch)
    first = import_locations('metro', region, city)
    sources['metro']['lines'].reverse()
    repeated = import_locations('metro', region, city)
    assert first['created'] == 2
    assert first['lines']['created'] == 1
    assert repeated['created'] == repeated['updated'] == 0
    assert repeated['unchanged'] == 2
    assert repeated['lines']['unchanged'] == 1


@pytest.mark.django_db
def test_regional_metro_filters_planned_and_foreign_stations(sources):
    """Load a regional catalog and retain stable IDs when its labels change."""
    def claims(value):
        """Represent one structured Wikidata claim in the public API fixture."""
        return [{'mainsnak': {'datavalue': {'value': value}}}]

    sources['regional_pages'] = [
        {'pageid': index, 'pageprops': {'wikibase_item': identifier}}
        for index, identifier in enumerate(['Q4055814', 'Q301', 'Q302'], 1)
    ]
    station = {
        'labels': {'ru': {'value': 'Авиастроительная'}},
        'claims': {
            'P17': claims({'id': 'Q159'}), 'P81': claims({'id': 'Q2047989'}),
            'P1619': claims({'time': '+2013-05-09T00:00:00Z'}),
        },
    }
    sources['entities']['Q4055814'] = station
    sources['entities']['Q301'] = deepcopy(station)
    sources['entities']['Q301']['claims']['P1619'] = claims({
        'time': '+2099-01-01T00:00:00Z',
    })
    sources['entities']['Q302'] = deepcopy(station)
    sources['entities']['Q302']['claims']['P17'] = claims({'id': 'Q183'})
    sources['entities']['Q2047989'] = {
        'labels': {'ru': {'value': 'Центральная линия'}},
        'claims': {'P465': claims('A31E1C')},
    }
    import_locations('regions')
    region = LegacyImportScope.from_mapping(legacy_catalog('region').get(legacy_code='16'))
    import_locations('cities', region)
    city = LegacyImportScope.from_mapping(legacy_catalog('city').get(legacy_region_id=region.pk))
    first = import_locations('metro', region, city)
    repeated = import_locations('metro', region, city)
    assert first['created'] == first['lines']['created'] == 1
    assert first['skipped'] == 2  # The mapped city reuses FIAS without reloading the city catalog.
    assert repeated['created'] == repeated['updated'] == 0
    station_object = Metro.objects.get()
    station['labels']['ru']['value'] = 'Новое название'
    changed = import_locations('metro', region, city)
    assert changed['updated'] == 1
    station_object.refresh_from_db()
    assert station_object.station == 'Новое название'
    assert station_object.metro_line.line_color == '#A31E1C'


def test_incomplete_regional_station_catalog_is_rejected():
    """Do not load a paginated or interrupted station catalog as complete."""
    source = OpenLocationSource()
    with patch.object(source, 'api', return_value={
        'continue': {'cmcontinue': 'remaining'},
        'query': {'categorymembers': [{'pageid': 1}]},
    }):
        with pytest.raises(OpenDataError, match='полный'):
            source.regional_metro('Казанского')


@pytest.mark.django_db
def test_foreign_or_wrong_region_is_rejected_before_wikimedia(sources):
    """Never use names alone to put foreign cities into Russian dictionaries."""
    region = Region.objects.create(name='Берлин', code='DE')
    with pytest.raises(LocationImportError, match='России'):
        import_locations('cities', region)
    assert not legacy_catalog('city').exists()


@pytest.mark.django_db
def test_city_country_and_type_are_verified(sources, hierarchy):
    """Do not mistake a similarly named ship or foreign city for a city."""
    region, city = hierarchy
    country = sources['entities']['Q649']['claims']['P17'][0]['mainsnak']['datavalue']
    country['value']['id'] = 'Q183'
    with pytest.raises(LocationImportError, match='российский город'):
        import_locations('districts', region, city)
    assert not legacy_catalog('district').exists()


@pytest.mark.django_db(transaction=True)
def test_simultaneous_import_is_rejected_before_network():
    """Prevent parallel source requests across real PostgreSQL sessions."""
    other = connection.copy(alias='location-import-lock')
    try:
        with other.cursor() as cursor:
            cursor.execute('SELECT pg_advisory_lock(%s)', [IMPORT_LOCK_IDENTIFIER])
        with patch('location.open_data.OpenLocationSource.download') as download:
            with pytest.raises(LocationImportError, match='Другой импорт'):
                import_locations('regions')
        download.assert_not_called()
    finally:
        other.close()


@pytest.mark.django_db
def test_import_guard_is_released_after_failure(sources):
    """An upstream failure must leave later imports usable."""
    with patch(
        'location.open_data.OpenLocationSource.city_catalog',
        side_effect=OpenDataError('Недоступен'),
    ):
        with pytest.raises(LocationImportError):
            import_locations('regions')
    assert import_locations('regions')['created'] == 3


def test_transport_retries_transient_failure_and_bounds_response():
    """Retry once with backoff while bounding source memory and socket time."""
    response = MagicMock()
    response.__enter__.return_value.read.return_value = b'public data'
    with patch(
        'location.open_data.urlopen', side_effect=[URLError('temporary'), response],
    ) as download:
        with patch('location.open_data.time.sleep') as backoff:
            assert OpenLocationSource().download(CITY_CATALOG_URL) == 'public data'
    assert download.call_count == 2
    assert download.call_args.kwargs['timeout'] <= 8
    backoff.assert_called_once_with(0.5)


def test_transport_rejects_arbitrary_urls():
    """Reject SSRF input before opening an HTTP connection."""
    with patch('location.open_data.urlopen') as download:
        with pytest.raises(OpenDataError, match='Недопустимый источник'):
            OpenLocationSource().download('http://127.0.0.1/private')
    download.assert_not_called()


def test_city_names_use_settlement_and_city_area_before_region():
    """Keep Alupka distinct from Yalta and read cities encoded as areas."""
    source = OpenLocationSource()
    catalog = (
        'country,region_type,region,area_type,area,city,settlement,kladr_id,fias_id\n'
        'Россия,Респ,Крым,,,Ялта,Алупка,9100000800100,'
        'daa6815b-0cf0-44c7-981c-84d72d51f2b1\n'
        'Россия,обл,Московская,г,Дмитров,,,5004500000000,'
        '0d8a246f-6446-403e-91c6-3aec9cdbfc32\n'
    )
    with patch.object(source, 'download', return_value=catalog):
        assert [row['city_name'] for row in source.city_catalog()] == ['Алупка', 'Дмитров']


def test_region_type_is_not_duplicated_in_extended_names():
    """Keep official extended names from receiving a second type suffix."""
    source = OpenLocationSource()
    catalog = (
        'country,region_type,region,city,kladr_id,fias_id\n'
        'Россия,обл,Кемеровская область - Кузбасс,Кемерово,4200000900000,'
        'a5b44f7f-4ae6-400d-bc51-160d1843403a\n'
        'Россия,Респ,Чувашская Республика - Чувашия,Чебоксары,2100000100000,'
        'dd8caeab-c685-4f2a-bf5f-550aca1bbc48\n'
    )
    with patch.object(source, 'download', return_value=catalog):
        assert [row['region_name'] for row in source.city_catalog()] == [
            'Кемеровская область - Кузбасс', 'Чувашская Республика - Чувашия',
        ]


def test_bulk_city_resolution_reuses_verified_candidates():
    """Prime a redirected article and avoid an extra per-city search."""
    source = OpenLocationSource()
    data = load_sources()
    with patch.object(source, 'download', side_effect=partial(source_reply, data)):
        row = next(row for row in source.city_catalog() if row['city_name'] == 'Москва')
    with patch.object(source, 'api', return_value={'query': {
        'redirects': [{'from': 'Москва', 'to': 'Москва (город)'}],
        'pages': [{'title': 'Москва (город)', 'pageprops': {'wikibase_item': 'Q649'}}],
    }}):
        with patch.object(source, 'get_entities', return_value={}):
            source.prime_cities([row])
    source.entities = data['entities']
    with patch.object(source, 'api') as external_api:
        assert source.resolve_city(row)['id'] == 'Q649'
    external_api.assert_not_called()


@pytest.mark.parametrize('payload', ['[]', '{"error":{"code":"maxlag"}}', 'not json'])
def test_api_errors_or_malformed_payloads_are_not_imported(payload):
    """Do not interpret empty or failed API envelopes as successful catalogs."""
    source = OpenLocationSource()
    with patch.object(source, 'download', return_value=payload):
        with pytest.raises(OpenDataError):
            source.api(CITY_CATALOG_URL, {})


def test_ended_and_future_claims_are_excluded():
    """Avoid importing previous administrative structures as current ones."""
    entity = {'claims': {'P150': [
        {'mainsnak': {'datavalue': {'value': 'active'}}},
        {'mainsnak': {'datavalue': {'value': 'ended'}}, 'qualifiers': {
            'P582': [{'datavalue': {'value': {'time': '+2000-01-01T00:00:00Z'}}}],
        }},
        {'mainsnak': {'datavalue': {'value': 'future'}}, 'qualifiers': {
            'P580': [{'datavalue': {'value': {'time': '+2099-01-01T00:00:00Z'}}}],
        }},
    ]}}
    assert current_claims(entity, 'P150') == ['active']


@pytest.mark.django_db
def test_city_loading_uses_bulk_queries(django_assert_num_queries):
    """Keep database query counts independent of city batch size."""
    region = save_legacy_catalog_entry('region', {'name': 'Москва', 'code': '77'})
    records = [
        LocationRecord(f'fias/{index}', f'Город {index}')
        for index in range(200)
    ]
    with transaction.atomic():
        lock_location_catalog()
        with CaptureQueriesContext(connection) as queries:
            _, first = upsert_geography_records('city', records, parent=region)
    assert len(queries) <= 15
    with django_assert_num_queries(1):
        _, repeated = upsert_geography_records('city', records, parent=region)
    assert first['created'] == 200
    assert repeated['unchanged'] == 200


@pytest.mark.parametrize('entities', [{}, {'Q159': None}, {'Q159': {'missing': ''}}])
def test_partial_entities_are_rejected(entities):
    """Never accept missing requested entities as an empty successful import."""
    source = OpenLocationSource()
    with patch.object(source, 'api', return_value={'entities': entities}):
        with pytest.raises(OpenDataError, match='неполный'):
            source.get_entities(['Q159'])


def test_station_redirects_keep_stable_page_identifiers():
    """A renamed Wikipedia article keeps the imported station identity."""
    source = OpenLocationSource()
    with patch.object(source, 'api', return_value={'query': {
        'normalized': [{'from': 'old name', 'to': 'Old name'}],
        'redirects': [{'from': 'Old name', 'to': 'New name'}],
        'pages': [{'pageid': 123, 'title': 'New name'}],
    }}):
        assert source.station_pages(['old name'])['old name']['pageid'] == 123
