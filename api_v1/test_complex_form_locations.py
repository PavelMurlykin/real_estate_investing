"""Keep React form geography canonical and legacy clients compatible."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from api_v1.test_complex_localities import (  # noqa: F401
    complex_catalog, import_user, locality_catalog, locality_payload,
)
from location.models import Location, LocationClosure
from property.models import RealEstateComplex


@pytest.mark.django_db
@pytest.mark.parametrize('name', ['Пушкин', 'Стрельна'])
def test_canonical_complex_form_create_edit_repeat(client, locality_catalog, name):
    """Use Location scopes without rewriting preserved district and child links."""
    project = locality_catalog['complex']
    building = locality_catalog['building']
    primary = project.location_links.get(is_primary=True)
    building.complex_location = primary
    building.save(update_fields=['complex_location'])
    original_district = project.district_id
    original_metro = list(project.metro_availability.values())
    locality = Location.objects.get(name=name)
    payload = {
        'locationId': locality.pk, 'regionLocationId': locality.region_id,
        'districtLocationId': locality.parent_id,
    }
    for _ in range(2):
        response = client.patch(f'/api/v1/complexes/{project.pk}/', payload, content_type='application/json')
        assert response.status_code == 200, response.content
        assert response.json()['location']['id'] == locality.pk
        assert response.json()['districtLocationId'] == locality.parent_id
        assert response.json()['regionLocationId'] == locality.region_id
    project.refresh_from_db()
    building.refresh_from_db()
    assert project.district_id == original_district
    assert building.complex_location_id == primary.pk
    assert project.location_links.filter(location=locality).count() == 1
    assert list(project.metro_availability.values()) == original_metro
    created = client.post('/api/v1/complexes/', {
        **locality_payload(locality_catalog, name), 'name': f'Новый {name}', **payload,
    }, content_type='application/json')
    assert created.status_code == 201, created.content
    assert created.json()['districtId'] is None


@pytest.mark.django_db
def test_canonical_complex_form_scope_errors_are_atomic(client, locality_catalog):
    """Reject mismatching scopes and wrong categories without saving any changes."""
    project = locality_catalog['complex']
    before = RealEstateComplex.objects.values().get(pk=project.pk)
    locality = Location.objects.get(name='Пушкин')
    other = Location.objects.get(name='Стрельна')
    for scope in [
        {'districtLocationId': other.parent_id}, {'regionLocationId': locality.parent_id},
    ]:
        response = client.patch(f'/api/v1/complexes/{project.pk}/', {
            'name': 'Не сохранять', 'locationId': locality.pk, **scope,
        }, content_type='application/json')
        assert response.status_code == 400, response.content
        assert next(iter(scope)) in response.json()
        assert RealEstateComplex.objects.values().get(pk=project.pk) == before


@pytest.mark.django_db
def test_old_complex_payload_still_creates_and_updates(client, locality_catalog):
    """Keep old districtId-only clients and metadata-only edits working."""
    payload = locality_payload(locality_catalog)
    payload.pop('locationId')
    payload['districtId'] = locality_catalog['district'].pk
    response = client.post('/api/v1/complexes/', payload, content_type='application/json')
    assert response.status_code == 201, response.content
    identifier = response.json()['id']
    response = client.patch(f'/api/v1/complexes/{identifier}/', {'description': 'Старый формат'}, content_type='application/json')
    assert response.status_code == 200, response.content
    assert response.json()['districtId'] == payload['districtId']


@pytest.mark.django_db
def test_complex_options_skip_old_geography_only_when_requested(client, locality_catalog):
    """The React options path never queries old geographic tables."""
    with CaptureQueriesContext(connection) as queries:
        response = client.get('/api/v1/complexes/options/', {'canonicalLocations': 'true'})
    assert response.status_code == 200
    assert all(response.json()[field] == [] for field in ['regions', 'cities', 'districts', 'metroStations'])
    assert not any(f'FROM "{table}"' in row['sql'] for row in queries
                   for table in ['region', 'city', 'district'])
    old = client.get('/api/v1/complexes/options/', {'cityId': locality_catalog['city'].pk})
    assert old.status_code == 200
    assert old.json()['regions'] and old.json()['districts'] and old.json()['metroStations']


@pytest.mark.django_db
def test_locality_context_is_bounded_and_uses_administrative_ancestors(client, locality_catalog):
    """Hydrate region and district for all localities, including a nested area."""
    locality = Location.objects.get(name='Стрельна')
    with CaptureQueriesContext(connection) as queries:
        response = client.get('/api/v1/catalog-options/locations/', {
            'category': 'locality', 'includeContext': 'true', 'q': 'Стрельна', 'selectedIds': locality.pk,
        })
    assert response.status_code == 200
    assert len(queries) <= 6
    row, = response.json()['results']
    assert row['regionLocationId'] == locality.region_id
    assert row['districtLocationId'] == locality.parent_id
    assert response.json()['selected'][0]['districtLocationId'] == locality.parent_id
    LocationClosure.objects.filter(descendant=locality, ancestor=locality.parent).update(depth=2)
    assert client.get('/api/v1/catalog-options/locations/', {
        'selectedIds': locality.pk, 'includeContext': 'true',
    }).json()['selected'][0]['districtLocationId'] == locality.parent_id
