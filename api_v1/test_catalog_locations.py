"""Keep catalog display, geography filtering and ordering on canonical identities."""

import re
from importlib import import_module

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from api_v1.test_location_filters import (  # noqa: F401
    complex_catalog, filtered_catalog, import_user, locality_catalog,
)
from api_v1.test_calculation_locations import location_calculations  # noqa: F401
from api_v1.test_customers import customer_users  # noqa: F401
from bank.models import MortgageProgramRegionalCreditLimit
from customer.models import Customer, CustomerCalculation, CustomerTrenchCalculation
from location.tests.legacy_fixtures import create_legacy_fixture
from location.tests.legacy_fixtures import canonical_legacy_location
from location.tests.legacy_fixtures import historical_geography_schema
from location.tests.legacy_fixtures import legacy_district_for
from location.models import LocationCompatibilityEntry, LocationAlias
from mortgage.models import MortgageCalculation
from property.forms import RealEstateComplexForm
from property.models import Property, RealEstateComplex, RealEstateComplexBuilding, RealEstateComplexLocation
from trench_mortgage.models import Trench, TrenchMortgageCalculation


def catalog_endpoints():
    """Exercise both API catalogs and the actual native page handlers."""
    return (
        ('/api/v1/complexes/', False), ('/api/v1/properties/', True),
        (reverse('property:complex_list'), False), (reverse('property:list'), True),
    )


def catalog_rows(client, path, parameters):
    """Read a native page or a paginated API without hiding request failures."""
    response = client.get(path, {'legacy': 1, **parameters})
    assert response.status_code == 200, response.content
    if path.startswith('/api/'):
        return response.json()['results']
    return list(response.context['page_obj'])


@pytest.mark.django_db
def test_catalog_sorting_and_scope_filters_before_pagination(client, filtered_catalog):
    """Order by Pushkin/Strelna even when project names and old districts disagree."""
    for town in ('pushkin', 'strelna'):
        LocationAlias.objects.create(location=filtered_catalog[town][0], name='Сверка пригородов')
    for path, properties in catalog_endpoints():
        native = not path.startswith('/api/')
        for town in ('pushkin', 'strelna'):
            location, project, _, apartment = filtered_catalog[town]
            for scopes in (
                {'localityId': location.pk}, {'districtLocationId': location.parent_id},
                {'regionLocationId': location.region_id, 'districtLocationId': location.parent_id, 'localityId': location.pk},
            ):
                rows = catalog_rows(client, path, scopes)
                identifiers = {row.pk if native else row['id'] for row in rows}
                assert identifiers == {apartment.pk if properties else project.pk}
                row, = rows
                assert (row.geographic_locality_name if native else row['city']) == location.name
                assert (row.geographic_district_id if native else row['districtLocationId']) == location.parent_id
            conflict = catalog_rows(client, path, {
                'localityId': location.pk,
                'districtLocationId': filtered_catalog['strelna' if town == 'pushkin' else 'pushkin'][0].parent_id,
            })
            assert not conflict
        for descending in (False, True):
            parameters = {'search': 'Сверка пригородов', 'ordering': '-city' if descending else 'city',
                          'sort_by': 'city', 'sort_dir': 'desc' if descending else 'asc'}
            rows = catalog_rows(client, path, parameters)
            assert [row.geographic_locality_name if native else row['city'] for row in rows] == (
                ['Стрельна', 'Пушкин'] if descending else ['Пушкин', 'Стрельна']
            )
            if not native:
                page = client.get(path, {**parameters, 'pageSize': 1, 'page': 2}).json()
                assert page['results'][0]['city'] == ('Пушкин' if descending else 'Стрельна')


@pytest.mark.django_db
def test_old_city_urls_map_to_canonical_territory_without_numeric_id_confusion(client, filtered_catalog):
    """Keep old federal-city filters inclusive of suburbs while respecting overrides."""
    pushkin, project, _, _ = filtered_catalog['pushkin']
    root_city = create_legacy_fixture('city', pk=900000, name='Санкт-Петербург', location=pushkin.region,
                                      region=legacy_district_for(filtered_catalog['legacy']).city.region)
    for path, _ in catalog_endpoints():
        key = 'city' if path == '/api/v1/properties/' else 'cityId' if path.startswith('/api/') else 'filter_city'
        rows = catalog_rows(client, path, {key: root_city.pk})
        names = {row['city'] if path.startswith('/api/') else row.geographic_locality_name for row in rows}
        assert {'Пушкин', 'Стрельна'} <= names
        assert not catalog_rows(client, path, {key: pushkin.pk})
        assert not catalog_rows(client, path, {key: root_city.pk, 'localityId': 999999999})
    project.district_id = legacy_district_for(filtered_catalog['legacy']).pk
    project.save()
    old_city = legacy_district_for(project).city_id
    assert project.pk not in {row['id'] for row in catalog_rows(client, '/api/v1/complexes/', {'cityId': old_city})}


@pytest.mark.django_db
def test_complex_coverage_and_apartment_building_override_are_distinct(client, filtered_catalog):
    """A complex covers multiple current territories; each apartment has one point."""
    pushkin, project, building, apartment = filtered_catalog['pushkin']
    strelna = filtered_catalog['strelna'][0]
    secondary = RealEstateComplexLocation.objects.create(real_estate_complex=project, location=strelna)
    for path, properties in catalog_endpoints():
        rows = catalog_rows(client, path, {'localityId': strelna.pk})
        identifiers = {row['id'] if path.startswith('/api/') else row.pk for row in rows}
        if properties:
            assert apartment.pk not in identifiers
        else:
            assert project.pk in identifiers
    secondary.is_historical = True
    secondary.save()
    assert project.pk not in {row['id'] for row in catalog_rows(client, '/api/v1/complexes/', {'localityId': strelna.pk})}
    building.complex_location = secondary
    building.save()
    assert project.pk in {row['id'] for row in catalog_rows(client, '/api/v1/complexes/', {'localityId': strelna.pk})}
    for path, properties in catalog_endpoints():
        rows = catalog_rows(client, path, {'localityId': strelna.pk})
        row = next(row for row in rows if (row['id'] if path.startswith('/api/') else row.pk) == (apartment.pk if properties else project.pk))
        assert (row['city'] if path.startswith('/api/') else row.geographic_locality_name) == ('Стрельна' if properties else 'Пушкин')
        assert not catalog_rows(client, path, {'localityId': strelna.pk, 'districtLocationId': pushkin.parent_id})


@pytest.mark.django_db
def test_catalog_reads_keep_finances_customers_and_all_original_fields(client, location_calculations):
    """Compare original rows and associations after native/API searches and sorts."""
    models = (LocationCompatibilityEntry, RealEstateComplex, RealEstateComplexLocation,
              RealEstateComplexBuilding, Property, Customer, CustomerCalculation,
              CustomerTrenchCalculation, MortgageCalculation, TrenchMortgageCalculation,
              Trench, MortgageProgramRegionalCreditLimit)
    before = {model: list(model.objects.order_by('pk').values()) for model in models}
    data = location_calculations
    for path, _ in catalog_endpoints():
        for parameters in ({'search': 'Пушкин'}, {'search': 'Стрельна'},
                           {'localityId': data['catalog']['strelna'][0].pk},
                           {'ordering': 'city', 'sort_by': 'city'}):
            catalog_rows(client, path, parameters)
    assert all(list(model.objects.order_by('pk').values()) == rows for model, rows in before.items())
    assert data['customer'].get_preferential_credit_limit() == 12000000


@pytest.mark.django_db
def test_native_selectors_are_bounded_and_queries_do_not_grow_per_result(client, filtered_catalog):
    """Keep the HTML and query count bounded when apartment history grows."""
    counts = {}
    for path, _ in catalog_endpoints():
        with CaptureQueriesContext(connection) as captured:
            rows = catalog_rows(client, path, {})
        counts[path] = len(captured)
        assert counts[path] < 20
    original = filtered_catalog['pushkin'][3]
    for number in range(25):
        Property.objects.create(building=original.building, apartment_number=f'Доп-{number}',
                                area=original.area, floor=original.floor, property_cost=original.property_cost,
                                layout=original.layout, decoration=original.decoration)
    for path, _ in catalog_endpoints():
        with CaptureQueriesContext(connection) as captured:
            catalog_rows(client, path, {})
        assert len(captured) == counts[path]
    response = client.get(reverse('property:list'), {'legacy': 1, 'localityId': filtered_catalog['pushkin'][0].pk})
    assert response.content.count(b'data-remote-options=') >= 5
    assert b'data-catalog-clear-on=' in response.content
    assert 'Стрельна' not in response.content.decode()


@pytest.mark.django_db
def test_current_geography_reads_do_not_join_the_legacy_catalogs(client, filtered_catalog):
    """Check bounded canonical reads, including a coarse complex and a legacy URL."""
    locality, project, building, apartment = filtered_catalog['pushkin']
    coarse = filtered_catalog['legacy']
    legacy_city_id = legacy_district_for(coarse).city_id
    endpoints = (
        ('/api/v1/complexes/', {'cityId': legacy_city_id, 'ordering': 'city'}),
        (f'/api/v1/complexes/{coarse.pk}/', {}),
        ('/api/v1/properties/', {'localityId': locality.pk, 'search': 'Пушкин'}),
        (f'/api/v1/properties/{apartment.pk}/', {}),
        ('/api/v1/catalog-options/complexes/', {'cityId': legacy_city_id, 'selected': project.pk}),
        ('/api/v1/catalog-options/buildings/', {'selected': building.pk}),
        ('/api/v1/homepage/complexes/', {'canonicalLocations': 'true', 'allLocations': 'true'}),
        ('/api/v1/overview/', {'canonicalLocations': 'true'}),
        ('/api/complexes/', {'city_id': legacy_city_id}),
    )
    for endpoint, parameters in endpoints:
        with CaptureQueriesContext(connection) as captured:
            response = client.get(endpoint, parameters)
        assert response.status_code == 200, response.content
        assert not any(re.search(r'\b(?:FROM|JOIN) "(?:district|city|region)"', query['sql'])
                       for query in captured.captured_queries), endpoint


@pytest.mark.django_db(transaction=True)
def test_legacy_district_ancestry_and_missing_primary_keep_old_identifiers(client, filtered_catalog):
    """Keep original IDs when a coarse primary is displayed with current labels."""
    project = filtered_catalog['legacy']
    district = legacy_district_for(project)
    mapping = LocationCompatibilityEntry.objects.get(model_name='district', legacy_id=district.pk)
    district_mapping = LocationCompatibilityEntry.objects.filter(pk=mapping.pk)
    migration = import_module('location.migrations.0014_legacy_district_ancestry')
    before = list(project.location_links.values())
    with historical_geography_schema() as historic:
        district_mapping.update(legacy_city_id=None, legacy_region_id=None)
        with connection.schema_editor() as editor:
            for _ in range(2):
                migration.capture_legacy_district_ancestry(historic, editor)
    assert list(project.location_links.values()) == before
    mapping.refresh_from_db()
    assert (mapping.legacy_city_id, mapping.legacy_region_id) == (district.city_id, district.city.region_id)
    location = mapping.location
    location.name = 'Уточнённое название района'
    location.save(update_fields=['name'])
    detail = f'/api/v1/complexes/{project.pk}/'
    for has_primary in (True, False):
        if not has_primary:
            project.location_links.all().delete()
        payload = client.get(detail).json()
        assert payload['district'] == location.name
        assert payload['districtLocationId'] == location.pk
        assert (payload['districtId'], payload['cityId'], payload['regionId']) == (
            district.pk, district.city_id, district.city.region_id,
        )


@pytest.mark.django_db
@pytest.mark.parametrize('native_form', [False, True])
def test_legacy_district_edit_moves_only_coarse_binding(client, filtered_catalog, native_form):
    """Keep the old request key, preserve history and retain a precise locality."""
    project = filtered_catalog['legacy']
    building = project.realestatecomplexbuilding_set.get()
    previous = project.location_links.get(is_primary=True)
    building.complex_location = previous
    building.save(update_fields=['complex_location'])
    new_district = create_legacy_fixture('district', name='Другой район', city=legacy_district_for(project).city)
    canonical_legacy_location(new_district)
    url = f'/api/v1/complexes/{project.pk}/'
    if native_form:
        form = RealEstateComplexForm(data={
            'name': project.name, 'developer': project.developer_id, 'district': new_district.pk,
            'real_estate_class': project.real_estate_class_id, 'real_estate_type': project.real_estate_type_id,
        }, instance=project)
        assert form.is_valid(), form.errors
        form.save()
        response = client.get(url)
    else:
        response = client.patch(url, {'districtId': new_district.pk}, content_type='application/json')
    assert response.status_code == 200, response.content
    assert response.json()['district'] == new_district.name
    previous.refresh_from_db()
    building.refresh_from_db()
    assert previous.is_historical and building.complex_location_id == previous.pk

    locality, precise, _, _ = filtered_catalog['strelna']
    response = client.patch(f'/api/v1/complexes/{precise.pk}/', {'districtId': new_district.pk},
                            content_type='application/json')
    assert response.status_code == 200, response.content
    assert response.json()['districtId'] == new_district.pk
    assert response.json()['localityId'] == locality.pk
