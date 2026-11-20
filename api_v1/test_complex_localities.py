"""Check locality-first complex mutations without fabricated legacy districts."""

import pytest

from api_v1.test_location_import import import_user
from api_v1.test_real_estate_complexes import complex_catalog
from location.tests.legacy_fixtures import update_legacy_fixture
from location.legacy_catalog import legacy_catalog
from location.gar_import import load_region
from location.models import Location
from location.tests.test_gar import SPB
from property.forms import RealEstateComplexForm
from property.models import ApartmentDecoration, ApartmentLayout, Property, RealEstateComplex
from api_v1.serializers import ManualCalculationPropertySerializer


@pytest.fixture
def locality_catalog(complex_catalog, client, import_user):
    """Add real GAR identities to a legacy graph and authenticate a moderator."""
    region = complex_catalog['region']
    update_legacy_fixture(region, name='Санкт-Петербург', code='78')
    load_region(SPB, '78', '20261113')
    client.force_login(import_user('moderator'))
    return complex_catalog


def locality_payload(catalog, locality='Пушкин'):
    """Submit a complex without any legacy city or district identifier."""
    return {
        'name': 'Квартал без прежнего района',
        'developerId': catalog['developer'].pk,
        'realEstateClassId': catalog['real_estate_class'].pk,
        'realEstateTypeId': catalog['real_estate_type'].pk,
        'locationId': Location.objects.get(name=locality).pk,
        'buildings': [{'number': 'Новый корпус', 'isActive': True}],
    }


@pytest.mark.django_db
def test_create_edit_locality_without_district_and_read_related_property(client, locality_catalog):
    """Create in Pushkin, move to Strelna, retain building and metro identities."""
    payload = locality_payload(locality_catalog)
    payload['metroAvailability'] = [{
        'metroId': locality_catalog['metro'].pk,
        'transportAccessibilityTypeId': locality_catalog['accessibility_type'].pk,
        'walkingTimeMinutes': 20,
    }]
    response = client.post('/api/v1/complexes/', payload, content_type='application/json')
    assert response.status_code == 201, response.content
    data = response.json()
    assert data['districtId'] is None and data['cityId'] is None
    assert data['city'] == 'Пушкин' and data['district'] == 'Пушкинский район'
    assert data['regionId'] == locality_catalog['region'].pk
    complex_object = RealEstateComplex.objects.get(pk=data['id'])
    building = complex_object.realestatecomplexbuilding_set.get()
    availability = complex_object.metro_availability.get()
    second = client.patch(f'/api/v1/complexes/{complex_object.pk}/', {
        'locationId': Location.objects.get(name='Стрельна').pk,
    }, content_type='application/json')
    assert second.status_code == 200, second.content
    assert second.json()['city'] == 'Стрельна'
    assert complex_object.metro_availability.get().pk == availability.pk
    assert complex_object.realestatecomplexbuilding_set.get().pk == building.pk
    property_object = Property.objects.create(
        building=building, apartment_number='1', area=52, floor=1, property_cost=5000000,
        layout=ApartmentLayout.objects.create(name='Студия'),
        decoration=ApartmentDecoration.objects.create(name='Без отделки'),
    )
    assert client.get(f'/api/v1/properties/{property_object.pk}/').json()['city'] == 'Стрельна'
    assert client.get('/api/v1/properties/').status_code == 200
    options = client.get('/api/v1/catalog-options/complexes/', {'selected': complex_object.pk}).json()
    assert options['selected'][0]['cityId'] is None
    choices = client.get('/api/v1/properties/options/', {'developerId': complex_object.developer_id})
    assert choices.status_code == 200
    assert complex_object.pk in {row['id'] for row in choices.json()['realEstateComplexes']}
    manual = ManualCalculationPropertySerializer(data={
        'developerId': complex_object.developer_id, 'realEstateComplexId': complex_object.pk,
        'buildingId': building.pk, 'apartmentNumber': '2', 'area': '52.00',
        'layoutId': property_object.layout_id, 'floor': 2, 'decorationId': property_object.decoration_id,
    })
    assert manual.is_valid(), manual.errors
    assert client.get('/api/v1/properties/', {'search': 'Стрельна'}).json()['totalCount'] == 1
    override = complex_object.location_links.get(location__name='Пушкин')
    building.complex_location = override
    building.save(update_fields=['complex_location'])
    assert client.get(f'/api/v1/properties/{property_object.pk}/').json()['city'] == 'Пушкин'


@pytest.mark.django_db
def test_existing_edit_preserves_legacy_links_and_secondary_building_override(client, locality_catalog):
    """Refine an old complex without clearing district, apartments or stations."""
    complex_object = locality_catalog['complex']
    building = locality_catalog['building']
    previous_district = complex_object.district_id
    primary = complex_object.location_links.get(is_primary=True)
    building.complex_location = primary
    building.save(update_fields=['complex_location'])
    response = client.patch(f'/api/v1/complexes/{complex_object.pk}/', {
        'locationId': Location.objects.get(name='Пушкин').pk,
    }, content_type='application/json')
    assert response.status_code == 200, response.content
    complex_object.refresh_from_db()
    building.refresh_from_db()
    assert complex_object.district_id == previous_district
    assert building.complex_location_id == primary.pk
    assert complex_object.location_links.count() == 2
    assert complex_object.metro_availability.get().pk == locality_catalog['availability'].pk
    assert client.patch(f'/api/v1/complexes/{complex_object.pk}/', {'districtId': None}, content_type='application/json').status_code == 200


@pytest.mark.django_db
def test_rejects_missing_invalid_and_inactive_locality(client, locality_catalog):
    """Require real locality roles and never silently create a placeholder district."""
    payload = locality_payload(locality_catalog)
    payload.pop('locationId')
    assert client.post('/api/v1/complexes/', payload, content_type='application/json').status_code == 400
    payload['locationId'] = locality_catalog['complex'].location_links.get(is_primary=True).location_id
    assert client.post('/api/v1/complexes/', payload, content_type='application/json').status_code == 400
    pushkin = Location.objects.get(name='Пушкин')
    pushkin.is_active = False
    pushkin.save(update_fields=['is_active'])
    payload['locationId'] = pushkin.pk
    assert client.post('/api/v1/complexes/', payload, content_type='application/json').status_code == 400


@pytest.mark.django_db
def test_fallback_form_accepts_locality_and_bounds_options(locality_catalog):
    """Django fallback forms use the same binding service and bounded choices."""
    payload = locality_payload(locality_catalog)
    form = RealEstateComplexForm(data={
        'name': payload['name'], 'developer': payload['developerId'],
        'real_estate_class': payload['realEstateClassId'],
        'real_estate_type': payload['realEstateTypeId'], 'location': payload['locationId'],
    })
    assert form.is_valid(), form.errors
    assert len(list(form['location'].field.widget.choices)) <= 2
    saved = form.save()
    assert saved.district_id is None
    assert saved.primary_location.name == 'Пушкин'


@pytest.mark.django_db
def test_same_named_villages_are_selectable_without_fabricated_cities(locality_catalog, client, django_assert_num_queries):
    """Distinct GAR identities survive creation, display and bounded list loading."""
    from django.test import Client

    rows = [dict(row) for row in SPB]
    for identifier, parent, level, name in [
        ('4', '1', '2', 'Северный'), ('5', '1', '2', 'Южный'),
        ('6', '4', '6', 'Дубровка'), ('7', '5', '6', 'Дубровка'),
    ]:
        rows.append(dict(SPB[2], id=identifier, guid=f'village-fixture-{identifier}',
                         parent=parent, level=level, name=name,
                         type='р-н' if level == '2' else 'д.',
                         typeName='Район' if level == '2' else 'Деревня'))
    load_region(rows, '78', '20261113')
    cities_before = legacy_catalog('city').count()
    villages = list(Location.objects.filter(name='Дубровка'))
    assert len(villages) == 2
    for village in villages:
        payload = locality_payload(locality_catalog)
        payload.update(name=f'Квартал {village.pk}', locationId=village.pk)
        response = client.post('/api/v1/complexes/', payload, content_type='application/json')
        assert response.status_code == 201, response.content
        assert response.json()['location']['id'] == village.pk
        assert response.json()['city'] == 'Дубровка'
        assert response.json()['districtId'] is None
    assert legacy_catalog('city').count() == cities_before
    with django_assert_num_queries(5):
        assert Client().get('/api/v1/complexes/').status_code == 200
