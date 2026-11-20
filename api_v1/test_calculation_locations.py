"""Verify effective geography without modifying saved financial results or links."""

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from api_v1.test_location_filters import (  # noqa: F401
    complex_catalog, filtered_catalog, import_user, locality_catalog,
)
from api_v1.test_customers import customer_users  # noqa: F401
from api_v1.test_customer_calculations import create_customer_calculations
from bank.models import MortgageProgram, MortgageProgramRegionalCreditLimit
from customer.models import Customer, CustomerCalculation, CustomerTrenchCalculation
from location.models import LocationAlias
from location.tests.legacy_fixtures import (
    create_legacy_fixture, legacy_city_for, legacy_district_for, registered_legacy_id,
)
from mortgage.models import MortgageCalculation
from property.models import RealEstateComplexLocation
from trench_mortgage.models import Trench, TrenchMortgageCalculation


@pytest.fixture
def location_calculations(client, filtered_catalog, customer_users):
    """Save both financial programs in suburbs with no legacy city records."""
    owner, other = customer_users
    client.force_login(owner)
    customer = Customer.objects.create(
        user=owner, first_name='Локации расчётов',
        desired_city_id=registered_legacy_id(legacy_district_for(filtered_catalog['legacy']).city),
    )
    program = MortgageProgram.objects.create(
        name='Лимит географии', is_preferential=True, credit_limit=6000000,
    )
    MortgageProgramRegionalCreditLimit.objects.create(
        mortgage_program=program, region_id=legacy_city_for(customer.desired_city_id).region.pk, legacy_region_name=legacy_city_for(customer.desired_city_id).region.name, credit_limit=12000000,
    )
    customer.preferential_programs.add(program)
    identifiers = {}
    for name in ('pushkin', 'strelna'):
        identifiers[name] = create_customer_calculations(
            client, customer, filtered_catalog[name][3],
        )
    return {
        'catalog': filtered_catalog, 'customer': customer,
        'owner': owner, 'other': other, 'ids': identifiers,
    }


def endpoints(data):
    """Exercise both saved histories and the customer's combined table."""
    return [
        ('/api/v1/mortgage/calculations/', 0),
        ('/api/v1/mortgage/trench/calculations/', 1),
        (f'/api/v1/customers/{data["customer"].pk}/calculations/', None),
    ]


def expected_identifiers(data, town, program):
    """Keep link identifiers separate from calculation identifiers."""
    return set(data['ids'][town] if program is None else [data['ids'][town][program]])


@pytest.mark.django_db
def test_saved_search_filters_and_sorting_use_canonical_locations(client, location_calculations):
    """Search both suburbs and their administrative parents before paging."""
    data = location_calculations
    for town, label in [('pushkin', 'Пушкин'), ('strelna', 'Стрельна')]:
        locality = data['catalog'][town][0]
        for endpoint, program in endpoints(data):
            for parameters in (
                {'q': label}, {'q': locality.parent.name},
                {'localityId': locality.pk},
                {'districtLocationId': locality.parent_id},
                {
                    'regionLocationId': locality.region_id,
                    'districtLocationId': locality.parent_id,
                    'localityId': locality.pk,
                },
            ):
                response = client.get(endpoint, parameters)
                assert response.status_code == 200, response.content
                rows = response.json()['results']
                key = 'calculationId' if program is None else 'id'
                assert {row[key] for row in rows} == expected_identifiers(data, town, program)
                assert all(row['property']['city'] == label for row in rows)
                assert all(row['property']['localityId'] == locality.pk for row in rows)
                assert all(
                    row['property']['districtLocationId'] == locality.parent_id
                    for row in rows
                )
                assert all(row['property']['region'] == 'Санкт-Петербург' for row in rows)
            conflict = client.get(endpoint, {
                'districtLocationId': data['catalog']['pushkin'][0].parent_id,
                'localityId': data['catalog']['strelna'][0].pk,
            })
            assert conflict.status_code == 200 and conflict.json()['totalCount'] == 0
    for endpoint, _ in endpoints(data):
        response = client.get(endpoint, {'ordering': 'city', 'pageSize': 1})
        assert response.status_code == 200
        assert response.json()['results'][0]['property']['city'] == 'Пушкин'
        response = client.get(endpoint, {'ordering': '-city', 'pageSize': 1})
        assert response.json()['results'][0]['property']['city'] == 'Стрельна'


@pytest.mark.django_db
def test_aliases_and_building_override_exclude_secondary_history_and_old_district(
    client, location_calculations,
):
    """Use the apartment's territory rather than other complex links or old city names."""
    data = location_calculations
    pushkin, project, building, _ = data['catalog']['pushkin']
    strelna = data['catalog']['strelna'][0]
    project.district_id = legacy_district_for(data['catalog']['legacy']).pk
    project.save()
    historical = RealEstateComplexLocation.objects.create(
        real_estate_complex=project, location=strelna, is_historical=True,
    )
    LocationAlias.objects.create(location=pushkin, name='Алиас пригорода')
    for endpoint, program in endpoints(data):
        rows = client.get(endpoint, {'q': 'Алиас пригорода'}).json()['results']
        key = 'calculationId' if program is None else 'id'
        assert {row[key] for row in rows} == expected_identifiers(data, 'pushkin', program)
        old_city_search = client.get(endpoint, {
            'q': legacy_district_for(data['catalog']['legacy']).city.name,
        })
        assert old_city_search.json()['totalCount'] == 0
        strelna_response = client.get(endpoint, {'localityId': strelna.pk})
        assert strelna_response.json()['totalCount'] == (2 if program is None else 1)
    building.complex_location = historical
    building.save()
    for endpoint, _ in endpoints(data):
        assert client.get(endpoint, {'localityId': pushkin.pk}).json()['totalCount'] == 0
        rows = client.get(endpoint, {'localityId': strelna.pk}).json()['results']
        assert len(rows) == (4 if 'customers' in endpoint else 2)
        assert all(row['property']['city'] == 'Стрельна' for row in rows)


@pytest.mark.django_db
def test_old_city_url_resolves_through_mapping_without_id_confusion(client, location_calculations):
    """An old federal-city link includes the corresponding canonical suburbs."""
    data = location_calculations
    locality = data['catalog']['pushkin'][0]
    old_region = legacy_district_for(data['catalog']['legacy']).city.region
    city = create_legacy_fixture('city', pk=900000, name='Санкт-Петербург', region=old_region, location=locality.region)
    for endpoint, _ in endpoints(data):
        response = client.get(endpoint, {'city': city.pk})
        assert response.status_code == 200
        assert response.json()['totalCount'] == (4 if 'customers' in endpoint else 2)
        assert client.get(endpoint, {'city': locality.pk}).json()['totalCount'] == 0


@pytest.mark.django_db
def test_financial_rows_links_and_limits_are_unchanged_by_all_location_reads(
    client, location_calculations,
):
    """Compare every stored result, tranche and customer association after reads."""
    data = location_calculations
    models = (MortgageCalculation, TrenchMortgageCalculation, Trench, Customer,
              CustomerCalculation, CustomerTrenchCalculation, MortgageProgramRegionalCreditLimit)
    before = {model: list(model.objects.order_by('pk').values()) for model in models}
    limit = data['customer'].get_preferential_credit_limit()
    for endpoint, _ in endpoints(data):
        for parameters in ({}, {'q': 'Пушкин'}, {'q': 'Стрельна'}, {'ordering': 'city'},
                           {'regionLocationId': data['catalog']['strelna'][0].region_id}):
            response = client.get(endpoint, parameters)
            assert response.status_code == 200, response.content
    detail_paths = (
        '/api/v1/mortgage/calculations/',
        '/api/v1/mortgage/trench/calculations/',
    )
    for town, identifiers in data['ids'].items():
        for path, identifier in zip(detail_paths, identifiers):
            response = client.get(f'{path}{identifier}/')
            assert response.status_code == 200
            assert response.json()['property']['localityId'] == data['catalog'][town][0].pk
    assert all(
        list(model.objects.order_by('pk').values()) == snapshot
        for model, snapshot in before.items()
    )
    assert data['customer'].get_preferential_credit_limit() == limit == 12000000


@pytest.mark.django_db
def test_location_filters_preserve_ownership(client, location_calculations):
    """Geographic search must never reveal another user's saved scenarios."""
    data = location_calculations
    other_client = Client()
    other_client.force_login(data['other'])
    other_customer = Customer.objects.create(user=data['other'], first_name='Закрытый расчёт')
    foreign = create_customer_calculations(
        other_client, other_customer, data['catalog']['pushkin'][3],
    )
    for endpoint in ('/api/v1/mortgage/calculations/', '/api/v1/mortgage/trench/calculations/'):
        assert other_client.get(endpoint, {'q': 'Пушкин'}).json()['totalCount'] == 1
        assert client.get(endpoint, {'q': 'Пушкин'}).json()['totalCount'] == 1
    assert client.get(f'/api/v1/customers/{other_customer.pk}/calculations/').status_code == 404
    assert client.get(f'/api/v1/mortgage/calculations/{foreign[0]}/').status_code == 404
    assert client.get(f'/api/v1/mortgage/trench/calculations/{foreign[1]}/').status_code == 404


@pytest.mark.django_db
def test_fallback_pages_search_both_localities_and_keep_customer_links(
    client, location_calculations,
):
    """Render the same geography in native mortgage, tranche and customer tables."""
    data = location_calculations
    paths = (reverse('mortgage:calculation_list'), reverse('mortgage:trench_calculation_list'),
             reverse('customer:detail', kwargs={'pk': data['customer'].pk}))
    for path in paths:
        for town, label in [('pushkin', 'Пушкин'), ('strelna', 'Стрельна')]:
            response = client.get(path, {'legacy': 1, 'localityId': data['catalog'][town][0].pk})
            assert response.status_code == 200
            assert label in response.content.decode()
            assert 'name="localityId"' in response.content.decode()
            assert 'name="regionLocationId"' in response.content.decode()


@pytest.mark.django_db
def test_geographic_history_queries_do_not_grow_per_saved_calculation(
    client, location_calculations,
):
    """Keep canonical ancestry, aliases and customer unions free of N+1 reads."""
    data = location_calculations
    parameters = {
        'q': 'Санкт-Петербург',
        'regionLocationId': data['catalog']['pushkin'][0].region_id,
    }
    counts = {}
    for endpoint, _ in endpoints(data):
        with CaptureQueriesContext(connection) as captured:
            response = client.get(endpoint, parameters)
        assert response.status_code == 200
        counts[endpoint] = len(captured)
        assert counts[endpoint] < 15
    for town in ('pushkin', 'strelna'):
        create_customer_calculations(
            client, data['customer'], data['catalog'][town][3],
        )
    for endpoint, _ in endpoints(data):
        with CaptureQueriesContext(connection) as captured:
            response = client.get(endpoint, parameters)
        assert response.status_code == 200
        assert response.json()['totalCount'] == (8 if 'customers' in endpoint else 4)
        assert len(captured) == counts[endpoint]
