"""Verify canonical dictionaries, protected identities and geographic tree writes."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from api_v1.test_location_filters import (  # noqa: F401
    complex_catalog, filtered_catalog, import_user, locality_catalog,
)
from api_v1.test_calculation_locations import location_calculations  # noqa: F401
from api_v1.test_customers import customer_users  # noqa: F401
from location.tests.legacy_fixtures import create_legacy_fixture
from location.tests.legacy_fixtures import legacy_district_for
from location.catalog_service import save_catalog_location
from location.gar_import import load_region
from location.models import LocationCompatibilityEntry, Location, LocationAlias, LocationClosure, LocationIdentifier, LocationType
from location.tests.test_gar import SPB
from property.models import RealEstateComplexLocation
from mortgage.models import MortgageCalculation
from trench_mortgage.models import Trench, TrenchMortgageCalculation
from customer.models import Customer, CustomerCalculation, CustomerTrenchCalculation
from bank.models import MortgageProgramRegionalCreditLimit


def catalog_user(role):
    """Use distinct accounts alongside the imported geographic fixture's moderator."""
    if role == 'anonymous':
        return None
    roles = ['regular', 'staff', 'moderator', 'administrator', 'superuser']
    user, _ = get_user_model().objects.get_or_create(
        email=f'{role}@canonical-catalog.invalid', defaults={
            'phone_number': f'+7999000960{roles.index(role)}',
            'is_staff': role == 'staff', 'is_superuser': role == 'superuser',
        },
    )
    group_name = {'moderator': 'moderators', 'administrator': 'application_administrators'}.get(role)
    if group_name:
        user.groups.add(Group.objects.get_or_create(name=group_name)[0])
    return user


def endpoint(key, identifier=None):
    """Use a namespace whose IDs always identify Location."""
    return f'/api/v1/location-catalogs/{key}/' + (f'{identifier}/' if identifier else '')


@pytest.mark.django_db
def test_canonical_lists_search_scope_sort_page_and_aliases(client, filtered_catalog):
    """Expose Pushkin and Strelna with their actual administrative parents."""
    for town in ('pushkin', 'strelna'):
        location = filtered_catalog[town][0]
        LocationAlias.objects.create(location=location, name=f'Прежнее {location.name}')
        response = client.get(endpoint('localities'), {
            'q': location.name, 'regionId': location.region_id,
            'ancestorId': location.parent_id, 'typeId': location.location_type_id,
        })
        assert response.status_code == 200
        row, = response.json()['results']
        assert row['id'] == location.pk
        assert row['parent'] == location.parent.name
        assert row['region'] == 'Санкт-Петербург'
        assert row['typeId'] == location.location_type_id
        assert client.get(endpoint('localities'), {'q': f'Прежнее {location.name}'}).json()['totalCount'] == 1
        assert client.get(endpoint('districts'), {'q': location.parent.name}).json()['results'][0]['id'] == location.parent_id
    mismatch = client.get(endpoint('localities'), {
        'q': 'Стрельна', 'ancestorId': filtered_catalog['pushkin'][0].parent_id,
    })
    assert mismatch.json()['totalCount'] == 0
    response = client.get(endpoint('localities'), {'q': 'Прежнее', 'pageSize': 1, 'ordering': '-name'})
    assert response.json()['results'][0]['name'] == 'Стрельна'
    assert response.json()['totalPages'] > 1
    assert client.get(endpoint('regions')).json()['totalCount'] >= 1
    assert client.get(endpoint('localities'), {'regionId': 'bad'}).status_code == 400
    assert client.get(endpoint('municipalities')).status_code == 404


@pytest.mark.django_db
def test_manual_create_all_levels_and_delete_unused_without_legacy_rows(client, filtered_catalog):
    """Build region, district, town, village and rural locality in the new graph only."""
    old_count = LocationCompatibilityEntry.objects.count()
    created = []
    parent = None
    for key, category, name in (
        ('regions', 'region', 'Тестовый субъект'), ('districts', 'district', 'Тестовый район'),
        ('localities', 'locality', 'Тестовый город'),
    ):
        location_type = LocationType.objects.filter(category=category).first()
        response = client.post(endpoint(key), {
            'name': name, 'typeId': location_type.pk, 'parentId': parent,
        }, content_type='application/json')
        assert response.status_code == 201, response.content
        created.append(response.json()['id'])
        parent = created[-1]
    root, district, town = created
    for name, abbreviation in (('Село', 'с.'), ('Деревня', 'д.')):
        location_type = LocationType.objects.create(code=f'test:{abbreviation}', category='locality', name=name)
        response = client.post(endpoint('localities'), {
            'name': f'Тестовая {name}', 'typeId': location_type.pk, 'parentId': town,
        }, content_type='application/json')
        assert response.status_code == 201, response.content
        identifier = response.json()['id']
        assert LocationClosure.objects.get(ancestor_id=root, descendant_id=identifier).depth == 3
        assert Location.objects.get(pk=identifier).region_id == root
        assert client.delete(endpoint('localities', identifier)).status_code == 204
    assert client.delete(endpoint('regions', root)).status_code == 409
    assert Location.objects.get(pk=root).region_id == root
    for key, identifier in (('localities', town), ('districts', district), ('regions', root)):
        assert client.delete(endpoint(key, identifier)).status_code == 204
    assert old_count == LocationCompatibilityEntry.objects.count()


@pytest.mark.django_db
def test_rename_preserves_source_business_financial_rows_and_repeat_import(client, location_calculations, import_user):
    """Retain every financial value and association through a canonical rename and reload."""
    data = location_calculations
    client.force_login(catalog_user('moderator'))
    location = data['catalog']['strelna'][0]
    models = (MortgageCalculation, TrenchMortgageCalculation, Trench, Customer,
              CustomerCalculation, CustomerTrenchCalculation, MortgageProgramRegionalCreditLimit,
              RealEstateComplexLocation, LocationCompatibilityEntry)
    before = {model: list(model.objects.order_by('pk').values()) for model in models}
    identities = list(location.identifiers.order_by('pk').values())
    response = client.patch(endpoint('localities', location.pk), {
        'name': 'Стрельна тест', 'isActive': False, 'sourceVersion': 'overwrite-denied',
    }, content_type='application/json')
    assert response.status_code == 200, response.content
    assert response.json()['id'] == location.pk
    assert client.get(endpoint('localities'), {'q': 'Стрельна тест', 'status': 'inactive'}).json()['totalCount'] == 1
    assert client.delete(endpoint('localities', location.pk)).status_code == 409
    assert list(location.identifiers.order_by('pk').values()) == identities
    load_region(SPB, '78', '20261113')
    counts = load_region(SPB, '78', '20261113')
    assert all(not counts[key]['created'] and not counts[key]['updated'] for key in counts)
    location.refresh_from_db()
    assert location.name == 'Стрельна'
    assert location.source_version == '20261113'
    assert LocationAlias.objects.filter(location=location, name='Стрельна тест').exists()
    assert all(list(model.objects.order_by('pk').values()) == rows for model, rows in before.items())
    assert data['customer'].get_preferential_credit_limit() == 12000000


@pytest.mark.django_db
def test_move_subtree_rebuilds_only_external_ancestry_and_rejects_cycles(client, filtered_catalog):
    """Move actual location IDs while preserving internal paths and complex links."""
    pushkin, project, _, _ = filtered_catalog['pushkin']
    strelna = filtered_catalog['strelna'][0]
    child = save_catalog_location('locality', {
        'name': 'Дочерний посёлок', 'location_type': pushkin.location_type, 'parent': pushkin,
    })
    binding = project.location_links.get(is_primary=True).pk
    response = client.patch(endpoint('localities', pushkin.pk), {'parentId': strelna.parent_id}, content_type='application/json')
    assert response.status_code == 200, response.content
    assert not LocationClosure.objects.filter(ancestor_id=pushkin.parent_id, descendant=child).exists()
    assert LocationClosure.objects.get(ancestor_id=strelna.parent_id, descendant=child).depth == 2
    assert LocationClosure.objects.get(ancestor=pushkin, descendant=child).depth == 1
    assert project.location_links.get(is_primary=True).pk == binding
    before = list(LocationClosure.objects.order_by('pk').values())
    response = client.patch(endpoint('localities', pushkin.pk), {'parentId': child.pk}, content_type='application/json')
    assert response.status_code == 400
    assert list(LocationClosure.objects.order_by('pk').values()) == before
    assert client.patch(endpoint('localities', pushkin.pk), {'typeId': strelna.parent.location_type_id}, content_type='application/json').status_code == 400
    assert client.patch(endpoint('regions', pushkin.region_id), {'parentId': child.pk}, content_type='application/json').status_code == 400

    other_region = save_catalog_location('region', {
        'name': 'Другой субъект', 'location_type': pushkin.region.location_type,
    })
    other_district = save_catalog_location('district', {
        'name': 'Другой район', 'location_type': strelna.parent.location_type,
        'parent': other_region,
    })
    moved = client.patch(endpoint('localities', pushkin.pk), {
        'parentId': other_district.pk,
    }, content_type='application/json')
    assert moved.status_code == 200
    child.refresh_from_db()
    assert child.region_id == other_region.pk
    assert not LocationClosure.objects.filter(ancestor_id=pushkin.region_id, descendant=child).exists()
    assert LocationClosure.objects.get(ancestor=other_region, descendant=child).depth == 3
    assert project.location_links.get(is_primary=True).pk == binding


@pytest.mark.django_db
def test_used_manual_territory_cannot_be_deleted(client, filtered_catalog):
    """Protect real estate links even when a location has no source identifiers."""
    source, project, _, _ = filtered_catalog['strelna']
    manual = save_catalog_location('locality', {
        'name': 'Ручная территория ЖК', 'location_type': source.location_type,
        'parent': source.parent,
    })
    binding = RealEstateComplexLocation.objects.create(real_estate_complex=project, location=manual)
    assert client.delete(endpoint('localities', manual.pk)).status_code == 409
    assert RealEstateComplexLocation.objects.filter(pk=binding.pk, location=manual).exists()


@pytest.mark.django_db
@pytest.mark.parametrize('role', ['anonymous', 'regular', 'staff', 'moderator', 'administrator', 'superuser'])
def test_dictionary_permissions_keep_import_separate(client, import_user, filtered_catalog, role):
    """Allow public reads, manager writes and administrator-only national imports."""
    client.logout()
    user = catalog_user(role)
    if user:
        client.force_login(user)
    location = filtered_catalog['pushkin'][0]
    assert client.get(endpoint('localities')).status_code == 200
    response = client.patch(endpoint('localities', location.pk), {'name': location.name}, content_type='application/json')
    assert response.status_code == (200 if role in ('moderator', 'administrator', 'superuser') else 403)
    if role == 'moderator':
        assert client.post('/api/v1/location-imports/', {}, content_type='application/json').status_code == 403


@pytest.mark.django_db
def test_csrf_legacy_links_native_forms_and_bounded_queries(client, filtered_catalog, import_user):
    """Share canonical behavior with fallback pages and translate old edit IDs explicitly."""
    location = filtered_catalog['pushkin'][0]
    protected = Client(enforce_csrf_checks=True)
    protected.force_login(catalog_user('moderator'))
    assert protected.patch(endpoint('localities', location.pk), {'name': 'CSRF'}, content_type='application/json').status_code == 403
    legacy = create_legacy_fixture('city', name='Прежний Пушкин', location=location,
                                   region=legacy_district_for(filtered_catalog['legacy']).city.region, pk=900000)
    assert client.get(endpoint('localities', legacy.pk), {'legacy': 1}).json()['id'] == location.pk
    assert client.get(endpoint('localities', legacy.pk)).status_code == 404
    for model, search in [('region', 'Санкт-Петербург'), ('district', 'Пушкинский'), ('locality', 'Пушкин'), ('city', 'Стрельна')]:
        response = client.get('/locations/', {'model': model, 'legacy': 1, 'q': search})
        assert response.status_code == 200, response.content
        assert search in response.content.decode()
    saved = client.post(f'/locations/?model=locality&legacy=1&locationId={location.pk}', {
        'name': location.name, 'typeId': location.location_type_id,
        'parentId': location.parent_id, 'isActive': True,
    })
    assert saved.status_code == 302
    from django.http import QueryDict
    from react_frontend.middleware import build_react_frontend_url
    target = build_react_frontend_url('location:location_catalog', {}, QueryDict(
        f'model=locality&locationId={location.pk}',
    ))
    assert target == f'/app/locations/localities/?editLocationId={location.pk}'
    assert client.get('/locations/', {'legacy': 1, 'locationId': 'bad'}).status_code == 404
    with CaptureQueriesContext(connection) as captured:
        response = client.get(endpoint('localities'), {'pageSize': 100})
    assert response.status_code == 200 and len(captured) <= 5
