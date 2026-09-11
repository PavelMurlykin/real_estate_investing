import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from location.models import City, District, Metro, MetroLine, Region
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
    with django_assert_num_queries(2):
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
