"""Keep program editing, calculator options and customer limits on one region identity."""

import json
from decimal import Decimal
from importlib import import_module
from pathlib import Path
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.db import connection

from api_v1.test_customer_locations import geographic_customer  # noqa: F401
from api_v1.test_customers import customer_users  # noqa: F401
from api_v1.test_location_filters import complex_catalog, filtered_catalog, import_user, locality_catalog  # noqa: F401
from api_v1.tests import create_catalog_manager
from bank.models import Bank, BankProgram, MortgageProgramRegionalCreditLimit
from location.tests.legacy_fixtures import legacy_district_for, registered_legacy_id
from location.gar_import import load_region
from location.models import LegacyLocationMapping, Location, LocationIdentifier, Region
from property.location_context import set_primary_location
from property.models import Property, RealEstateComplex, RealEstateComplexBuilding


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


@pytest.mark.django_db
def test_financial_region_for_pushkin_strelna_and_likino(client, geographic_customer, filtered_catalog):
    """Resolve suburb and village limits through the actual federal subject of the property."""
    original = filtered_catalog['legacy']
    program = geographic_customer.preferential_programs.get()
    old_limit = program.regional_credit_limits.get()
    BankProgram.objects.create(bank=Bank.objects.create(name='Сверка лимитов'), mortgage_program=program)
    fixture = Path(__file__).resolve().parents[1] / 'browser_acceptance' / 'data' / 'likino.json'
    load_region(json.loads(fixture.read_text(encoding='utf-8')), '50', '20261113')
    likino = LocationIdentifier.objects.get(provider='gar', value='868510').location
    likino_limit = MortgageProgramRegionalCreditLimit.objects.create(
        mortgage_program=program, region_location=likino.region, credit_limit=9500000,
    )
    project = RealEstateComplex.objects.create(
        name='Мыс', developer=original.developer, real_estate_class=original.real_estate_class,
        real_estate_type=original.real_estate_type, district_id=registered_legacy_id(legacy_district_for(original)),
    )
    set_primary_location(project, likino)
    building = RealEstateComplexBuilding.objects.create(real_estate_complex=project, number='1')
    template = filtered_catalog['pushkin'][3]
    apartment = Property.objects.create(building=building, apartment_number='1', area=55, floor=1,
                                        property_cost=6000000, layout=template.layout, decoration=template.decoration)
    options = client.get('/api/v1/mortgage/options/', {'canonicalLocations': 'true'}).json()
    amounts = {row['regionLocationId']: row['creditLimit'] for row in options['programs'][0]['regionalCreditLimits']}
    for locality, target, limit, expected_legacy in (
        (filtered_catalog['pushkin'][0], filtered_catalog['pushkin'][3], old_limit, old_limit.region_id),
        (filtered_catalog['strelna'][0], filtered_catalog['strelna'][3], old_limit, old_limit.region_id),
        (likino, apartment, likino_limit, None),
    ):
        response = client.patch(f'/api/v1/customers/{geographic_customer.pk}/', {
            'desiredRegionLocationId': locality.region_id, 'desiredLocalityId': locality.pk,
        }, content_type='application/json')
        assert response.status_code == 200, response.content
        profile = client.get(f'/api/v1/customers/{geographic_customer.pk}/').json()
        selector = client.get('/mortgage/financial-region/', {
            'canonicalLocations': 'true', 'buildingId': target.building_id,
        })
        assert selector.status_code == 200, selector.content
        assert selector.json()['financialRegionLocationId'] == profile['desiredFinancialRegionLocationId'] == locality.region_id
        assert profile['desiredFinancialRegionId'] == expected_legacy
        assert profile['calculated']['preferentialCreditLimit'] == amounts[locality.region_id] == f'{limit.credit_limit:.2f}'
        legacy = client.get('/mortgage/financial-region/', {'regionLocationId': locality.region_id}).json()
        assert legacy == {'financialRegionId': expected_legacy}


@pytest.mark.django_db
def test_financial_backfill_retains_conflicting_legacy_amounts(client, geographic_customer, filtered_catalog):
    """Preserve exact old financial IDs and never choose an alias for a Location-only caller."""
    program = geographic_customer.preferential_programs.get()
    limit = program.regional_credit_limits.get()
    region = filtered_catalog['strelna'][0].region
    BankProgram.objects.create(bank=Bank.objects.create(name='Банк сверки'), mortgage_program=program)
    alias = Region.objects.create(name='Другая запись того же субъекта', code='alternate')
    LegacyLocationMapping.objects.create(model_name='region', legacy_id=alias.pk, location=region)
    other = MortgageProgramRegionalCreditLimit.objects.create(mortgage_program=program, region_id=alias.pk, legacy_region_name=alias.name, credit_limit=9000000)
    assert program.get_credit_limit(region_location_id=region.pk) == Decimal('6000000')
    assert program.get_credit_limit(region_location_id=region.pk, legacy_region_id=alias.pk) == Decimal('9000000')
    context = SimpleNamespace(connection=connection)
    bank_migration = import_module('bank.migrations.0018_complete_limit_locations')
    customer_migration = import_module('customer.migrations.0008_complete_financial_regions')
    for _ in range(2):
        bank_migration.complete_limit_locations(apps, context)
        customer_migration.complete_financial_regions(apps, context)
    limit.refresh_from_db()
    other.refresh_from_db()
    geographic_customer.refresh_from_db()
    assert geographic_customer.desired_financial_region_id == limit.region_id
    assert geographic_customer.desired_financial_region_location_id == region.pk
    assert geographic_customer.get_preferential_credit_limit() == Decimal('12000000')
    assert limit.region_location_id is None and other.region_location_id is None
    rows = client.get('/api/v1/mortgage/options/', {'canonicalLocations': 'true'}).json()['programs'][0]['regionalCreditLimits']
    assert {row['regionId']: (row['regionLocationId'], row['creditLimit']) for row in rows} == {
        limit.region_id: (None, '12000000.00'), alias.pk: (None, '9000000.00'),
    }
    LegacyLocationMapping.objects.filter(model_name='region', legacy_id=alias.pk).delete()
    for _ in range(2):
        bank_migration.complete_limit_locations(apps, context)
    limit.refresh_from_db()
    other.refresh_from_db()
    assert (limit.region_location_id, limit.credit_limit) == (region.pk, Decimal('12000000'))
    assert (other.region_location_id, other.credit_limit) == (None, Decimal('9000000'))
