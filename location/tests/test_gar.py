"""Exercise official XML extraction, stable identities and resumable loading."""

import io
import zipfile
from importlib import import_module
from types import SimpleNamespace
from unittest.mock import patch

import pytest
from django.apps import apps
from django.db import connection

from location.gar_source import GarSource, GarSourceError
from location.gar_source import validate_source_url
from location.gar_import import load_region
from location.jobs import run_import_job, start_import_job
from location.migration_support import backfill_locations
from location.models import (
    City, District, LegacyLocationMapping, Location, LocationClosure,
    LocationIdentifier, LocationType, MetroSystem, Region,
)


SPB = [
    {'id': '1', 'guid': 'c2deb16a-0330-4f05-821f-1d09c93331e6', 'name': 'Санкт-Петербург', 'level': '1', 'type': 'г.', 'typeName': 'Город', 'path': ['1'], 'parent': None, 'region': '1'},
    {'id': '2', 'guid': '110d6ad9-0b64-47cf-a2ee-7e935228799c', 'name': 'Пушкин', 'level': '5', 'type': 'г.', 'typeName': 'Город', 'path': ['1', '2'], 'parent': '1', 'region': '1'},
    {'id': '3', 'guid': '3eece910-1326-4602-aa21-e4ee117275ad', 'name': 'Стрельна', 'level': '6', 'type': 'п.', 'typeName': 'Поселок', 'path': ['1', '3'], 'parent': '1', 'region': '1'},
]


@pytest.mark.parametrize('url', ['http://fias.nalog.ru/test', 'https://localhost/test',
                              'https://fias-file.nalog.ru:444/test', 'https://u:p@fias.nalog.ru/test'])
def test_rejects_non_official_downloads_and_redirects(url):
    """Never allow a stored source or redirect to access arbitrary networks."""
    with pytest.raises(GarSourceError):
        validate_source_url(url)


class MemoryArchive(io.BytesIO):
    """Serve the exact compressed ZIP member bytes without network calls."""

    def open_range(self, start, size):
        return io.BytesIO(self.getvalue()[start:start + size])


def archive_bytes(rows, missing_parent=False):
    """Build real deflated XML fixtures in the official file layout."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED) as archive:
        archive.writestr('AS_ADDR_OBJ_TYPES_20261113.XML', '<TYPES><ADDRESSOBJECTTYPE LEVEL="6" NAME="Поселок" SHORTNAME="п." /></TYPES>')
        objects = ''.join(f'<OBJECT OBJECTID="{row["id"]}" OBJECTGUID="{row["guid"]}" NAME="{row["name"]}" TYPENAME="{row["type"]}" LEVEL="{row["level"]}" ISACTUAL="1" ISACTIVE="1" />' for row in rows)
        hierarchy = ''.join(f'<ITEM OBJECTID="{row["id"]}" PATH="{".".join(row["path"])}" ISACTIVE="1" />' for row in rows if not missing_parent or row['id'] != '3')
        archive.writestr('78/AS_ADDR_OBJ_20261113.XML', f'<ADDRESSOBJECTS>{objects}</ADDRESSOBJECTS>')
        archive.writestr('78/AS_ADM_HIERARCHY_20261113.XML', f'<ITEMS>{hierarchy}</ITEMS>')
    return output.getvalue()


def test_extracts_official_types_paths_and_validates_complete_hierarchy(tmp_path):
    """Include settlements as well as cities and reuse only complete extracts."""
    with patch('location.gar_source.RemoteArchive', return_value=MemoryArchive(archive_bytes(SPB))):
        source = GarSource('20261113', 'unused', tmp_path)
        assert source.regions() == ['78']
        rows = source.extract_region('78')
        assert {row['name'] for row in rows} == {'Санкт-Петербург', 'Пушкин', 'Стрельна'}
        assert rows[-1]['typeName'] == 'Поселок'
        with patch.object(source, 'chunks', side_effect=AssertionError('Should use verified cache')):
            assert source.extract_region('78') == rows
    with patch('location.gar_source.RemoteArchive', return_value=MemoryArchive(archive_bytes(SPB, True))):
        with pytest.raises(GarSourceError, match='Неполная'):
            GarSource('20261114', 'unused', tmp_path).extract_region('78')
    assert not (tmp_path / '20261114' / '78.json').exists()


def test_rejects_corrupt_cached_member(tmp_path):
    """CRC checks reject a cache member even when its compressed length matches."""
    with patch('location.gar_source.RemoteArchive', return_value=MemoryArchive(archive_bytes(SPB))):
        source = GarSource('20261113', 'unused', tmp_path)
        member = source.member('78/AS_ADDR_OBJ_')
        list(source.chunks(member))
        path = source.directory / (member.filename.replace('/', '_') + '.deflate')
        data = bytearray(path.read_bytes())
        data[len(data) // 2] ^= 64
        path.write_bytes(data)
        with pytest.raises(GarSourceError):
            list(source.chunks(member))
        assert not path.exists()


@pytest.mark.django_db
def test_preserves_district_ids_and_imports_pushkin_strelna_idempotently():
    """Retain federal roles and existing administrative districts on both runs."""
    region = Region.objects.create(name='Санкт-Петербург', code='78')
    city = City.objects.create(name='Санкт-Петербург', region=region)
    districts = [District.objects.create(name=f'{name} район', city=city) for name in ('Пушкинский', 'Петродворцовый')]
    backfill_locations(apps)
    before = dict(LegacyLocationMapping.objects.filter(model_name='district').values_list('legacy_id', 'location_id'))
    first = load_region(SPB, '78', '20261113')
    pushkin = Location.objects.get(name='Пушкин')
    strelna = Location.objects.get(name='Стрельна')
    assert pushkin.parent_id == before[districts[0].pk]
    assert strelna.parent_id == before[districts[1].pk]
    assert first['cities']['created'] == 2
    assert LocationClosure.objects.filter(ancestor_id=before[districts[0].pk], descendant=pushkin, depth=1).exists()
    assert LegacyLocationMapping.objects.get(model_name='city', legacy_id=city.pk).location_id == pushkin.region_id
    second = load_region(SPB, '78', '20261113')
    assert all(counts['created'] == counts['updated'] == 0 for counts in second.values())
    assert City.objects.count() == 1 and District.objects.count() == 2
    assert dict(LegacyLocationMapping.objects.filter(model_name='district').values_list('legacy_id', 'location_id')) == before
    assert LocationIdentifier.objects.get(provider='fias', value=SPB[1]['guid']).location_id == pushkin.pk


@pytest.mark.django_db
def test_fresh_catalog_creates_overrides_on_first_run():
    """A clean database must have the same hierarchy as an upgraded database."""
    load_region(SPB, '78', '20261113')
    assert Location.objects.get(name='Стрельна').parent.name == 'Петродворцовый район'
    second = load_region(SPB, '78', '20261113')
    assert all(counts['created'] == counts['updated'] == 0 for counts in second.values())


@pytest.mark.django_db
def test_rename_keeps_guid_district_and_search_alias():
    """Stable FIAS IDs keep administrative overlays correct after a rename."""
    load_region(SPB, '78', '20261113')
    previous = Location.objects.get(name='Пушкин')
    changed = [dict(row) for row in SPB]
    changed[1]['name'] = 'Пушкин новое название'
    result = load_region(changed, '78', '20261114')
    previous.refresh_from_db()
    assert previous.name == changed[1]['name']
    assert previous.parent.name == 'Пушкинский район'
    assert previous.aliases.filter(name='Пушкин').exists()
    assert result['cities']['created'] == 0


@pytest.mark.django_db
def test_audited_gar_city_keeps_its_identity_in_migration_and_repeat_import(client):
    """Correct the direct city role while retaining old search, IDs and metro links."""
    root = dict(SPB[0], id='807356', guid='29251dcf-00a1-4e34-98d4-5c47484a36d4',
                name='Московская', type='обл.', typeName='Область', path=['807356'])
    town = dict(SPB[1], id='862378', guid='6ae8ad9e-aa6c-4849-92d8-8e637059c9b0',
                name='Одинцово', level='2', path=['807356', '862378'], parent=root['id'])
    namesake = dict(town, id='862377', guid='namesake', level='5', path=['807356', '862377'])
    region = Region.objects.create(name='Московская область', code='50')
    city = City.objects.create(name='Одинцово', region=region, source_identifier=f'fias/{town["guid"]}')
    backfill_locations(apps)
    counts = load_region([root, town, namesake], '50', '20261113')
    previous = LocationIdentifier.objects.get(provider='fias', value=town['guid']).location
    other = LocationIdentifier.objects.get(provider='fias', value=namesake['guid']).location
    assert previous.pk != other.pk
    assert counts['districts']['created'] == 0
    legacy_type = LocationType.objects.create(
        code='gar:2:г.', name='Город', abbreviation='г.', category='district',
    )
    Location.objects.filter(pk=previous.pk).update(location_type=legacy_type)
    Location.objects.filter(pk=other.pk).update(location_type=legacy_type)
    system = MetroSystem.objects.create(name='Тестовая система', location=previous)
    migration = import_module('location.migrations.0012_reconcile_gar_city_and_district_roles')
    migration.reconcile_gar_geography(apps, SimpleNamespace(connection=connection))
    migration.reconcile_gar_geography(apps, SimpleNamespace(connection=connection))
    previous.refresh_from_db()
    other.refresh_from_db()
    assert previous.location_type.category == 'locality'
    assert other.location_type_id == legacy_type.pk
    assert previous.parent_id == previous.region_id == other.region_id
    assert LegacyLocationMapping.objects.get(model_name='city', legacy_id=city.pk).location_id == previous.pk
    assert MetroSystem.objects.get(pk=system.pk).location_id == previous.pk
    assert LocationClosure.objects.filter(ancestor_id=previous.region_id, descendant=previous, depth=1).exists()
    for _ in range(2):
        load_region([root, town, namesake], '50', '20261113')
        assert LocationIdentifier.objects.get(provider='gar', value=town['id']).location_id == previous.pk
    previous.refresh_from_db()
    assert previous.location_type.category == 'locality'
    assert client.get(f'/api/v1/location-dictionaries/cities/{city.pk}/').json()['name'] == 'Одинцово'
    assert client.get(f'/api/v1/location-catalogs/localities/{city.pk}/?legacy=1').json()['id'] == previous.pk


@pytest.mark.django_db
def test_administrative_review_retains_district_identity_and_suburbs(client):
    """Confirm only the evidenced district under the exact federal city."""
    region = Region.objects.create(name='Санкт-Петербург', code='78')
    city = City.objects.create(name=region.name, region=region)
    pushkin_district = District.objects.create(
        name='Пушкинский район', city=city, source_identifier='wikidata/Q220316',
    )
    petrodvorets_district = District.objects.create(
        name='Петродворцовый район', city=city, source_identifier='wikidata/Q270114',
    )
    unresolved = District.objects.create(name='Прежний округ', city=city)
    backfill_locations(apps)
    mappings = dict(LegacyLocationMapping.objects.filter(
        model_name='district',
    ).values_list('legacy_id', 'location_id'))
    for attempt in range(2):
        counts = load_region(SPB, '78', '20261113')
        assert counts['districts']['updated'] == (2 if attempt == 0 else 0)
    for district, suburb in [(pushkin_district, 'Пушкин'), (petrodvorets_district, 'Стрельна')]:
        district_location = Location.objects.get(pk=mappings[district.pk])
        assert not district_location.needs_review
        assert district_location.source_status == 'verified'
        assert district_location.source_version.startswith('administrative:')
        assert Location.objects.get(name=suburb).parent_id == district_location.pk
        assert client.get(f'/api/v1/location-dictionaries/districts/{district.pk}/').json()['name'] == district.name
        resolved = client.get(f'/api/v1/location-catalogs/districts/{district.pk}/?legacy=1').json()
        assert resolved['id'] == district_location.pk
    assert Location.objects.get(pk=mappings[unresolved.pk]).needs_review


@pytest.mark.django_db
def test_homonymous_villages_remain_distinct_and_cycle_rolls_back():
    """Names alone never merge settlements from different administrative paths."""
    rows = [dict(SPB[0], id='1', guid='root', name='Тестовый', type='обл.', typeName='Область')]
    for identifier, parent, level, name in [
        ('2', '1', '2', 'Первый'), ('3', '1', '2', 'Второй'),
        ('4', '2', '6', 'Дубровка'), ('5', '3', '6', 'Дубровка'),
    ]:
        rows.append(dict(SPB[2], id=identifier, guid=f'fixture-{identifier}',
                         parent=parent, level=level, name=name,
                         type='р-н' if level == '2' else 'д.',
                         typeName='Район' if level == '2' else 'Деревня'))
    load_region(rows, '01', '20261113')
    villages = Location.objects.filter(name='Дубровка')
    assert villages.count() == 2
    assert len(set(villages.values_list('parent_id', flat=True))) == 2
    repeated = load_region(rows, '01', '20261113')
    assert all(counts['created'] == counts['updated'] == 0 for counts in repeated.values())
    rows[0]['name'] = 'Не должно сохраниться'
    rows[-1]['parent'] = rows[-1]['id']
    with pytest.raises(ValueError, match='cycle'):
        load_region(rows, '01', '20261114')
    assert not Location.objects.filter(name='Не должно сохраниться').exists()


@pytest.mark.django_db
def test_job_resumes_regions_and_pins_source_version(tmp_path, settings):
    """A failed region leaves its cursor unchanged and retry uses one snapshot."""
    settings.GAR_CACHE_DIRECTORY = tmp_path
    with patch('location.jobs.latest_snapshot', return_value=('20261113', 'https://fias-file.nalog.ru/test.zip')), patch('location.jobs.GarSource') as factory:
        source = factory.return_value
        source.regions.return_value = ['78', '01']
        source.extract_region.side_effect = [SPB, GarSourceError('Повторите')]
        job = start_import_job()
        run_import_job(job)
        job.refresh_from_db()
        assert job.status == 'failed' and job.processed_regions == 1
        assert start_import_job().pk == job.pk
        source.extract_region.side_effect = None
        source.extract_region.return_value = []
        with patch('location.jobs.latest_snapshot', side_effect=AssertionError('Snapshot already pinned')):
            run_import_job(job)
        job.refresh_from_db()
        assert job.status == 'completed' and job.processed_regions == 2
        assert job.coverage['retiredRegions'] == ['01']
