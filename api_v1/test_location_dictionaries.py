from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.db import connection, connections
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from rest_framework.fields import DateTimeField

from location.compatibility import canonical_legacy_location
from location.models import City, District, LegacyLocationMapping, Location, LocationIdentifier, LocationType, Metro, MetroLine, Region
from users.roles import MODERATOR_GROUP_NAME


@pytest.fixture
def location_dictionary_catalog():
    """Create a representative hierarchy for every location dictionary."""
    region = Region.objects.create(name='Москва', code='77')
    city = City.objects.create(name='Москва', region=region)
    district = District.objects.create(name='Центральный', city=city)
    metro_line = MetroLine.objects.create(
        line='Сокольническая',
        line_color='#D92B2B',
        city=city,
    )
    metro = Metro.objects.create(
        station='Охотный Ряд',
        metro_line=metro_line,
    )
    second_region = Region.objects.create(
        name='Санкт-Петербург',
        code='78',
        is_active=False,
    )
    second_city = City.objects.create(
        name='Санкт-Петербург',
        region=second_region,
    )
    second_line = MetroLine.objects.create(
        line='Невско-Василеостровская',
        line_color='#2384C6',
        city=second_city,
    )
    Metro.objects.create(station='Гостиный двор', metro_line=second_line)
    canonical_legacy_location(district)
    canonical_legacy_location(second_city)
    return {
        'regions': region,
        'cities': city,
        'districts': district,
        'metro': metro,
        'metro_line': metro_line,
        'second_region': second_region,
        'second_city': second_city,
        'second_line': second_line,
    }


def create_location_manager():
    """Create a user allowed to mutate shared location dictionaries."""
    user = get_user_model().objects.create_user(
        email='location-moderator@example.com',
        password='safe-test-password',
        phone_number='+79990000211',
    )
    moderator_group, _ = Group.objects.get_or_create(
        name=MODERATOR_GROUP_NAME
    )
    user.groups.add(moderator_group)
    return user


@pytest.mark.django_db
def test_old_region_api_refreshes_import_reference_and_keeps_location(client):
    """Keep a stable canonical identity when a legacy region is written or removed."""
    client.force_login(create_location_manager())
    region_type = LocationType.objects.create(code='test-region', name='Область', category='region')
    location = Location.objects.create(name='Каноническая область', location_type=region_type)
    LocationIdentifier.objects.create(location=location, provider='ru-region-code', value='50')
    endpoint = '/api/v1/location-dictionaries/regions/'
    response = client.post(endpoint, {'name': 'Прежняя область', 'code': '50'},
                           content_type='application/json')
    assert response.status_code == 201, response.content
    identifier = response.json()['id']
    mapping = LegacyLocationMapping.objects.get(model_name='region', legacy_id=identifier)
    assert mapping.location_id == location.pk
    endpoint += f'{identifier}/'
    response = client.patch(endpoint, {'name': 'Обновлённая область', 'code': '050'},
                            content_type='application/json')
    assert response.status_code == 200, response.content
    mapping.refresh_from_db()
    assert (mapping.legacy_name, mapping.legacy_code) == ('Обновлённая область', '050')
    assert mapping.location_id == location.pk
    assert client.delete(endpoint).status_code == 204
    mapping.refresh_from_db()
    assert not mapping.legacy_name and not mapping.legacy_code
    assert mapping.location_id == location.pk
    assert client.get(endpoint).status_code == 404


@pytest.mark.django_db
def test_old_region_creation_skips_reserved_id(client, location_dictionary_catalog):
    """Never reissue a tombstoned ID, and reserve new IDs from the native sequence."""
    client.force_login(create_location_manager())
    location = Location.objects.get(legacy_mappings__model_name='region',
                                    legacy_mappings__legacy_id=location_dictionary_catalog['regions'].pk)
    with connection.cursor() as cursor:
        cursor.execute('SELECT nextval(pg_get_serial_sequence(%s, %s))', ['region', 'id'])
        previous, = cursor.fetchone()
    reserved = LegacyLocationMapping.objects.create(model_name='region', legacy_id=previous + 1, location=location)

    endpoint = '/api/v1/location-dictionaries/regions/'
    response = client.post(endpoint, {'name': 'Проверочная область', 'code': 'T501'}, content_type='application/json')
    assert response.status_code == 201, response.content
    identifier = response.json()['id']
    assert identifier > reserved.legacy_id
    assert Region.objects.get(pk=identifier).name == 'Проверочная область'
    assert Region.objects.create(name='Область из админки', code='T502').pk > identifier
    reserved.refresh_from_db()
    assert reserved.location_id == location.pk and reserved.legacy_name == ''


@pytest.mark.django_db
def test_mutations_work_from_registry_and_protect_mapped_children(client, location_dictionary_catalog):
    """Keep old API writes and dependency protection independent of a missing mirror row."""
    client.force_login(create_location_manager())
    catalog = location_dictionary_catalog
    parent = LegacyLocationMapping.objects.get(model_name='region', legacy_id=catalog['regions'].pk)
    registry_only_region = LegacyLocationMapping.objects.create(
        model_name='region', legacy_id=450000, legacy_name='Территория', legacy_code='T450', location=parent.location,
    )
    child = LegacyLocationMapping.objects.create(
        model_name='city', legacy_id=450001, legacy_name='Город', legacy_region_id=registry_only_region.legacy_id,
        location=parent.location,
    )
    endpoint = f'/api/v1/location-dictionaries/regions/{registry_only_region.legacy_id}/'
    with CaptureQueriesContext(connection) as queries:
        response = client.patch(endpoint, {'name': 'Прежняя территория'}, content_type='application/json')
    assert response.status_code == 200, response.content
    assert response.json()['name'] == 'Прежняя территория'
    assert parent.location.name != response.json()['name']
    assert not any('FROM "region"' in query['sql'] or 'JOIN "region"' in query['sql'] for query in queries)
    assert client.delete(endpoint).status_code == 409
    child.refresh_from_db()
    assert child.legacy_region_id == registry_only_region.legacy_id
    assert client.delete(f'/api/v1/location-dictionaries/cities/{child.legacy_id}/').status_code == 204
    assert client.delete(endpoint).status_code == 204
    assert client.get(endpoint).status_code == 404
    registry_only_region.refresh_from_db()
    assert registry_only_region.location_id == parent.location_id


@pytest.mark.django_db(transaction=True)
def test_concurrent_region_creations_validate_against_committed_registry():
    """Serialize competing case-insensitive names before creating their mirrors."""
    manager = create_location_manager()
    barrier = Barrier(2)

    def post_region(name, code):
        """Send a real request from a separate database connection."""
        try:
            client = Client()
            client.force_login(manager)
            barrier.wait(timeout=10)
            response = client.post('/api/v1/location-dictionaries/regions/', {'name': name, 'code': code},
                                   content_type='application/json')
            return response.status_code, response.json()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(post_region, 'Область проверки', 'PAR1')
        second = executor.submit(post_region, 'область проверки', 'PAR2')
        answers = dict((first.result(timeout=20), second.result(timeout=20)))
    assert set(answers) == {201, 400}
    assert 'name' in answers[400]
    assert Region.objects.filter(name__iexact='Область проверки').count() == 1
    assert LegacyLocationMapping.objects.filter(model_name='region', legacy_id=answers[201]['id']).count() == 1


@pytest.mark.django_db
def test_legacy_dictionary_and_selectors_read_mapping_with_original_ids(client, location_dictionary_catalog):
    """Preserve exact parents, dates, activity, and selection IDs without legacy table reads."""
    catalog = location_dictionary_catalog
    region, city, district = catalog['regions'], catalog['cities'], catalog['districts']
    mapping = LegacyLocationMapping.objects.get(model_name='district', legacy_id=district.pk)
    mapping.location.is_active = False
    mapping.location.save(update_fields=['is_active'])
    with CaptureQueriesContext(connection) as queries:
        rows = client.get('/api/v1/location-dictionaries/districts/', {
            'regionId': region.pk, 'cityId': city.pk, 'q': region.name,
            'ordering': 'city', 'status': 'active',
        }).json()['results']
        options = client.get('/api/v1/catalog-options/districts/', {
            'cityId': city.pk, 'q': 'absent', 'selected': district.pk, 'activeOnly': True,
        }).json()
        cities = client.get('/api/cities/', {'region_id': region.pk}).json()
        districts = client.get('/api/districts/', {'city_id': city.pk}).json()
    row, = rows
    assert row['id'] == district.pk and row['isActive'] and row['location'] is None
    assert row['createdAt'] == DateTimeField().to_representation(district.created_at)
    assert row['region'] == {'id': region.pk, 'name': region.name}
    assert row['city'] == {'id': city.pk, 'name': city.name}
    assert row['legacyEditUrl'] == f'/locations/?model=district&edit={district.pk}'
    assert options['results'] == [] and options['selected'] == [{
        'id': district.pk, 'label': district.name, 'regionId': region.pk, 'cityId': city.pk,
    }]
    assert cities == [{'id': city.pk, 'name': city.name}]
    assert districts == [{'id': district.pk, 'name': district.name}]
    assert not any(f'{verb} "{table}"' in query['sql'] for query in queries
                   for verb in ('FROM', 'JOIN') for table in ('region', 'city', 'district'))


@pytest.mark.django_db
@pytest.mark.parametrize(
    'dictionary_key',
    ('regions', 'cities', 'districts', 'metro'),
)
def test_location_dictionary_list_supports_every_whitelisted_model(
    client,
    location_dictionary_catalog,
    dictionary_key,
):
    """Expose every configured dictionary through one public contract."""
    response = client.get(
        reverse(
            'api_v1:location_dictionary_list',
            kwargs={'dictionary_key': dictionary_key},
        )
    )

    assert response.status_code == 200
    assert response.json()['totalCount'] >= 1
    assert any(
        row['id'] == location_dictionary_catalog[dictionary_key].pk
        for row in response.json()['results']
    )


@pytest.mark.django_db
def test_location_metro_list_filters_with_constant_query_count(
    client,
    location_dictionary_catalog,
    django_assert_num_queries,
):
    """Filter metro stations without per-row hierarchy queries."""
    with django_assert_num_queries(3):
        response = client.get(
            reverse(
                'api_v1:location_dictionary_list',
                kwargs={'dictionary_key': 'metro'},
            ),
            {
                'q': 'Охотный',
                'regionId': location_dictionary_catalog['regions'].pk,
                'cityId': location_dictionary_catalog['cities'].pk,
                'metroLineId': (
                    location_dictionary_catalog['metro_line'].pk
                ),
                'status': 'active',
            },
        )

    assert response.status_code == 200
    assert response.json()['results'] == [
        {
            'id': location_dictionary_catalog['metro'].pk,
            'name': 'Охотный Ряд',
            'code': None,
            'region': {
                'id': location_dictionary_catalog['regions'].pk,
                'name': 'Москва',
            },
            'city': {
                'id': location_dictionary_catalog['cities'].pk,
                'name': 'Москва',
            },
            'metroLine': {
                'id': location_dictionary_catalog['metro_line'].pk,
                'name': 'Сокольническая',
                'color': '#D92B2B',
            },
            'system': None,
            'location': None,
            'lines': [{
                'id': location_dictionary_catalog['metro_line'].pk,
                'name': 'Сокольническая', 'color': '#D92B2B',
            }],
            'lineColor': None,
            'locationIsInferred': True,
            'usageCount': 0,
            'isActive': True,
            'createdAt': response.json()['results'][0]['createdAt'],
            'updatedAt': response.json()['results'][0]['updatedAt'],
            'legacyEditUrl': (
                '/locations/?model=metro&edit='
                f"{location_dictionary_catalog['metro'].pk}"
            ),
        }
    ]


@pytest.mark.django_db
def test_location_dictionary_detail_and_unknown_key_are_safe(
    client,
    location_dictionary_catalog,
):
    """Return a public entry and hide unsupported model names."""
    city = location_dictionary_catalog['cities']
    response = client.get(
        reverse(
            'api_v1:location_dictionary_detail',
            kwargs={'dictionary_key': 'cities', 'pk': city.pk},
        )
    )
    unknown_response = client.get(
        reverse(
            'api_v1:location_dictionary_list',
            kwargs={'dictionary_key': 'users'},
        )
    )

    assert response.status_code == 200
    assert response.json()['name'] == 'Москва'
    assert response.json()['region']['name'] == 'Москва'
    assert unknown_response.status_code == 404


@pytest.mark.django_db
def test_location_options_follow_region_and_city_bounds(
    client,
    location_dictionary_catalog,
    settings,
):
    """Return only requested hierarchy options and report truncation."""
    settings.PUBLIC_CATALOG_API_MAX_RESULTS = 1
    response = client.get(
        reverse('api_v1:location_dictionary_options'),
        {
            'regionId': location_dictionary_catalog['regions'].pk,
            'cityId': location_dictionary_catalog['cities'].pk,
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        'regions': [
            {
                'id': location_dictionary_catalog['regions'].pk,
                'name': 'Москва',
            }
        ],
        'cities': [
            {
                'id': location_dictionary_catalog['cities'].pk,
                'name': 'Москва',
                'regionId': location_dictionary_catalog['regions'].pk,
            }
        ],
        'metroLines': [
            {
                'id': location_dictionary_catalog['metro_line'].pk,
                'name': 'Сокольническая',
                'color': '#D92B2B',
                'cityId': location_dictionary_catalog['cities'].pk,
            }
        ],
        'truncated': {
            'regions': True,
            'cities': False,
            'metroLines': False,
        },
    }


@pytest.mark.django_db
def test_location_mutations_require_catalog_permission(
    client,
    location_dictionary_catalog,
):
    """Reject shared location changes from a regular authenticated user."""
    regular_user = get_user_model().objects.create_user(
        email='location-regular@example.com',
        password='safe-test-password',
        phone_number='+79990000212',
    )
    client.force_login(regular_user)
    response = client.post(
        reverse(
            'api_v1:location_dictionary_list',
            kwargs={'dictionary_key': 'cities'},
        ),
        data={
            'name': 'Зеленоград',
            'regionId': location_dictionary_catalog['regions'].pk,
        },
        content_type='application/json',
    )

    assert response.status_code == 403
    assert not City.objects.filter(name='Зеленоград').exists()


@pytest.mark.django_db
def test_location_manager_can_create_and_update_nested_entries(
    client,
    location_dictionary_catalog,
):
    """Create a city and move a district through validated API writes."""
    client.force_login(create_location_manager())
    create_response = client.post(
        reverse(
            'api_v1:location_dictionary_list',
            kwargs={'dictionary_key': 'cities'},
        ),
        data={
            'name': '  Зеленоград  ',
            'regionId': location_dictionary_catalog['regions'].pk,
            'isActive': True,
        },
        content_type='application/json',
    )
    district = location_dictionary_catalog['districts']
    update_response = client.patch(
        reverse(
            'api_v1:location_dictionary_detail',
            kwargs={'dictionary_key': 'districts', 'pk': district.pk},
        ),
        data={
            'cityId': location_dictionary_catalog['second_city'].pk,
            'isActive': False,
        },
        content_type='application/json',
    )

    assert create_response.status_code == 201, create_response.json()
    assert create_response.json()['region']['name'] == 'Москва'
    assert City.objects.get(name='Зеленоград').region == (
        location_dictionary_catalog['regions']
    )
    assert update_response.status_code == 200, update_response.json()
    district.refresh_from_db()
    assert district.city == location_dictionary_catalog['second_city']
    assert district.is_active is False


@pytest.mark.django_db
def test_location_api_validates_shape_parents_and_scoped_duplicates(
    client,
    location_dictionary_catalog,
):
    """Reject invalid parents, unsupported fields, and scoped duplicates."""
    client.force_login(create_location_manager())
    cities_url = reverse(
        'api_v1:location_dictionary_list',
        kwargs={'dictionary_key': 'cities'},
    )
    metro_url = reverse(
        'api_v1:location_dictionary_list',
        kwargs={'dictionary_key': 'metro'},
    )

    duplicate_response = client.post(
        cities_url,
        data={
            'name': '  москва ',
            'regionId': location_dictionary_catalog['regions'].pk,
        },
        content_type='application/json',
    )
    invalid_parent_response = client.post(
        metro_url,
        data={'name': 'Тестовая', 'metroLineId': 999999},
        content_type='application/json',
    )
    unsupported_field_response = client.post(
        cities_url,
        data={
            'name': 'Тверь',
            'regionId': location_dictionary_catalog['regions'].pk,
            'code': '69',
        },
        content_type='application/json',
    )

    assert duplicate_response.status_code == 400
    assert 'name' in duplicate_response.json()
    assert invalid_parent_response.status_code == 400
    assert 'metroLineId' in invalid_parent_response.json()
    assert unsupported_field_response.status_code == 400
    assert 'code' in unsupported_field_response.json()


@pytest.mark.django_db
def test_location_region_code_is_required_normalized_and_unique(
    client,
    location_dictionary_catalog,
):
    """Normalize region codes and reject missing or duplicate values."""
    client.force_login(create_location_manager())
    regions_url = reverse(
        'api_v1:location_dictionary_list',
        kwargs={'dictionary_key': 'regions'},
    )
    missing_response = client.post(
        regions_url,
        data={'name': 'Тверская область'},
        content_type='application/json',
    )
    duplicate_response = client.post(
        regions_url,
        data={'name': 'Тульская область', 'code': ' 77 '},
        content_type='application/json',
    )
    success_response = client.post(
        regions_url,
        data={'name': 'Тверская область', 'code': ' tv '},
        content_type='application/json',
    )

    assert missing_response.status_code == 400
    assert 'code' in missing_response.json()
    assert duplicate_response.status_code == 400
    assert 'code' in duplicate_response.json()
    assert success_response.status_code == 201, success_response.json()
    assert Region.objects.get(name='Тверская область').code == 'TV'


@pytest.mark.django_db
def test_location_delete_reports_dependencies_and_deletes_unused(
    client,
    location_dictionary_catalog,
):
    """Return a conflict for used regions and delete an unused district."""
    client.force_login(create_location_manager())
    used_region = location_dictionary_catalog['regions']
    unused_district = location_dictionary_catalog['districts']

    conflict_response = client.delete(
        reverse(
            'api_v1:location_dictionary_detail',
            kwargs={'dictionary_key': 'regions', 'pk': used_region.pk},
        )
    )
    delete_response = client.delete(
        reverse(
            'api_v1:location_dictionary_detail',
            kwargs={'dictionary_key': 'districts', 'pk': unused_district.pk},
        )
    )

    assert conflict_response.status_code == 409
    assert Region.objects.filter(pk=used_region.pk).exists()
    assert delete_response.status_code == 204
    assert not District.objects.filter(pk=unused_district.pk).exists()
