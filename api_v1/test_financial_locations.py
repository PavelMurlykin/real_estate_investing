"""Keep program editing, calculator options and customer limits on one region identity."""

from decimal import Decimal

import pytest

from api_v1.test_customer_locations import geographic_customer  # noqa: F401
from api_v1.test_customers import customer_users  # noqa: F401
from api_v1.test_location_filters import complex_catalog, filtered_catalog, import_user, locality_catalog  # noqa: F401
from api_v1.tests import create_catalog_manager
from bank.models import Bank, BankProgram, MortgageProgramRegionalCreditLimit
from location.models import Location, Region


@pytest.mark.django_db
def test_canonical_limits_preserve_old_edits_and_customer_amounts(
    client, geographic_customer, filtered_catalog, customer_users,
):
    """Repeat both formats and resolve Pushkin and Strelna to the same active limit."""
    customer = geographic_customer
    program = customer.preferential_programs.get()
    limit = program.regional_credit_limits.get()
    region = filtered_catalog['strelna'][0].region
    client.force_login(create_catalog_manager())
    BankProgram.objects.create(bank=Bank.objects.create(name='Банк локаций'), mortgage_program=program)
    endpoint = f'/api/v1/mortgage-programs/{program.pk}/'
    for query, identity in [
        ('?canonicalLocations=true', {'regionLocationId': region.pk}),
        ('', {'regionId': limit.region_id}),
        ('?canonicalLocations=true', {'regionLocationId': region.pk}),
    ]:
        response = client.patch(endpoint + query, {
            'regionalCreditLimits': [{**identity, 'creditLimit': '12000000.00', 'isActive': True}],
        }, content_type='application/json')
        assert response.status_code == 200, response.content
        row, = response.json()['regionalCreditLimits']
        assert row['id'] == limit.pk and row['creditLimit'] == '12000000.00'
        assert ('regionLocationId' in row) == bool(query)
    limit.refresh_from_db()
    assert limit.region_location_id == region.pk
    assert program.get_credit_limit(limit.region_id) == Decimal('12000000')
    options = client.get('/api/v1/mortgage/options/', {'canonicalLocations': 'true'}).json()
    row, = options['programs'][0]['regionalCreditLimits']
    assert row == {
        'regionId': limit.region_id, 'regionLocationId': region.pk,
        'retainedRegionKey': f'region:{limit.region_id}', 'creditLimit': '12000000.00',
    }
    legacy, = client.get('/api/v1/mortgage/options/').json()['programs'][0]['regionalCreditLimits']
    assert legacy == {'regionId': limit.region_id, 'creditLimit': '12000000.00'}
    owner, _ = customer_users
    client.force_login(owner)
    for town in ['pushkin', 'strelna']:
        locality, _, _, apartment = filtered_catalog[town]
        assert client.get(f'/api/v1/properties/{apartment.pk}/').json()['regionLocationId'] == region.pk
        response = client.patch(f'/api/v1/customers/{customer.pk}/', {
            'desiredLocalityId': locality.pk,
        }, content_type='application/json')
        assert response.status_code == 200, response.content
        profile = client.get(f'/api/v1/customers/{customer.pk}/').json()
        assert profile['desiredFinancialRegionLocationId'] == region.pk
        assert profile['desiredFinancialRegionId'] == limit.region_id
        assert profile['calculated']['preferentialCreditLimit'] == '12000000.00'


@pytest.mark.django_db
def test_region_without_old_identity_and_legacy_writer(client, geographic_customer, filtered_catalog):
    """Keep a Location-only override through replacement by an old API client."""
    program = geographic_customer.preferential_programs.get()
    legacy = program.regional_credit_limits.get()
    region_type = filtered_catalog['strelna'][0].region.location_type
    region = Location.objects.create(name='Новый финансовый субъект', location_type=region_type)
    count = Region.objects.count()
    client.force_login(create_catalog_manager())
    endpoint = f'/api/v1/mortgage-programs/{program.pk}/'
    response = client.patch(endpoint + '?canonicalLocations=true', {'regionalCreditLimits': [
        {'regionLocationId': region.pk, 'creditLimit': '8000000.00'},
        {'regionId': legacy.region_id, 'creditLimit': '12000000.00'},
    ]}, content_type='application/json')
    assert response.status_code == 200, response.content
    assert client.patch(endpoint, {'regionalCreditLimits': [
        {'regionId': legacy.region_id, 'creditLimit': '12000000.00'},
    ]}, content_type='application/json').status_code == 200
    limit = MortgageProgramRegionalCreditLimit.objects.get(region_location=region)
    assert limit.region_id is None and Region.objects.count() == count
    assert program.get_credit_limit(region_location_id=region.pk) == Decimal('8000000')
    assert len(client.get(endpoint).json()['regionalCreditLimits']) == 1
    for fields in [{'regionLocationId': filtered_catalog['strelna'][0].pk},
                   {'regionLocationId': region.pk, 'regionId': legacy.region_id}]:
        response = client.patch(endpoint, {'regionalCreditLimits': [{**fields, 'creditLimit': '1'}]},
                                content_type='application/json')
        assert response.status_code == 400
        assert program.get_credit_limit(region_location_id=region.pk) == Decimal('8000000')
