"""Verify canonical search and safe refinement of existing complex territories."""

import pytest
from django.apps import apps
from django.core.exceptions import ValidationError
from django.test import Client

from api_v1.test_location_import import import_user
from api_v1.test_real_estate_complexes import complex_catalog
from location.gar_import import load_region
from location.migration_support import backfill_locations
from location.models import LegacyLocationMapping, Location
from location.tests.test_gar import SPB
from property.models import RealEstateComplex, RealEstateComplexLocation


@pytest.fixture
def geography_catalog(complex_catalog):
    """Upgrade a legacy complex while keeping its children and metro links."""
    region = complex_catalog['region']
    region.name, region.code = 'Санкт-Петербург', '78'
    region.save(update_fields=['name', 'code'])
    backfill_locations(apps)
    load_region(SPB, '78', '20261113')
    return complex_catalog


@pytest.mark.django_db
def test_search_returns_settlements_and_administrative_ancestors(client, geography_catalog, django_assert_num_queries):
    """Search precedes pagination and uses a bounded number of queries."""
    pushkin = Location.objects.get(name='Пушкин')
    response = client.get('/api/v1/locations/', {'q': 'Пушкин', 'category': 'locality'})
    assert response.status_code == 200
    assert response.json()['results'][0]['id'] == pushkin.pk
    assert 'Пушкинский' in response.json()['results'][0]['parent']
    assert client.get('/api/v1/catalog-options/locations/', {'q': 'Стрельна'}).json()['totalCount'] == 1
    assert client.get('/api/v1/locations/', {'q': 'Санкт-Петербург', 'category': 'locality'}).json()['totalCount'] == 1
    assert client.get('/api/v1/locations/', {'ancestorId': pushkin.parent_id, 'category': 'locality'}).json()['totalCount'] == 1
    # Count + page + empty selections: independent of result count.
    with django_assert_num_queries(2):
        assert client.get('/api/v1/locations/').status_code == 200


@pytest.mark.django_db
def test_refines_complex_and_building_without_changing_legacy_or_metro(client, import_user, geography_catalog):
    """Keep district/metro/building IDs, inherit primary and preserve overrides."""
    complex_object = geography_catalog['complex']
    building = geography_catalog['building']
    original_district = complex_object.district_id
    original_metro = list(complex_object.metro_availability.values_list('pk', 'metro_id'))
    pushkin = Location.objects.get(name='Пушкин')
    strelna = Location.objects.get(name='Стрельна')
    client.force_login(import_user('moderator'))
    url = f'/api/v1/complexes/{complex_object.pk}/locations/'
    payload = {'locations': [{'locationId': pushkin.pk, 'isPrimary': True}, {'locationId': strelna.pk, 'isPrimary': False}],
               'buildings': [{'id': building.pk, 'locationId': strelna.pk}]}
    response = client.put(url, payload, content_type='application/json')
    assert response.status_code == 200, response.content
    assert response.json()['buildings'][0]['effectiveLocationId'] == strelna.pk
    assert client.put(url, payload, content_type='application/json').status_code == 200
    assert complex_object.location_links.count() == 2
    complex_object.refresh_from_db()
    assert complex_object.district_id == original_district
    assert list(complex_object.metro_availability.values_list('pk', 'metro_id')) == original_metro
    payload['locations'] = payload['locations'][:1]
    payload['buildings'] = []
    assert client.put(url, payload, content_type='application/json').status_code == 400
    payload['buildings'] = [{'id': building.pk, 'locationId': None}]
    assert client.put(url, payload, content_type='application/json').status_code == 200
    assert client.get(url).json()['buildings'][0]['effectiveLocationId'] == pushkin.pk
    assert client.get('/api/v1/complexes/', {'locationId': pushkin.parent_id}).json()['totalCount'] == 1


@pytest.mark.django_db
@pytest.mark.parametrize('role', ['anonymous', 'regular', 'staff', 'moderator', 'administrator', 'superuser'])
def test_binding_roles_and_invalid_primary(client, import_user, geography_catalog, role):
    """Read publicly; allow mutations only to actual catalog managers."""
    complex_object = geography_catalog['complex']
    user = import_user(role)
    if user:
        client.force_login(user)
    url = f'/api/v1/complexes/{complex_object.pk}/locations/'
    assert client.get(url).status_code == 200
    payload = {'locations': [{'locationId': Location.objects.get(name='Пушкин').pk, 'isPrimary': False}]}
    response = client.put(url, payload, content_type='application/json')
    assert response.status_code == (400 if role in ['moderator', 'administrator', 'superuser'] else 403)


@pytest.mark.django_db
def test_binding_requires_csrf(import_user, geography_catalog):
    """Unsafe writes remain protected with an authenticated Django session."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(import_user('administrator'))
    assert client.put(f'/api/v1/complexes/{geography_catalog["complex"].pk}/locations/', {}, content_type='application/json').status_code == 403


@pytest.mark.django_db
def test_conservative_backfill_is_repeatable(geography_catalog):
    """Repeated backfills leave manually refined complex bindings unchanged."""
    complex_object = geography_catalog['complex']
    link = complex_object.location_links.get(is_primary=True)
    mapping = LegacyLocationMapping.objects.get(model_name='district', legacy_id=complex_object.district_id)
    assert link.location_id == mapping.location_id
    before = list(RealEstateComplexLocation.objects.values_list('pk', 'location_id', 'is_primary'))
    backfill_locations(apps)
    assert list(RealEstateComplexLocation.objects.values_list('pk', 'location_id', 'is_primary')) == before


@pytest.mark.django_db
def test_model_validation_rejects_cycles_and_foreign_building_links(geography_catalog):
    """Protect admin/model forms as well as the dedicated binding endpoint."""
    primary = geography_catalog['complex'].location_links.get(is_primary=True)
    location = primary.location
    location.parent = location
    with pytest.raises(ValidationError, match='Цикл'):
        location.clean()
    other_complex = RealEstateComplex.objects.create(
        name='Другой квартал', developer=geography_catalog['complex'].developer,
        district=geography_catalog['complex'].district,
        real_estate_class=geography_catalog['complex'].real_estate_class,
        real_estate_type=geography_catalog['complex'].real_estate_type,
    )
    building = geography_catalog['building']
    building.complex_location = other_complex.location_links.get(is_primary=True)
    with pytest.raises(ValidationError, match='территорию этого ЖК'):
        building.clean()
