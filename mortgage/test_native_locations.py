"""Protect native calculator geography and unchanged financial relationships."""

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext

from api_v1.test_location_filters import (  # noqa: F401
    complex_catalog, filtered_catalog, import_user, locality_catalog,
)
from bank.models import MortgageProgram, MortgageProgramRegionalCreditLimit
from customer.models import Customer, CustomerCalculation, CustomerTrenchCalculation
from location.tests.legacy_fixtures import create_legacy_fixture
from location.models import LocationCompatibilityEntry
from mortgage.forms import MortgageForm
from mortgage.models import MortgageCalculation
from property.location_context import set_primary_location
from property.models import Property
from trench_mortgage.models import TrenchMortgageCalculation


def calculator_data(apartment, locality, mode='market'):
    """Submit the same financial inputs with explicit canonical territory."""
    return {
        'PROPERTY': apartment.pk, 'PROPERTY_COST': '5000000',
        'OBJECT_REGION_LOCATION': locality.region_id,
        'OBJECT_DISTRICT_LOCATION': locality.parent_id, 'OBJECT_LOCALITY': locality.pk,
        'OBJECT_BUILDING': apartment.building_id,
        'DISCOUNT_MARKUP_TYPE': 'discount', 'DISCOUNT_MARKUP_VALUE': '0',
        'INITIAL_PAYMENT_PERCENT': '20', 'INITIAL_PAYMENT_RUBLES': '1000000',
        'INITIAL_PAYMENT_DATE': '2026-01-01', 'MORTGAGE_TERM': '240',
        'ANNUAL_RATE': '12', 'TRENCH_COUNT': '1', 'HAS_GRACE_PERIOD': 'no',
        'calculate': mode, 'CALCULATION_TYPE': mode,
        'trench_date_1': '2026-01-01', 'trench_amount_source_1': 'rubles',
        'annual_rate_1': '12',
    }


@pytest.mark.django_db
@pytest.mark.parametrize('town', ['pushkin', 'strelna'])
@pytest.mark.parametrize('mode', ['market', 'trench'])
def test_native_calculate_repeat_preserves_links(client, filtered_catalog, town, mode):
    """Save both programs twice with the same results and the original apartment."""
    locality, _, _, apartment = filtered_catalog[town]
    owner = get_user_model().objects.get(pk=client.session['_auth_user_id'])
    customer = Customer.objects.create(user=owner, first_name='Проверка')
    model = MortgageCalculation if mode == 'market' else TrenchMortgageCalculation
    links = CustomerCalculation if mode == 'market' else CustomerTrenchCalculation
    data = {**calculator_data(apartment, locality, mode), 'customer': customer.pk}
    old_property = Property.objects.values().get(pk=apartment.pk)
    results = []
    for _ in range(2):
        response = client.post('/mortgage/?legacy=1', data)
        assert response.status_code == 200, response.content
        assert not response.context['mortgage_form'].errors
        assert ('result' if mode == 'market' else 'trench_result') in response.context
        calculation = model.objects.latest('pk')
        assert calculation.property_id == apartment.pk
        assert calculation.user_id == owner.pk
        results.append({key: value for key, value in model.objects.values().get(pk=calculation.pk).items()
                        if key not in {'id', 'timestamp'}})
    assert results[0] == results[1]
    assert links.objects.filter(customer=customer).count() == 2
    assert Property.objects.values().get(pk=apartment.pk) == old_property


@pytest.mark.django_db
def test_native_prefill_selectors_limits_and_bounds(client, filtered_catalog):
    """Display real suburbs, bound HTML choices and resolve a distinct financial ID."""
    locality, _, building, apartment = filtered_catalog['strelna']
    LocationCompatibilityEntry.objects.filter(
        location_id=locality.region_id, model_name='region',
    ).delete()
    legacy_region = create_legacy_fixture(
        'region', pk=900001, name='Финансовый регион', code='LIM', location=locality.region,
    )
    program = MortgageProgram.objects.create(name='Лимит', is_preferential=True, credit_limit=6000000)
    limit = MortgageProgramRegionalCreditLimit.objects.create(
        mortgage_program=program, region_id=legacy_region.pk, legacy_region_name=legacy_region.name, credit_limit=12000000,
    )
    for index in range(26):
        Property.objects.create(
            building=building, apartment_number=f'ZZ-{index:02}', area=50, floor=2,
            layout=apartment.layout, decoration=apartment.decoration, property_cost=5000000,
        )
    response = client.get('/mortgage/', {'legacy': 1, 'property_id': apartment.pk})
    form = response.context['mortgage_form']
    assert form.initial['OBJECT_LOCALITY'] == locality.pk
    assert form.fields['OBJECT_CITY'].widget.input_type == 'hidden'
    assert len(form.fields['OBJECT_LOCALITY'].widget.choices) <= 52
    assert len(response.context['property_form_data']['properties']) == 1
    assert b'dependent_selects.js' not in response.content
    context = client.get('/mortgage/financial-region/', {'regionLocationId': locality.region_id}).json()
    assert context['financialRegionId'] == legacy_region.pk
    with CaptureQueriesContext(connection) as queries:
        options = client.get('/mortgage/property-options/', {'buildingId': building.pk}).json()
    assert len(options['properties']) == 20 and options['nextPage'] == 2
    assert len(queries) <= 12
    matched = client.get('/mortgage/property-options/', {'buildingId': building.pk, 'q': 'ZZ-25'}).json()
    assert matched['properties'][0]['apartment_number'] == 'ZZ-25'
    assert matched['properties'][0]['financial_region_id'] == legacy_region.pk
    limit.refresh_from_db()
    assert limit.credit_limit == 12000000
    assert client.get('/mortgage/property-options/').json()['properties'] == []
    assert client.get('/mortgage/property-options/', {
        'buildingId': building.pk, 'localityId': filtered_catalog['pushkin'][0].pk,
    }).json()['properties'] == []


@pytest.mark.django_db
def test_native_rejects_conflicting_scope_and_accepts_building_override(client, filtered_catalog):
    """An explicit building binding wins over a moved project's primary territory."""
    locality, project, building, apartment = filtered_catalog['pushkin']
    previous = project.location_links.get(is_primary=True)
    set_primary_location(project, filtered_catalog['strelna'][0])
    building.complex_location = previous
    building.save(update_fields=['complex_location'])
    good = calculator_data(apartment, locality)
    form = MortgageForm(good)
    assert form.is_valid(), form.errors
    bad = {**good, 'OBJECT_LOCALITY': filtered_catalog['strelna'][0].pk}
    response = client.post('/mortgage/?legacy=1', bad)
    assert 'OBJECT_BUILDING' in response.context['mortgage_form'].errors
    assert not MortgageCalculation.objects.exists()
    payload = client.get(f'/mortgage/property-cost/{apartment.pk}/').json()
    assert payload['locality_id'] == locality.pk
    assert client.get('/mortgage/?legacy=1').status_code == 200


@pytest.mark.django_db
def test_financial_region_never_uses_numeric_coincidence(client, filtered_catalog):
    """Missing canonical mappings must not select a legacy region with the same PK."""
    locality = filtered_catalog['pushkin'][0]
    LocationCompatibilityEntry.objects.filter(location_id=locality.region_id, model_name='region').delete()
    assert client.get('/mortgage/financial-region/', {
        'regionLocationId': locality.region_id,
    }).json()['financialRegionId'] is None


@pytest.mark.django_db
@pytest.mark.parametrize('path', ['/mortgage/property-options/', '/mortgage/financial-region/'])
@pytest.mark.parametrize('value', ['invalid', '-1', '99999999999999999999999'])
def test_native_selectors_validate_identifiers(client, path, value):
    """Malformed public selector inputs produce validation errors, not SQL errors."""
    assert client.get(path, {'localityId': value}).status_code == 400
    assert client.post(path).status_code == 405


@pytest.mark.django_db
@pytest.mark.parametrize('town', ['pushkin', 'strelna'])
def test_native_new_apartment_without_legacy_district_reuses_on_repeat(client, filtered_catalog, town):
    """Create once through the native form and retain its building on resubmission."""
    locality, project, building, apartment = filtered_catalog[town]
    data = {
        **calculator_data(apartment, locality), 'PROPERTY': '',
        'OBJECT_APARTMENT_NUMBER': 'Новая-2', 'OBJECT_AREA': '51', 'OBJECT_FLOOR': '2',
        'OBJECT_LAYOUT': apartment.layout_id, 'OBJECT_DECORATION': apartment.decoration_id,
    }
    assert project.district_id is None
    original_count = Property.objects.count()
    for _ in range(2):
        response = client.post('/mortgage/?legacy=1', data)
        assert response.status_code == 200
        assert not response.context['mortgage_form'].errors
        assert 'result' in response.context
    assert Property.objects.count() == original_count + 1
    created = Property.objects.get(building=building, apartment_number='Новая-2')
    assert created.building_id == building.pk
    assert MortgageCalculation.objects.filter(property=created).count() == 2
