from decimal import Decimal

import pytest
from django.urls import reverse

from .test_customers import customer_profile, customer_users
from .test_saved_mortgage import build_save_payload, saved_calculation_property
from .test_trench_mortgage import build_saved_trench_mortgage_payload
from .tests import property_catalog


@pytest.mark.django_db
def test_property_filters_combine_exact_numbers_and_identifiers(
    client, property_catalog, django_assert_num_queries,
):
    """Restore all eight filters before bounded catalog pagination."""
    apartment = property_catalog[0]
    complex_object = apartment.building.real_estate_complex
    filters = {
        'city': complex_object.district.city_id,
        'developer': complex_object.developer_id,
        'realEstateComplex': complex_object.pk,
        'building': apartment.building_id,
        'apartmentNumber': '01', 'layout': apartment.layout_id,
        'area': '42.50', 'propertyCost': '12500000.00',
    }
    url = reverse('api_v1:property_list')
    with django_assert_num_queries(2):
        response = client.get(url, filters)
    assert [row['id'] for row in response.json()['results']] == [apartment.pk]
    for name in filters:
        mismatch = 'no match' if name == 'apartmentNumber' else '0'
        if name in {'city', 'developer', 'realEstateComplex', 'building', 'layout'}:
            mismatch = 999999
        result = client.get(url, {**filters, name: mismatch})
        assert result.status_code == 200, (name, result.content)
        assert result.json()['totalCount'] == 0, name


@pytest.mark.django_db
@pytest.mark.parametrize('kind', ['market', 'trench', 'customer'])
def test_calculation_ranges_are_inclusive_and_filter_before_pagination(
    client, customer_users, customer_profile, saved_calculation_property, kind,
):
    """Keep years, last payments and ranges consistent in all three lists."""
    owner, _ = customer_users
    client.force_login(owner)
    builder = (build_saved_trench_mortgage_payload if kind == 'trench'
               else build_save_payload)
    history_url = reverse(
        'api_v1:saved_trench_mortgage_calculation_create'
        if kind == 'trench' else 'api_v1:saved_mortgage_calculation_list'
    )
    for cost, payment, term, rate in (
        ('4000000.12', '20', 24, '12'), ('6000000.34', '30', 25, '10'),
    ):
        payload = builder(
            saved_calculation_property, propertyCost=cost,
            priceAdjustmentValue='0', initialPaymentValue=payment,
            mortgageTermMonths=term, annualRate=rate,
        )
        payload['customerId'] = customer_profile.pk
        saved = client.post(history_url, payload, content_type='application/json')
        assert saved.status_code == 201
    url = (reverse('api_v1:customer_calculation_list',
                   kwargs={'pk': customer_profile.pk})
           if kind == 'customer' else history_url)
    response = client.get(url, {'ordering': '-finalPropertyCost', 'pageSize': 1})
    assert response.status_code == 200
    assert response.json()['totalCount'] == 2
    selected = response.json()['results'][0]
    assert selected['finalPropertyCost'] == '6000000.34'
    payment_field = {'market': 'mainMonthlyPayment', 'trench': 'lastMonthlyPayment',
                     'customer': 'monthlyPayment'}[kind]
    ranges = {
        'cost': selected['finalPropertyCost'],
        'initialPayment': selected['initialPaymentRubles'],
        'monthlyPayment': selected[payment_field], 'rate': selected['annualRate'],
    }
    for name, value in ranges.items():
        result = client.get(url, {f'{name}From': value, f'{name}To': value})
        assert result.status_code == 200, (name, result.content)
        assert result.json()['totalCount'] == 1, name
        assert result.json()['results'][0]['finalPropertyCost'] == '6000000.34'
        assert client.get(url, {f'{name}To': '0'}).json()['totalCount'] == 0
    result = client.get(url, {'termFrom': '2.08', 'termTo': '2.09'})
    assert result.json()['totalCount'] == 1
    assert result.json()['results'][0]['mortgageTermMonths'] == 25
    assert client.get(url, {'termFrom': '2.09'}).json()['totalCount'] == 0
    assert client.get(url, {'city': 999999}).json()['totalCount'] == 0
    for ordering in ('city', 'realEstateComplex', 'initialPaymentRubles',
                     'monthlyPayment', 'mortgageTermMonths'):
        assert client.get(url, {'ordering': ordering}).status_code == 200


@pytest.mark.django_db
def test_tranche_range_uses_the_last_payment_rather_than_maximum(
    client, customer_users, customer_profile, saved_calculation_property,
):
    """Preserve legacy filtering when a later tranche reduces the payment."""
    from trench_mortgage.models import Trench

    owner, _ = customer_users
    client.force_login(owner)
    url = reverse('api_v1:saved_trench_mortgage_calculation_create')
    saved = client.post(url, {
        **build_saved_trench_mortgage_payload(saved_calculation_property),
        'customerId': customer_profile.pk,
    }, content_type='application/json')
    assert saved.status_code == 201
    identifier = saved.json()['id']
    Trench.objects.filter(calculation_id=identifier, trench_number=1).update(
        monthly_payment=Decimal('200000.25')
    )
    Trench.objects.filter(calculation_id=identifier, trench_number=2).update(
        monthly_payment=Decimal('100000.15')
    )
    selected = client.get(url, {'monthlyPaymentTo': '100000.15'}).json()
    assert selected['totalCount'] == 1
    row = selected['results'][0]
    assert row['maximumMonthlyPayment'] == '200000.25'
    assert row['lastMonthlyPayment'] == '100000.15'
    linked_url = reverse('api_v1:customer_calculation_list',
                         kwargs={'pk': customer_profile.pk})
    assert client.get(linked_url, {'monthlyPaymentTo': '100000.15'}).json()[
        'totalCount'
    ] == 1
