"""Exercise canonical metro API, permissions, searches and fallback forms."""

from functools import partial
from unittest.mock import patch

import pytest
from django.test import Client
from django.contrib import admin
from django.db import connection, transaction
from django.db.models.deletion import ProtectedError
from django.test.utils import CaptureQueriesContext

from api_v1.test_location_dictionaries import create_location_manager
from api_v1.test_location_import import import_user  # noqa: F401
from location.metro_forms import MetroForm, MetroLineForm, MetroSystemForm
from location.compatibility import canonical_legacy_location
from location.models import City, LegacyLocationMapping, Location, LocationIdentifier, LocationType, Metro, MetroLine, MetroSystem, Region
from location.tests.test_metro_architecture import metro_geography, create_complex_link  # noqa: F401
from location.tests.source_fixtures import load_sources, source_reply
from property.models import RealEstateComplexMetroAvailability


def catalog_url(key, identifier=None):
    """Build the shared metro dictionary endpoint."""
    return f'/api/v1/location-dictionaries/{key}/' + (f'{identifier}/' if identifier else '')


@pytest.mark.django_db
def test_react_station_list_resolves_old_city_links_without_using_line_city(client, metro_geography):
    """Apply old URL IDs to the canonical network center and keep the old API shape."""
    system, line, station, _ = metro_geography
    region = Region.objects.create(name='Прежний регион', code='TEST')
    city = City.objects.create(region=region, name='Прежний город')
    LegacyLocationMapping.objects.create(
        model_name='city', legacy_id=city.pk, location=system.location,
        legacy_name=city.name, legacy_region_id=region.pk,
    )
    canonical_legacy_location(region)
    filters = {
        'canonicalLocations': 'true', 'cityId': city.pk,
        'ordering': '-location', 'status': 'active', 'q': system.location.name,
    }
    assert client.get(catalog_url('metro'), filters).json()['results'] == []
    station.is_active = True
    station.save(update_fields=['is_active'])
    result = client.get(catalog_url('metro'), filters)
    assert result.status_code == 200
    rows = result.json()['results']
    assert [row['id'] for row in rows] == [station.pk]
    assert rows[0]['city'] is None
    assert client.get(catalog_url('metro'), {'cityId': city.pk}).json()['results'] == []
    line.legacy_city_id = city.pk
    line.save(update_fields=['legacy_city_id'])
    old_row = client.get(catalog_url('metro'), {'cityId': city.pk}).json()['results'][0]
    assert old_row['city'] == {'id': city.pk, 'name': city.name}
    assert old_row['region'] == {'id': region.pk, 'name': region.name}


@pytest.mark.django_db
@pytest.mark.parametrize('registered_fias', (True, False))
def test_legacy_metro_filters_and_repeat_use_the_same_network(client, metro_geography, import_user, registered_fias):
    """Keep filters, an exact complex link and repeatability with mappings alone."""
    system, primary, station, suburb = metro_geography
    region_id, city_id = 71, 121
    if not registered_fias:
        LocationIdentifier.objects.filter(location=system.location, provider='fias').delete()
    LegacyLocationMapping.objects.bulk_create([
        LegacyLocationMapping(model_name='region', legacy_id=region_id, legacy_name='Москва',
                              legacy_code='77', location=system.location),
        LegacyLocationMapping(model_name='city', legacy_id=city_id, legacy_name='Москва',
                              legacy_region_id=region_id, location=system.location),
    ])
    primary.legacy_city_id = city_id
    primary.save(update_fields=['legacy_city_id'])
    alternate = MetroLine.objects.create(line='Пересадочная', line_color='#222222', system=system)
    station.lines.add(primary, alternate)
    link = create_complex_link(station, suburb)
    original_link = RealEstateComplexMetroAvailability.objects.values().get(pk=link.pk)
    parameters = {'regionId': region_id, 'cityId': city_id}
    with CaptureQueriesContext(connection) as queries:
        old = client.get(catalog_url('metro'), {**parameters, 'ordering': 'region'}).json()['results']
        new = client.get(catalog_url('metro'), {
            **parameters, 'canonicalLocations': 'true', 'locationId': suburb.pk,
            'metroLineId': alternate.pk, 'systemId': system.pk,
        }).json()['results']
    assert old[0]['id'] == new[0]['id'] == station.pk
    assert old[0]['city'] == {'id': city_id, 'name': 'Москва'}
    assert old[0]['region'] == {'id': region_id, 'name': 'Москва'}
    assert new[0]['location']['id'] == suburb.pk and new[0]['city'] is None
    assert not any(f'{verb} "{table}"' in query['sql'] for query in queries
                   for verb in ('FROM', 'JOIN') for table in ('city', 'region'))

    client.force_login(import_user('administrator'))
    with CaptureQueriesContext(connection) as queries:
        native = client.get('/locations/', {
            'model': 'metro', 'dictionary': 'metro', 'regionId': region_id, 'legacy': '1',
        })
    assert native.status_code == 200
    form = native.context['location_import_form']
    assert (region_id, 'Москва') in form.fields['regionId'].widget.choices
    assert (city_id, 'Москва') in form.fields['cityId'].widget.choices
    assert not any(f'{verb} "{table}"' in query['sql'] for query in queries
                   for verb in ('FROM', 'JOIN') for table in ('city', 'region'))
    sources = load_sources()
    endpoint = catalog_url('metro') + 'import/'
    with patch('location.open_data.OpenLocationSource.download', side_effect=partial(source_reply, sources)), \
            CaptureQueriesContext(connection) as queries:
        first = client.post(endpoint, parameters, content_type='application/json')
        legacy_repeat = client.post(endpoint, parameters, content_type='application/json')
        again = client.post(endpoint, {'systemId': system.pk}, content_type='application/json')
    assert first.status_code == legacy_repeat.status_code == again.status_code == 200, (
        first.content, legacy_repeat.content, again.content,
    )
    assert first.json()['created'] == 1
    for response in (legacy_repeat, again):
        assert response.json()['created'] == response.json()['updated'] == 0
        assert response.json()['lines']['created'] == response.json()['lines']['updated'] == 0
    assert not any(f'{verb} "{table}"' in query['sql'] for query in queries
                   for verb in ('FROM', 'JOIN', 'UPDATE', 'INTO') for table in ('city', 'region'))
    station.refresh_from_db()
    assert station.location_id == suburb.pk and not station.location_is_inferred
    assert set(station.lines.values_list('pk', flat=True)) == {primary.pk, alternate.pk}
    assert RealEstateComplexMetroAvailability.objects.values().get(pk=link.pk) == original_link


@pytest.mark.django_db
def test_legacy_city_used_by_metro_cannot_be_deleted(client, metro_geography):
    """Preserve the existing protection in the API and Django admin."""
    _, line, _, _ = metro_geography
    region = Region.objects.create(name='Москва', code='77')
    city = City.objects.create(region=region, name='Москва')
    canonical_legacy_location(city)
    line.legacy_city_id = city.pk
    line.save(update_fields=['legacy_city_id'])

    client.force_login(create_location_manager())
    response = client.delete(catalog_url('cities', city.pk))
    assert response.status_code == 409
    with pytest.raises(ProtectedError), transaction.atomic():
        City.objects.filter(pk=city.pk).delete()
    _, _, _, protected = admin.site._registry[City].get_deleted_objects([city], response.wsgi_request)
    assert str(line) in protected
    assert City.objects.filter(pk=city.pk).exists()


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
    assert MetroLine.objects.get(pk=other).legacy_city_id is None
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
