"""Exercise canonical metro API, permissions, searches and fallback forms."""

from unittest.mock import patch

import pytest
from django.test import Client
from django.contrib import admin
from django.db import transaction
from django.db.models.deletion import ProtectedError

from api_v1.test_location_dictionaries import create_location_manager
from api_v1.test_location_import import import_user  # noqa: F401
from location.metro_forms import MetroForm, MetroLineForm, MetroSystemForm
from location.models import Location, LocationType, Metro, MetroLine, MetroSystem
from location.tests.test_metro_architecture import metro_geography, create_complex_link  # noqa: F401


def catalog_url(key, identifier=None):
    """Build the shared metro dictionary endpoint."""
    return f'/api/v1/location-dictionaries/{key}/' + (f'{identifier}/' if identifier else '')


@pytest.mark.django_db
def test_canonical_crud_memberships_and_geography(client, metro_geography):
    """Create a line with no old city and preserve complex links on station edits."""
    system, line, station, locality = metro_geography
    client.force_login(create_location_manager())
    response = client.post(catalog_url('metro-lines'), {
        'name': 'Вторая', 'systemId': system.pk, 'lineColor': '#112233',
    }, content_type='application/json')
    assert response.status_code == 201, response.content
    other = response.json()['id']
    assert MetroLine.objects.get(pk=other).city_id is None
    link = create_complex_link(station, locality)
    response = client.patch(catalog_url('metro', station.pk), {
        'lineIds': [other], 'locationId': locality.pk,
    }, content_type='application/json')
    assert response.status_code == 200, response.content
    assert {row['id'] for row in response.json()['lines']} == {line.pk, other}
    assert response.json()['locationIsInferred'] is False
    link.refresh_from_db()
    assert link.metro_id == station.pk
    response = client.get(catalog_url('metro'), {'metroLineId': other, 'systemId': system.pk, 'locationId': locality.pk})
    assert [row['id'] for row in response.json()['results']] == [station.pk]
    choices = client.get('/api/v1/catalog-options/metro/', {'metroLineId': other}).json()
    assert [row['id'] for row in choices['results']] == [station.pk]
    assert system.name in choices['results'][0]['label']
    # A selected station survives an exact locality filter and remains editable.
    choices = client.get('/api/v1/catalog-options/metro/', {'locationId': system.location_id, 'selected': station.pk}).json()
    assert choices['results'] == [] and choices['selected'][0]['id'] == station.pk
    assert client.delete(catalog_url('metro-systems', system.pk)).status_code == 409
    assert client.delete(catalog_url('metro-lines', line.pk)).status_code == 409
    assert client.delete(catalog_url('metro-lines', other)).status_code == 409
    assert station.lines.filter(pk=other).exists()
    response = client.post('/locations/?legacy=1', {
        'action': 'delete', 'model': 'metro_line', 'object_id': other,
    })
    assert response.status_code == 400
    assert station.lines.filter(pk=other).exists()
    with pytest.raises(ProtectedError):
        with transaction.atomic():
            MetroLine.objects.filter(pk=other).delete()
    assert station.lines.filter(pk=other).exists()
    _, _, _, protected = admin.site._registry[MetroLine].get_deleted_objects(
        MetroLine.objects.filter(pk=other), response.wsgi_request,
    )
    assert protected


@pytest.mark.django_db
def test_reject_cross_network_and_invalid_station_location(client, metro_geography):
    """Allow a station outside its network center but reject mixed networks."""
    system, line, station, locality = metro_geography
    client.force_login(create_location_manager())
    other_system = MetroSystem.objects.create(name='Другая система', location=locality)
    other_line = MetroLine.objects.create(line='Другая', line_color='#123456', system=other_system)
    response = client.patch(catalog_url('metro', station.pk), {'lineIds': [other_line.pk]}, content_type='application/json')
    assert response.status_code == 400 and 'lineIds' in response.json()
    response = client.patch(catalog_url('metro', station.pk), {'locationId': None, 'locationIsInferred': False}, content_type='application/json')
    assert response.status_code == 400 and 'locationId' in response.json()
    response = client.patch(catalog_url('metro-lines', line.pk), {'systemId': other_system.pk}, content_type='application/json')
    assert response.status_code == 400
    district_type = LocationType.objects.create(code='metro-district', category='district', name='Район')
    district = Location.objects.create(name='Район', location_type=district_type)
    response = client.post(catalog_url('metro-systems'), {'name': 'Тест', 'locationId': district.pk}, content_type='application/json')
    assert response.status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize('role', ['anonymous', 'regular', 'staff', 'moderator', 'administrator', 'superuser'])
def test_canonical_import_permission_matrix(client, import_user, metro_geography, role):
    """Keep imports administrator-only for the new system-based entrypoint."""
    system = metro_geography[0]
    user = import_user(role)
    if user:
        client.force_login(user)
    with patch('api_v1.views.import_metro', return_value={'created': 0}) as importer:
        response = client.post(catalog_url('metro') + 'import/', {'systemId': system.pk}, content_type='application/json')
    allowed = role in ('administrator', 'superuser')
    assert response.status_code == (200 if allowed else 403), response.content
    assert importer.call_count == int(allowed)


@pytest.mark.django_db
def test_new_metro_writes_require_csrf(import_user, metro_geography):
    """Session administrators still need CSRF for import and editing."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(import_user('administrator'))
    for path in [catalog_url('metro') + 'import/', catalog_url('metro-systems'), catalog_url('metro-lines')]:
        assert client.post(path, {}, content_type='application/json').status_code == 403


@pytest.mark.django_db
def test_station_lists_have_bounded_queries(client, metro_geography, django_assert_num_queries):
    """Serialize locality, network and many-line membership without N+1 queries."""
    _, line, _, _ = metro_geography
    Metro.objects.bulk_create([Metro(station=f'Станция {index}', metro_line=line) for index in range(30)])
    with django_assert_num_queries(3):
        response = client.get(catalog_url('metro'), {'pageSize': 50})
    assert response.status_code == 200 and response.json()['totalCount'] == 31


@pytest.mark.django_db
def test_fallback_forms_use_canonical_fields_and_retain_primary(metro_geography):
    """Validate bounded Django selectors and preserve the primary membership."""
    system, line, station, locality = metro_geography
    form = MetroForm({
        'station': station.station, 'metro_line': line.pk, 'lines': [],
        'location': locality.pk, 'is_active': True,
    }, instance=station)
    assert form.is_valid(), form.errors
    form.save()
    assert station.lines.filter(pk=line.pk).exists()
    assert len(list(form.fields['location'].widget.choices)) <= 52
    assert 'city' not in MetroLineForm().fields
    assert MetroSystemForm({'name': 'Новая', 'location': locality.pk, 'is_active': True}).is_valid()
