"""Verify the old address contract and business records across the schema change."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test.utils import CaptureQueriesContext

from api_v1.test_customer_calculations import create_customer_calculations
from api_v1.test_customer_locations import geographic_customer  # noqa: F401
from api_v1.test_customers import customer_users  # noqa: F401
from api_v1.test_location_filters import complex_catalog, filtered_catalog, import_user, locality_catalog  # noqa: F401
from api_v1.test_real_estate_complexes import create_catalog_manager
from customer.models import Customer, CustomerCalculation, CustomerTrenchCalculation
from location.models import LegacyLocationMapping
from mortgage.models import MortgageCalculation
from property.models import Property, RealEstateComplex, RealEstateComplexBuilding
from trench_mortgage.models import TrenchMortgageCalculation


@pytest.mark.django_db(transaction=True)
def test_address_detachment_keeps_business_rows_and_compatibility_ids(client, geographic_customer, filtered_catalog):
    """Reapply the two migrations without replacing addresses, links or results."""
    customer = geographic_customer
    _, complex_object, building, apartment = filtered_catalog['strelna']
    market, trench = create_customer_calculations(client, customer, apartment)
    old_amount = customer.get_preferential_credit_limit()
    previous = [
        ('customer', '0008_complete_financial_regions'),
        ('location', '0017_detach_metro_line_city'),
        ('property', '0023_detach_developer_region'),
    ]
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    legacy_complex = filtered_catalog['legacy']
    records_to_preserve = [
        RealEstateComplex.objects.filter(pk__in=[complex_object.pk, legacy_complex.pk]),
        complex_object.location_links.all(),
        legacy_complex.location_links.all(),
        legacy_complex.metro_availability.all(),
        RealEstateComplexBuilding.objects.filter(pk=building.pk),
        Property.objects.filter(pk=apartment.pk),
        MortgageCalculation.objects.filter(pk=market),
        TrenchMortgageCalculation.objects.filter(pk=trench),
        CustomerCalculation.objects.filter(customer=customer),
        CustomerTrenchCalculation.objects.filter(customer=customer),
    ]
    snapshots = [(records, list(records.order_by('pk').values())) for records in records_to_preserve]
    try:
        executor.migrate(previous)
        historical = executor.loader.project_state(previous).apps
        old_customer = historical.get_model('customer', 'Customer')
        old_district = historical.get_model('location', 'District').objects.get(pk=customer.desired_district_id)
        missing_city = historical.get_model('location', 'City').objects.create(
            name='Сохранённый город без соответствия', region_id=old_district.city.region_id,
        )
        old_customer.objects.filter(pk=customer.pk).update(residence_city_id=missing_city.pk)
        expected_customer = old_customer.objects.values().get(pk=customer.pk)
        for target in (latest, previous, latest):
            MigrationExecutor(connection).migrate(target)
            customer.refresh_from_db()
            assert Customer.objects.values().get(pk=customer.pk) == expected_customer
            assert customer.get_preferential_credit_limit() == old_amount
            for records, expected in snapshots:
                assert list(records.order_by('pk').values()) == expected
            with connection.cursor() as cursor:
                for model, columns in (
                    (Customer, {'residence_city_id', 'desired_city_id', 'desired_district_id', 'desired_financial_region_id'}),
                    (RealEstateComplex, {'district_id'}),
                ):
                    constraints = connection.introspection.get_constraints(cursor, model._meta.db_table)
                    old_keys = {definition['columns'][0] for definition in constraints.values()
                                if definition['foreign_key'] and definition['foreign_key'][0] in {'region', 'city', 'district'}}
                    assert old_keys == (columns if target == previous else set())
        assert customer.legacy_residence_city_name == missing_city.name
    finally:
        MigrationExecutor(connection).migrate(latest)


@pytest.mark.django_db
def test_old_address_writes_work_without_mirror_rows(
    client, geographic_customer, filtered_catalog, customer_users,
):
    """Resolve the old customer and complex payloads from the public ID registry."""
    customer = geographic_customer
    locality, source, _, _ = filtered_catalog['pushkin']
    region_id = customer.get_legacy_financial_region_id()
    old_city = LegacyLocationMapping.objects.create(
        model_name='city', legacy_id=900010, location=locality,
        legacy_name='Прежний город', legacy_region_id=region_id,
    )
    old_district = LegacyLocationMapping.objects.create(
        model_name='district', legacy_id=900011, location=locality.parent,
        legacy_name='Прежний район', legacy_city_id=old_city.legacy_id, legacy_region_id=region_id,
    )
    profile_url = f'/api/v1/customers/{customer.pk}/'
    customer_payload = {
        'residenceCityId': old_city.legacy_id,
        'desiredCityId': old_city.legacy_id,
        'desiredDistrictId': old_district.legacy_id,
    }
    with CaptureQueriesContext(connection) as queries:
        response = client.patch(profile_url, customer_payload, content_type='application/json')
        assert response.status_code == 200, response.content
        profile = client.get(profile_url).json()
    assert profile['residenceCityId'] == profile['desiredCityId'] == old_city.legacy_id
    assert profile['desiredDistrictId'] == old_district.legacy_id
    assert profile['desiredFinancialRegionId'] == region_id
    assert profile['desiredLocalityId'] == locality.pk
    assert profile['calculated']['preferentialCreditLimit'] == '12000000.00'
    assert profile['residenceCity'] == old_city.legacy_name
    assert profile['desiredDistrict'] == old_district.legacy_name
    assert not any(f'{operation} "{table}"' in query['sql'] for query in queries
                   for operation in ('FROM', 'JOIN') for table in ('city', 'district', 'region'))
    client.force_login(customer_users[1])
    assert client.get(profile_url).status_code == 404
    assert client.patch(profile_url, customer_payload, content_type='application/json').status_code == 404

    complex_payload = {
        'name': 'ЖК по старому идентификатору', 'developerId': source.developer_id,
        'realEstateClassId': source.real_estate_class_id, 'realEstateTypeId': source.real_estate_type_id,
        'districtId': old_district.legacy_id,
    }
    catalog_url = '/api/v1/complexes/'
    assert client.post(catalog_url, complex_payload, content_type='application/json').status_code == 403
    client.force_login(create_catalog_manager())
    with CaptureQueriesContext(connection) as queries:
        response = client.post(catalog_url, complex_payload, content_type='application/json')
        assert response.status_code == 201, response.content
        complex_object = response.json()
        complex_url = f"{catalog_url}{complex_object['id']}/"
        assert client.get(complex_url).json()['districtId'] == old_district.legacy_id
        response = client.patch(complex_url, {'locationId': locality.pk}, content_type='application/json')
    assert response.status_code == 200, response.content
    assert response.json()['districtId'] == old_district.legacy_id
    assert response.json()['localityId'] == locality.pk
    assert RealEstateComplex.objects.get(pk=complex_object['id']).location_links.filter(is_historical=True).count() == 1
    assert not any(f'{operation} "{table}"' in query['sql'] for query in queries
                   for operation in ('FROM', 'JOIN') for table in ('city', 'district', 'region'))
    for dictionary, identifier in (('cities', old_city.legacy_id), ('districts', old_district.legacy_id)):
        assert client.delete(f'/api/v1/location-dictionaries/{dictionary}/{identifier}/').status_code == 409
