"""Verify canonical and legacy JSON imports without changing existing identities."""

import json
from copy import deepcopy
from decimal import Decimal
from importlib import import_module
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.apps import apps
from django.core.files.uploadedfile import SimpleUploadedFile
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.exceptions import ValidationError

from api_v1.test_complex_import_photos import import_payload, image_content  # noqa: F401
from api_v1.test_complex_localities import locality_catalog, complex_catalog, import_user  # noqa: F401
from api_v1.test_customer_calculations import create_customer_calculations
from api_v1.test_real_estate_complexes import create_catalog_manager
from bank.models import MortgageProgram, MortgageProgramRegionalCreditLimit
from core.json_import import JsonImportError
from customer.models import Customer, CustomerCalculation, CustomerTrenchCalculation
from location.gar_import import load_region
from location.migration_support import backfill_locations
from location.models import City, District, Location, LocationAlias, LocationIdentifier, Metro, MetroLine, MetroSystem, Region
from mortgage.models import MortgageCalculation
from property.complex_import import import_complex_catalog
from property.complex_photos import add_complex_photos
from property.location_context import set_primary_location
from property.models import (
    ApartmentDecoration, ApartmentLayout, Property, RealEstateComplex,
    RealEstateComplexBuilding, RealEstateComplexLocation,
)
from trench_mortgage.models import TrenchMortgageCalculation
from users.roles import APPLICATION_ADMINISTRATOR_GROUP_NAME, MODERATOR_GROUP_NAME


@pytest.fixture
def import_geography(locality_catalog):
    """Use official Pushkin/Strelna identifiers and a network centered in Petersburg."""
    center = Location.objects.get(name='Санкт-Петербург', location_type__category='region')
    locality_catalog['metro'].refresh_from_db()
    system = locality_catalog['metro'].metro_line.system
    system.location = center
    system.save()
    return locality_catalog


def canonical_payload(payload, locality='Пушкин'):
    """Convert the existing portable business fields to explicit FIAS geography."""
    result = deepcopy(payload)
    result['version'] = 2
    row = result['complexes'][0]
    for field in ('region_code', 'region', 'city', 'district', 'match_city'):
        row.pop(field, None)
    row.update(name='Канонический импорт', key='canonical:suburb')
    row['location'] = {'fias_id': LocationIdentifier.objects.get(
        location__name=locality, provider='fias',
    ).value}
    row['metro'] = []
    return result


def catalog_counts():
    """Detect accidental duplicate legacy or canonical dictionaries."""
    return {model._meta.label: model.objects.count()
            for model in (Region, City, District, Location, LocationIdentifier, MetroSystem, MetroLine, Metro)}


def json_import_account(role):
    """Create distinct accounts alongside the shared locality fixture's moderator."""
    roles = ('anonymous', 'regular', 'staff', 'moderator', 'administrator', 'superuser')
    if role == 'anonymous':
        return None
    user = get_user_model().objects.create_user(
        email=f'{role}@complex-json.invalid', phone_number=f'+7999333000{roles.index(role)}',
        password='json-import-test-password', is_staff=role == 'staff', is_superuser=role == 'superuser',
    )
    group_name = {'moderator': MODERATOR_GROUP_NAME, 'administrator': APPLICATION_ADMINISTRATOR_GROUP_NAME}.get(role)
    if group_name:
        group, _ = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    return user


@pytest.mark.django_db
@pytest.mark.parametrize('locality', ['Пушкин', 'Стрельна'])
@pytest.mark.parametrize('version', [1, 2])
def test_import_and_repeat_in_suburbs(import_payload, import_geography, settings, tmp_path, locality, version):
    """Import either format in a town absent from the old City table."""
    settings.MEDIA_ROOT = tmp_path
    payload = canonical_payload(import_payload, locality)
    row = payload['complexes'][0]
    station = import_geography['metro']
    row['metro'] = [{'station_id': station.pk, 'mode': 'Пешком', 'minutes': 20}]
    if version == 1:
        payload['version'] = 1
        row.pop('location')
        row.update(region_code='78', region='Санкт-Петербург', city=locality,
                   district='Пушкинский район' if locality == 'Пушкин' else 'Петродворцовый район')
        row['metro'] = deepcopy(import_payload['complexes'][0]['metro'])
    before = catalog_counts()
    first = import_complex_catalog(payload)
    complex_object = RealEstateComplex.objects.get(source_key=row['key'])
    original = (complex_object.pk, complex_object.realestatecomplexbuilding_set.get().pk,
                complex_object.metro_availability.get().pk, complex_object.photos.get().pk)
    second = import_complex_catalog(payload)
    complex_object.refresh_from_db()
    assert first['created'] == 1 and second['created'] == second['photos'] == 0
    assert complex_object.district_id is None and complex_object.primary_location.name == locality
    assert original == (complex_object.pk, complex_object.realestatecomplexbuilding_set.get().pk,
                        complex_object.metro_availability.get().pk, complex_object.photos.get().pk)
    assert complex_object.metro_availability.get().metro_id == station.pk
    assert before == catalog_counts()
    assert not City.objects.filter(name=locality).exists()


@pytest.mark.django_db
def test_move_retains_building_territory_properties_calculations_and_gallery(
    client, import_payload, import_geography, settings, tmp_path,
):
    """Move a complex to Strelna, keeping existing buildings, financial rows and memberships."""
    settings.MEDIA_ROOT = tmp_path
    payload = canonical_payload(import_payload)
    station = import_geography['metro']
    payload['complexes'][0]['metro'] = [{'station_id': station.pk, 'mode': 'Пешком', 'minutes': 20}]
    import_complex_catalog(payload)
    complex_object = RealEstateComplex.objects.get(source_key='canonical:suburb')
    building = complex_object.realestatecomplexbuilding_set.get()
    original_territory = complex_object.location_links.get(is_primary=True)
    building.complex_location = original_territory
    building.save()
    omitted = RealEstateComplexBuilding.objects.create(real_estate_complex=complex_object, number='2')
    photos = add_complex_photos(complex_object, [SimpleUploadedFile('blue.jpg', image_content('blue'))], primary_index=0)
    complex_object.refresh_from_db()
    photo_name = complex_object.photo.name
    photo_rows = list(complex_object.photos.order_by('pk').values())
    property_object = Property.objects.create(building=building, apartment_number='7', area='45', floor=3,
        property_cost='8000000', decoration=ApartmentDecoration.objects.create(name='Без отделки'),
        layout=ApartmentLayout.objects.create(name='Студия'))
    user = create_catalog_manager()
    client.force_login(user)
    customer = Customer.objects.create(user=user, first_name='Импорт', desired_city=import_geography['city'])
    program = MortgageProgram.objects.create(name='Региональная', is_preferential=True, credit_limit=6000000)
    MortgageProgramRegionalCreditLimit.objects.create(mortgage_program=program,
        region=import_geography['region'], credit_limit=12000000)
    customer.preferential_programs.add(program)
    market, trench = create_customer_calculations(client, customer, property_object)
    protected = [(model, model.objects.values().get(pk=identifier)) for model, identifier in (
        (Property, property_object.pk), (Customer, customer.pk),
        (MortgageCalculation, market), (TrenchMortgageCalculation, trench),
    )]
    previous_limit = customer.get_preferential_credit_limit()
    station_rows = list(Metro.objects.order_by('pk').values())
    availability = complex_object.metro_availability.get()
    availability.is_active = False
    availability.save()
    next_payload = canonical_payload(import_payload, 'Стрельна')
    next_payload['complexes'][0]['photos'] = []
    next_payload['complexes'][0]['metro'] = []
    for _ in range(2):
        import_complex_catalog(next_payload)
    complex_object.refresh_from_db()
    building.refresh_from_db()
    assert complex_object.primary_location.name == 'Стрельна'
    assert building.pk == property_object.building_id and building.complex_location_id == original_territory.pk
    assert building.geography.city == 'Пушкин'
    assert complex_object.realestatecomplexbuilding_set.filter(pk=omitted.pk).exists()
    assert complex_object.photo.name == photo_name
    assert list(complex_object.photos.order_by('pk').values()) == photo_rows
    assert photos[0].image.storage.exists(photos[0].image.name)
    assert complex_object.metro_availability.get().pk == availability.pk
    assert not complex_object.metro_availability.get().is_active
    assert list(Metro.objects.order_by('pk').values()) == station_rows
    for model, snapshot in protected:
        assert model.objects.values().get(pk=snapshot['id']) == snapshot
    assert CustomerCalculation.objects.filter(customer=customer, calculation_id=market).exists()
    assert CustomerTrenchCalculation.objects.filter(customer=customer, calculation_id=trench).exists()
    assert customer.get_preferential_credit_limit() == previous_limit == Decimal('12000000')


@pytest.mark.django_db
def test_old_file_keeps_confirmed_suburb(import_payload, import_geography, settings, tmp_path):
    """A coarse Petersburg/district pair must not replace confirmed Strelna."""
    settings.MEDIA_ROOT = tmp_path
    existing = import_geography['complex']
    set_primary_location(existing, Location.objects.get(name='Стрельна'))
    row = import_payload['complexes'][0]
    row.update(region_code='78', region='Санкт-Петербург', city='Санкт-Петербург', district='Петродворцовый район')
    first = import_complex_catalog(import_payload)
    second = import_complex_catalog(import_payload)
    existing.refresh_from_db()
    assert first['created'] == second['created'] == 0
    assert existing.primary_location.name == 'Стрельна'
    assert existing.district_id == import_geography['district'].pk


@pytest.mark.django_db
def test_mys_migration_and_legacy_import_preserve_likino(
    import_payload, complex_catalog, settings, tmp_path, client,
):
    """Refine the retained district link by GAR and preserve it on legacy reimport."""
    settings.MEDIA_ROOT = tmp_path
    region = complex_catalog['region']
    region.name, region.code = 'Московская область', '50'
    region.save(update_fields=['name', 'code'])
    city = complex_catalog['city']
    city.name = 'Одинцово'
    city.save(update_fields=['name'])
    district = complex_catalog['district']
    district.name = 'Одинцовский городской округ'
    district.save(update_fields=['name'])
    original = complex_catalog['complex']
    original.name, original.source_key = 'Мыс', 'ru:complex:mys'
    original.save(update_fields=['name', 'source_key'])
    legacy_location = original.location_links.get(is_primary=True).location
    Location.objects.filter(pk=legacy_location.pk).update(name=district.name)
    Location.objects.filter(pk=legacy_location.parent_id).update(name=city.name)
    records = [
        {
            'id': '807356', 'guid': '29251dcf-00a1-4e34-98d4-5c47484a36d4',
            'name': region.name, 'level': '1', 'type': 'обл.', 'typeName': 'Область',
            'parent': None,
        },
        {
            'id': '862378', 'guid': '6ae8ad9e-aa6c-4849-92d8-8e637059c9b0',
            'name': city.name, 'level': '2', 'type': 'г.', 'typeName': 'Город',
            'parent': '807356',
        },
        {
            'id': '868510', 'guid': 'f45a3692-93c0-42d2-807a-80112e346a13',
            'name': 'Ликино', 'level': '6', 'type': 'д.', 'typeName': 'Деревня',
            'parent': '862378',
        },
    ]
    load_region(records, '50', '20261113')
    locality = LocationIdentifier.objects.get(provider='gar', value='868510').location
    row = import_payload['complexes'][0]
    row.update(key=original.source_key, name=original.name, region_code=region.code,
               region=region.name, city=city.name, district=district.name)
    import_complex_catalog(import_payload)
    old_link = original.location_links.get(is_primary=True)
    old_complex = RealEstateComplex.objects.values().get(pk=original.pk)
    old_building = original.realestatecomplexbuilding_set.values().get()
    old_metro_id = original.metro_availability.get().pk
    migration = import_module('property.migrations.0021_refine_mys_location')
    for _ in range(2):
        migration.refine_mys_location(apps, SimpleNamespace(connection=connection))
    old_link.refresh_from_db()
    assert old_link.is_historical and not old_link.is_primary
    assert RealEstateComplex.objects.values().get(pk=original.pk) == old_complex
    assert original.realestatecomplexbuilding_set.values().get() == old_building
    assert original.location_links.get(is_primary=True).location_id == locality.pk
    for _ in range(2):
        result = import_complex_catalog(import_payload)
        assert result['created'] == result['photos'] == 0
    assert original.location_links.count() == 2
    assert original.location_links.get(is_primary=True).location_id == locality.pk
    assert original.metro_availability.get().pk == old_metro_id
    detail = client.get(f'/api/v1/complexes/{original.pk}/').json()
    assert detail['districtId'] == district.pk
    assert detail['localityId'] == locality.pk
    assert detail['city'] == 'Ликино'

    unrelated = District.objects.create(name='Другой район', city=city)
    backfill_locations(apps)
    row['district'] = unrelated.name
    with pytest.raises(JsonImportError, match='противоречит'):
        import_complex_catalog(import_payload)
    assert original.location_links.get(is_primary=True).location_id == locality.pk


@pytest.mark.django_db
def test_natural_metro_uses_network_and_adds_no_old_city(import_payload, import_geography, settings, tmp_path):
    """Create a line and station in the Petersburg system, not in Pushkin."""
    settings.MEDIA_ROOT = tmp_path
    payload = canonical_payload(import_payload)
    center = Location.objects.get(name='Санкт-Петербург', location_type__category='region')
    payload['complexes'][0]['metro'] = [{
        'station': 'Новая импортная', 'line': 'Новая линия', 'color': '#123456',
        'system_location': {'id': center.pk}, 'mode': 'На транспорте', 'minutes': 30,
    }]
    old_counts = (City.objects.count(), District.objects.count(), Region.objects.count())
    import_complex_catalog(payload)
    import_complex_catalog(payload)
    station = Metro.objects.get(station='Новая импортная')
    assert station.metro_line.system_id == import_geography['metro'].metro_line.system_id
    assert station.metro_line.city_id is None and station.location_id is None
    assert station.lines.filter(pk=station.metro_line_id).exists()
    assert old_counts == (City.objects.count(), District.objects.count(), Region.objects.count())


@pytest.mark.django_db
@pytest.mark.parametrize('reference', [
    {'id': 9999999}, {'fias_id': str(uuid4())},
    {'id': 1, 'fias_id': str(uuid4())}, {'id': 1, 'fiasId': str(uuid4())}, {},
])
def test_invalid_reference_is_atomic(import_payload, import_geography, reference, settings, tmp_path):
    """A later bad record rolls back preceding rows and photos."""
    settings.MEDIA_ROOT = tmp_path
    payload = canonical_payload(import_payload)
    bad = deepcopy(payload['complexes'][0])
    bad.update(key='invalid:reference', name='Не сохранять', location=reference)
    payload['complexes'].append(bad)
    original = list(RealEstateComplex.objects.order_by('pk').values())
    with pytest.raises((JsonImportError, ValidationError)):
        import_complex_catalog(payload)
    assert list(RealEstateComplex.objects.order_by('pk').values()) == original
    assert not list(tmp_path.rglob('*.jpg'))


@pytest.mark.django_db
def test_v2_api_import_and_csrf(client, import_payload, import_geography, settings, tmp_path):
    """Run both imports through multipart API with the original administrator role."""
    settings.MEDIA_ROOT = tmp_path
    payload = canonical_payload(import_payload, 'Стрельна')
    client.force_login(json_import_account('administrator'))
    for _ in range(2):
        reply = client.post('/api/v1/complexes/import/', {'file': SimpleUploadedFile(
            'complexes.json', json.dumps(payload).encode(), 'application/json',
        )})
        assert reply.status_code == 200, reply.content
    secure = Client(enforce_csrf_checks=True)
    secure.force_login(json_import_account('superuser'))
    assert secure.post('/api/v1/complexes/import/').status_code == 403


@pytest.mark.django_db
def test_import_lookup_is_bounded(import_payload, import_geography, settings, tmp_path):
    """A large locality catalog does not introduce per-locality queries."""
    settings.MEDIA_ROOT = tmp_path
    payload = canonical_payload(import_payload)
    payload['complexes'][0]['photos'] = []
    template = Location.objects.get(name='Пушкин')
    Location.objects.bulk_create([Location(name=f'Однофамильный {number}', location_type=template.location_type,
        parent=template.parent, region=template.region) for number in range(1000)])
    with CaptureQueriesContext(connection) as queries:
        import_complex_catalog(payload)
    assert len(queries) <= 50


@pytest.mark.django_db
def test_ambiguous_locality_requires_explicit_fias(import_payload, import_geography, settings, tmp_path):
    """Never merge homonymous localities by their display name."""
    settings.MEDIA_ROOT = tmp_path
    locality = Location.objects.get(name='Пушкин')
    Location.objects.create(name=locality.name, location_type=locality.location_type,
                            parent=locality.parent, region=locality.region)
    old = deepcopy(import_payload)
    old['complexes'][0].update(region_code='78', region='Санкт-Петербург', city='Пушкин', district='Пушкинский район')
    with pytest.raises(JsonImportError, match='однозначно'):
        import_complex_catalog(old)
    payload = canonical_payload(import_payload)
    assert import_complex_catalog(payload)['created'] == 1


@pytest.mark.django_db
def test_explicit_previous_location_adopts_existing_complex(import_payload, import_geography, settings, tmp_path):
    """Rename and move an existing source-less complex without replacing its ID."""
    settings.MEDIA_ROOT = tmp_path
    existing = import_geography['complex']
    strelna = Location.objects.get(name='Стрельна')
    set_primary_location(existing, strelna)
    payload = canonical_payload(import_payload)
    payload['complexes'][0].update(match_name=existing.name, match_location={'id': strelna.pk})
    first = import_complex_catalog(payload)
    second = import_complex_catalog(payload)
    existing.refresh_from_db()
    assert first['created'] == second['created'] == 0
    assert existing.source_key == 'canonical:suburb' and existing.primary_location.name == 'Пушкин'
    assert existing.realestatecomplexbuilding_set.get().pk == import_geography['building'].pk
    assert existing.location_links.filter(location=strelna, is_historical=True).exists()


@pytest.mark.django_db
def test_additional_line_resolves_same_station(import_payload, import_geography, settings, tmp_path):
    """An additional line must not produce a second physical station."""
    settings.MEDIA_ROOT = tmp_path
    station = import_geography['metro']
    line = MetroLine.objects.create(line='Дополнительная', line_color='#777777', system=station.metro_line.system)
    station.lines.add(line)
    payload = canonical_payload(import_payload)
    payload['complexes'][0]['metro'] = [{
        'system_id': line.system_id, 'line': line.line, 'station': station.station,
        'mode': 'На транспорте', 'minutes': 30,
    }]
    before = catalog_counts()
    import_complex_catalog(payload)
    import_complex_catalog(payload)
    complex_object = RealEstateComplex.objects.get(source_key='canonical:suburb')
    assert complex_object.metro_availability.get().metro_id == station.pk
    assert catalog_counts() == before
    assert set(station.lines.values_list('pk', flat=True)) == {line.pk, station.metro_line_id}


@pytest.mark.django_db
def test_later_bad_station_rolls_back_geography_links_and_new_metro(import_payload, import_geography, settings, tmp_path):
    """Roll back a created complex, line, station and photo if another row fails."""
    settings.MEDIA_ROOT = tmp_path
    payload = canonical_payload(import_payload)
    payload['complexes'][0]['metro'] = [{
        'system_id': import_geography['metro'].metro_line.system_id,
        'line': 'Новая для отката', 'station': 'Станция для отката',
        'color': '#123456', 'mode': 'Пешком', 'minutes': 10,
    }]
    bad = deepcopy(payload['complexes'][0])
    bad.update(key='bad:station', name='Не сохранять', metro=[{'station_id': 99999999, 'mode': 'Пешком', 'minutes': 5}])
    payload['complexes'].append(bad)
    before = catalog_counts()
    complex_count = RealEstateComplex.objects.count()
    link_count = RealEstateComplexLocation.objects.count()
    with pytest.raises(JsonImportError):
        import_complex_catalog(payload)
    assert catalog_counts() == before
    assert RealEstateComplex.objects.count() == complex_count
    assert RealEstateComplexLocation.objects.count() == link_count
    assert not list(tmp_path.rglob('*.jpg'))


@pytest.mark.django_db
@pytest.mark.parametrize('role', ['anonymous', 'regular', 'staff', 'moderator', 'administrator', 'superuser'])
def test_new_import_role_matrix(client, import_payload, import_geography, settings, tmp_path, role):
    """The canonical format retains the existing server-side import access policy."""
    settings.MEDIA_ROOT = tmp_path
    client.logout()
    user = json_import_account(role)
    if user:
        client.force_login(user)
    payload = canonical_payload(import_payload)
    response = client.post('/api/v1/complexes/import/', {'file': SimpleUploadedFile(
        'complexes.json', json.dumps(payload).encode(), 'application/json',
    )})
    allowed = role in ('administrator', 'superuser')
    assert response.status_code == (200 if allowed else 403), response.content
    assert RealEstateComplex.objects.filter(source_key='canonical:suburb').exists() == allowed


@pytest.mark.django_db
def test_conflicting_project_identity_is_reported_without_partial_rows(import_payload, import_geography, settings, tmp_path):
    """A same-developer name conflict returns an import error instead of server failure."""
    settings.MEDIA_ROOT = tmp_path
    payload = canonical_payload(import_payload)
    payload['complexes'][0]['name'] = import_geography['complex'].name
    before = list(RealEstateComplex.objects.order_by('pk').values())
    with pytest.raises((JsonImportError, ValidationError)):
        import_complex_catalog(payload)
    assert list(RealEstateComplex.objects.order_by('pk').values()) == before
    assert not list(tmp_path.rglob('*.jpg'))


@pytest.mark.django_db
def test_legacy_labels_survive_canonical_source_renames(import_payload, import_geography, settings, tmp_path):
    """Use preserved names and aliases when the official region or district is renamed."""
    settings.MEDIA_ROOT = tmp_path
    region = Location.objects.get(name='Санкт-Петербург', location_type__category='region')
    district = Location.objects.get(name='Пушкинский район')
    for location in (region, district):
        LocationAlias.objects.get_or_create(location=location, name=location.name)
        location.name = f'Новое имя {location.name}'
        location.save()
    row = import_payload['complexes'][0]
    row.update(name='Старые географические названия', region_code='78', region='Санкт-Петербург',
               city='Пушкин', district='Пушкинский район')
    assert import_complex_catalog(import_payload)['created'] == 1
    assert import_complex_catalog(import_payload)['created'] == 0
    assert RealEstateComplex.objects.get(source_key=row['key']).primary_location.name == 'Пушкин'
