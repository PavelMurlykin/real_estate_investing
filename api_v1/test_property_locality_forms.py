"""Verify locality-first apartment forms without replacing existing building links."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from api_v1.test_location_filters import filtered_catalog, locality_catalog, complex_catalog, import_user
from location.models import City, District, Location, Region
from property.forms import PropertyForm
from property.location_context import set_primary_location
from property.models import Property, RealEstateComplexBuilding, WindowView


@pytest.mark.django_db
def test_property_form_options_use_canonical_localities_and_building_overrides(client, filtered_catalog):
    """Filter projects and buildings by the same effective geography as apartment lists."""
    strelna, veren, building, apartment = filtered_catalog['strelna']
    pushkin = filtered_catalog['pushkin'][0]
    parameters = {
        'regionLocationId': strelna.region_id, 'districtLocationId': strelna.parent_id,
        'localityId': strelna.pk, 'developerId': veren.developer_id, 'realEstateComplexId': veren.pk,
    }
    response = client.get('/api/v1/properties/options/', parameters)
    assert response.status_code == 200
    assert response.json()['realEstateComplexes'] == [{'id': veren.pk, 'name': veren.name}]
    assert response.json()['buildings'] == [{'id': building.pk, 'number': building.number}]
    parameters['localityId'] = pushkin.pk
    assert client.get('/api/v1/properties/options/', parameters).json()['buildings'] == []
    previous = veren.location_links.get(is_primary=True)
    set_primary_location(veren, pushkin)
    building.complex_location = previous
    building.save(update_fields=['complex_location'])
    parameters['localityId'] = strelna.pk
    assert client.get('/api/v1/properties/options/', parameters).json()['buildings'][0]['id'] == building.pk
    options = client.get('/api/v1/catalog-options/buildings/', {'selectedIds': building.pk}).json()
    context = options['selected'][0]
    assert context['localityId'] == strelna.pk and context['districtLocationId'] == strelna.parent_id
    assert context['regionLocationId'] == strelna.region_id
    assert context['regionId'] == filtered_catalog['legacy'].district.city.region_id
    assert client.get('/api/v1/properties/options/', {'localityId': 'invalid'}).status_code == 400


@pytest.mark.django_db
def test_create_edit_apartment_keeps_geography_on_building_only(client, filtered_catalog):
    """Create in Pushkin, edit fields, then explicitly choose a Strelna building."""
    strelna, _, strelna_building, _ = filtered_catalog['strelna']
    pushkin, _, building, template = filtered_catalog['pushkin']
    counts = [model.objects.count() for model in [Region, City, District, Location]]
    view = WindowView.objects.create(name='Парк')
    payload = {
        'buildingId': building.pk, 'apartmentNumber': 'NEW-42', 'area': '51.25', 'floor': 4,
        'propertyCost': '8000000.00', 'layoutId': template.layout_id,
        'decorationId': template.decoration_id, 'windowViewIds': [view.pk],
    }
    created = client.post('/api/v1/properties/', payload, content_type='application/json')
    assert created.status_code == 201, created.content
    data = created.json()
    identifier = data['id']
    assert data['localityId'] == pushkin.pk and data['cityId'] is None and data['districtId'] is None
    response = client.patch(f'/api/v1/properties/{identifier}/', {'area': '52.25'}, content_type='application/json')
    assert response.status_code == 200
    apartment = Property.objects.get(pk=identifier)
    assert apartment.building_id == building.pk and list(apartment.window_views.all()) == [view]
    assert str(apartment.property_cost) == '8000000.00'
    response = client.patch(f'/api/v1/properties/{identifier}/', {'buildingId': strelna_building.pk}, content_type='application/json')
    assert response.status_code == 200 and response.json()['localityId'] == strelna.pk
    assert counts == [model.objects.count() for model in [Region, City, District, Location]]


@pytest.mark.django_db
def test_native_property_form_preserves_selected_territory_and_rejects_conflicting_helpers(client, filtered_catalog):
    """Use current building ancestry and retain entered values after validation errors."""
    strelna, project, building, apartment = filtered_catalog['strelna']
    pushkin = filtered_catalog['pushkin'][0]
    form = PropertyForm(instance=apartment)
    assert form.initial['locality'] == strelna.pk
    assert form.initial['district_location'] == strelna.parent_id
    assert all(len(form.fields[name].widget.choices) <= 52 for name in ['locality', 'complex', 'building'])
    payload = {
        'building': building.pk, 'apartment_number': 'NEW', 'area': '52.00', 'floor': 3,
        'property_cost': '7000000.00', 'layout': apartment.layout_id, 'decoration': apartment.decoration_id,
    }
    form = PropertyForm(data=payload)
    assert form.is_valid(), form.errors
    payload['locality'] = pushkin.pk
    form = PropertyForm(data=payload)
    assert not form.is_valid() and 'building' in form.errors
    response = client.get(reverse('property:update', args=[apartment.pk]))
    assert response.status_code == 200
    assert 'п. Стрельна' in response.content.decode()
    assert 'property-form-data' not in response.content.decode()


@pytest.mark.django_db
def test_building_choices_batch_explicit_geography_and_preserve_selected_values(client, filtered_catalog):
    """Keep geographic option queries constant when the number of buildings grows."""
    strelna, project, building, _ = filtered_catalog['strelna']
    building.complex_location = project.location_links.get(is_primary=True)
    building.save(update_fields=['complex_location'])
    url = '/api/v1/catalog-options/buildings/'
    parameters = {'realEstateComplexId': project.pk, 'localityId': strelna.pk}
    with CaptureQueriesContext(connection) as initial:
        response = client.get(url, parameters)
    assert response.status_code == 200
    RealEstateComplexBuilding.objects.bulk_create([
        RealEstateComplexBuilding(real_estate_complex=project, number=str(index), complex_location=building.complex_location)
        for index in range(2, 12)
    ])
    with CaptureQueriesContext(connection) as expanded:
        response = client.get(url, parameters)
    assert response.status_code == 200 and response.json()['totalCount'] == 11
    assert len(expanded) == len(initial)
    selected = client.get(url, {'q': 'нет совпадений', 'selectedIds': building.pk}).json()
    assert selected['selected'][0]['localityId'] == strelna.pk
