"""Exercise canonical scope filtering, historic bindings and building overrides."""

from importlib import import_module

import pytest
from django.apps import apps
from django.db import connection
from django.test import Client

from api_v1.test_complex_localities import locality_catalog
from api_v1.test_location_import import import_user
from api_v1.test_real_estate_complexes import complex_catalog
from api_v1.serializers import ManualCalculationPropertySerializer
from location.compatibility import canonical_legacy_location
from location.models import City, LegacyLocationMapping, Location, LocationClosure
from property.location_context import set_primary_location
from property.models import (
    ApartmentDecoration, ApartmentLayout, Property, RealEstateComplex,
    RealEstateComplexBuilding, RealEstateComplexLocation,
)


@pytest.fixture
def filtered_catalog(locality_catalog):
    """Build separate Pushkin/Strelna projects with real geographic identities."""
    original = locality_catalog['complex']
    result = {'legacy': original}
    for key, name in [('strelna', 'Стрельна'), ('pushkin', 'Пушкин')]:
        locality = Location.objects.get(name=name)
        project = RealEstateComplex.objects.create(
            name='Veren Village' if key == 'strelna' else 'Пушкинский квартал',
            developer=original.developer, real_estate_class=original.real_estate_class,
            real_estate_type=original.real_estate_type,
        )
        set_primary_location(project, locality)
        building = RealEstateComplexBuilding.objects.create(real_estate_complex=project, number='1')
        apartment = Property.objects.create(
            building=building, apartment_number='1', area=50, floor=1, property_cost=5000000,
            layout=ApartmentLayout.objects.get_or_create(name='Студия')[0],
            decoration=ApartmentDecoration.objects.get_or_create(name='Без отделки')[0],
        )
        result[key] = (locality, project, building, apartment)
    return result


def result_ids(client, endpoint, parameters):
    """Read bounded public results and expose validation errors in failures."""
    response = client.get(endpoint, parameters)
    assert response.status_code == 200, response.content
    return {row['id'] for row in response.json()['results']}


@pytest.mark.django_db
def test_manual_calculation_checks_location_against_the_building(filtered_catalog):
    """Accept the new scopes and reject a same-region locality mismatch."""
    locality, project, building, apartment = filtered_catalog['pushkin']
    payload = {
        'regionLocationId': locality.region_id,
        'districtLocationId': locality.parent_id,
        'localityId': locality.pk,
        'developerId': project.developer_id,
        'realEstateComplexId': project.pk,
        'buildingId': building.pk,
        'apartmentNumber': '42',
        'area': '50.00',
        'floor': 1,
        'layoutId': apartment.layout_id,
        'decorationId': apartment.decoration_id,
    }
    serializer = ManualCalculationPropertySerializer(data=payload)
    assert serializer.is_valid(), serializer.errors
    assert serializer.validated_data['OBJECT_BUILDING'] == building
    serializer = ManualCalculationPropertySerializer(data={
        **payload, 'localityId': filtered_catalog['strelna'][0].pk,
    })
    assert not serializer.is_valid()


@pytest.mark.django_db
def test_veren_village_matches_region_district_and_settlement(filtered_catalog):
    """Saint Petersburg includes both suburbs; each district/locality separates them."""
    client = Client()
    strelna, veren, _, apartment = filtered_catalog['strelna']
    pushkin, other, _, other_apartment = filtered_catalog['pushkin']
    for field, scope, wanted, excluded in [
        ('regionLocationId', strelna.region_id, {veren.pk, other.pk}, set()),
        ('districtLocationId', strelna.parent_id, {veren.pk}, {other.pk}),
        ('localityId', strelna.pk, {veren.pk}, {other.pk}),
        ('localityId', pushkin.pk, {other.pk}, {veren.pk}),
    ]:
        identifiers = result_ids(client, '/api/v1/complexes/', {field: scope})
        assert wanted <= identifiers and not excluded & identifiers
    assert result_ids(client, '/api/v1/properties/', {'localityId': strelna.pk}) == {apartment.pk}
    assert result_ids(client, '/api/v1/properties/', {'localityId': pushkin.pk}) == {other_apartment.pk}
    assert result_ids(client, '/api/v1/homepage/complexes/', {'districtLocationId': strelna.parent_id}) == {veren.pk}
    assert veren.pk in result_ids(client, '/api/v1/catalog-options/complexes/', {'localityId': strelna.pk})


@pytest.mark.django_db
def test_homepage_map_labels_and_legacy_city_link(client, filtered_catalog):
    """Use only the requested locality for the map and retain the old response contract."""
    url = '/api/v1/homepage/complexes/'
    for key in ('pushkin', 'strelna'):
        locality, project, _, _ = filtered_catalog[key]
        response = client.get(url, {
            'canonicalLocations': 'true', 'regionLocationId': locality.region_id, 'localityId': locality.pk,
        })
        assert response.status_code == 200
        data = response.json()
        assert data['territoryLabel'] == locality.name
        row, = data['results']
        assert row['id'] == project.pk
        assert row['locationLabel'] == f'{locality.name}, {locality.parent.name}, Санкт-Петербург'

    locality, project, _, _ = filtered_catalog['pushkin']
    old_city = City.objects.create(name='Пушкин', region=filtered_catalog['legacy'].district.city.region)
    LegacyLocationMapping.objects.create(model_name='city', legacy_id=old_city.pk, location=locality)
    canonical_legacy_location(old_city)
    data = client.get(url, {'canonicalLocations': 'true', 'city': old_city.pk}).json()
    assert data['territoryLabel'] == 'Пушкин'
    assert [row['id'] for row in data['results']] == [project.pk]
    legacy = client.get(url, {'city': old_city.pk}).json()
    assert legacy['selectedCity'] == {'id': old_city.pk, 'name': 'Пушкин'}
    assert 'territoryLabel' not in legacy
    assert 'locationLabel' not in legacy['results'][0]


@pytest.mark.django_db
def test_overview_counts_active_localities_without_legacy_cities(client, filtered_catalog):
    """Count GAR villages, exclude inactive entries and preserve the old statistic."""
    locality = filtered_catalog['strelna'][0]
    endpoint = '/api/v1/overview/'
    parameters = {'canonicalLocations': 'true'}
    legacy = client.get(endpoint).json()
    assert any(stat['key'] == 'cities' for stat in legacy['statistics'])

    def locality_count():
        """Read the active locality statistic from the public canonical overview."""
        statistics = client.get(endpoint, parameters).json()['statistics']
        assert all(stat['key'] != 'cities' for stat in statistics)
        return next(stat['value'] for stat in statistics if stat['label'] == 'Населённые пункты')

    initial = locality_count()
    village = Location.objects.create(
        name='Тестовая деревня', location_type=locality.location_type,
        parent=locality.parent, region=locality.region,
    )
    assert locality_count() == initial + 1
    village.is_active = False
    village.save(update_fields=['is_active'])
    assert locality_count() == initial
    assert client.get(endpoint).json()['statistics'] == legacy['statistics']


@pytest.mark.django_db
def test_old_location_does_not_match_after_move_but_override_remains_effective(filtered_catalog):
    """An old binding is retained as history, until a building explicitly uses it."""
    client = Client()
    strelna, _, _, _ = filtered_catalog['strelna']
    pushkin, project, building, apartment = filtered_catalog['pushkin']
    previous = project.location_links.get(is_primary=True)
    set_primary_location(project, strelna)
    previous.refresh_from_db()
    assert previous.is_historical and not previous.is_primary
    assert project.pk not in result_ids(client, '/api/v1/complexes/', {'localityId': pushkin.pk})
    assert apartment.pk not in result_ids(client, '/api/v1/properties/', {'localityId': pushkin.pk})
    building.complex_location = previous
    building.save(update_fields=['complex_location'])
    assert project.pk in result_ids(client, '/api/v1/complexes/', {'localityId': pushkin.pk})
    assert apartment.pk in result_ids(client, '/api/v1/properties/', {'localityId': pushkin.pk})
    assert apartment.pk not in result_ids(client, '/api/v1/properties/', {'localityId': strelna.pk})
    assert building.pk in result_ids(client, '/api/v1/catalog-options/buildings/', {'localityId': pushkin.pk})


@pytest.mark.django_db
def test_multiple_territories_do_not_satisfy_incompatible_scopes(filtered_catalog):
    """Intersect filters on the same territory rather than different project links."""
    client = Client()
    strelna, _, _, _ = filtered_catalog['strelna']
    pushkin, project, _, _ = filtered_catalog['pushkin']
    RealEstateComplexLocation.objects.create(real_estate_complex=project, location=strelna)
    assert project.pk in result_ids(client, '/api/v1/complexes/', {'localityId': strelna.pk})
    assert not result_ids(client, '/api/v1/complexes/', {
        'districtLocationId': pushkin.parent_id, 'localityId': strelna.pk,
    })


@pytest.mark.django_db
def test_filters_remain_bounded_and_locality_options_follow_both_hierarchy_directions(filtered_catalog, django_assert_num_queries):
    """Preserve fixed query counts and federal-city/locality roles in selectors."""
    client = Client()
    strelna, veren, _, _ = filtered_catalog['strelna']
    with django_assert_num_queries(5):
        assert result_ids(client, '/api/v1/complexes/', {'localityId': strelna.pk}) == {veren.pk}
    options = result_ids(client, '/api/v1/locations/', {'category': 'locality', 'relatedToId': strelna.parent_id})
    assert strelna.pk in options and strelna.region_id in options
    assert strelna.parent_id in result_ids(client, '/api/v1/locations/', {'category': 'district', 'relatedToId': strelna.pk})


@pytest.mark.django_db
def test_historical_state_is_editable_but_primary_cannot_be_historical(client, filtered_catalog):
    """Managers may reactivate an old territory while invalid primary state is rejected."""
    strelna, _, _, _ = filtered_catalog['strelna']
    pushkin, project, _, _ = filtered_catalog['pushkin']
    set_primary_location(project, strelna)
    url = f'/api/v1/complexes/{project.pk}/locations/'
    payload = {'locations': [
        {'locationId': strelna.pk, 'isPrimary': True, 'isHistorical': True},
        {'locationId': pushkin.pk, 'isPrimary': False, 'isHistorical': False},
    ]}
    assert client.put(url, payload, content_type='application/json').status_code == 400
    payload['locations'][0]['isHistorical'] = False
    assert client.put(url, payload, content_type='application/json').status_code == 200
    assert project.pk in result_ids(client, '/api/v1/complexes/', {'localityId': pushkin.pk})


@pytest.mark.django_db
def test_homonymous_localities_are_filtered_by_identity(filtered_catalog):
    """Keep equally named settlements in separate administrative districts."""
    strelna, veren, _, _ = filtered_catalog['strelna']
    pushkin, project, _, _ = filtered_catalog['pushkin']
    homonym = Location.objects.create(
        name=strelna.name, location_type=strelna.location_type,
        parent=pushkin.parent, region=pushkin.region,
    )
    LocationClosure.objects.bulk_create([
        LocationClosure(ancestor=homonym, descendant=homonym, depth=0),
        *[LocationClosure(ancestor_id=row.ancestor_id, descendant=homonym, depth=row.depth + 1)
          for row in pushkin.parent.ancestor_links.all()],
    ])
    set_primary_location(project, homonym)
    client = Client()
    assert result_ids(client, '/api/v1/complexes/', {'localityId': strelna.pk}) == {veren.pk}
    assert result_ids(client, '/api/v1/complexes/', {'localityId': homonym.pk}) == {project.pk}
    assert project.pk not in result_ids(client, '/api/v1/complexes/', {'districtLocationId': strelna.parent_id})


@pytest.mark.django_db
def test_migration_marks_only_legacy_snapshots_and_preserves_building_links(filtered_catalog):
    """Migrate existing secondary district bindings without removing any reference."""
    project = filtered_catalog['legacy']
    old = project.location_links.get(is_primary=True)
    strelna = filtered_catalog['strelna'][0]
    set_primary_location(project, strelna)
    old.is_historical = False
    old.save(update_fields=['is_historical'])
    other = RealEstateComplexLocation.objects.create(
        real_estate_complex=project, location=filtered_catalog['pushkin'][0],
    )
    building = project.realestatecomplexbuilding_set.first()
    building.complex_location = old
    building.save(update_fields=['complex_location'])
    migration = import_module('property.migrations.0019_realestatecomplexlocation_is_historical_and_more')
    with connection.schema_editor() as editor:
        migration.preserve_legacy_snapshots(apps, editor)
        migration.preserve_legacy_snapshots(apps, editor)
    old.refresh_from_db()
    other.refresh_from_db()
    building.refresh_from_db()
    assert old.is_historical and not other.is_historical
    assert building.complex_location_id == old.pk
    assert project.location_links.count() == 3
