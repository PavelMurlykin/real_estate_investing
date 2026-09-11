from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from location.models import City, District, Region
from property.models import (
    ApartmentDecoration,
    ApartmentLayout,
    Developer,
    RealEstateClass,
    RealEstateComplex,
    RealEstateType,
    TransportAccessibilityType,
    WindowView,
)
from users.roles import MODERATOR_GROUP_NAME


@pytest.fixture
def property_dictionary_catalog():
    """Create all supported dictionary models and one protected relation."""
    region = Region.objects.create(name='Тестовый регион', code='TD')
    city = City.objects.create(name='Тестоград', region=region)
    district = District.objects.create(name='Центральный', city=city)
    developer = Developer.objects.create(name='Тестовый застройщик')
    real_estate_type = RealEstateType.objects.create(
        name='Квартира', description='Жилая недвижимость'
    )
    real_estate_class = RealEstateClass.objects.create(
        name='Бизнес',
        description='Повышенный комфорт',
        weight=Decimal('1.20'),
    )
    RealEstateClass.objects.create(
        name='Комфорт',
        weight=Decimal('1.00'),
        is_active=False,
    )
    RealEstateComplex.objects.create(
        name='Тестовый квартал',
        developer=developer,
        district=district,
        real_estate_class=real_estate_class,
        real_estate_type=real_estate_type,
    )
    return {
        'real-estate-types': real_estate_type,
        'real-estate-classes': real_estate_class,
        'apartment-layouts': ApartmentLayout.objects.create(name='Студия'),
        'apartment-decorations': ApartmentDecoration.objects.create(
            name='Чистовая'
        ),
        'window-views': WindowView.objects.create(name='Во двор'),
        'transport-accessibility-types': (
            TransportAccessibilityType.objects.create(name='Велосипед')
        ),
    }


def create_catalog_manager():
    """Create a user allowed to mutate shared property dictionaries."""
    user = get_user_model().objects.create_user(
        email='dictionary-moderator@example.com',
        password='safe-test-password',
        phone_number='+79990000111',
    )
    moderator_group, _ = Group.objects.get_or_create(
        name=MODERATOR_GROUP_NAME
    )
    user.groups.add(moderator_group)
    return user


@pytest.mark.django_db
@pytest.mark.parametrize(
    'dictionary_key',
    (
        'real-estate-types',
        'real-estate-classes',
        'apartment-layouts',
        'apartment-decorations',
        'window-views',
        'transport-accessibility-types',
    ),
)
def test_property_dictionary_list_supports_every_whitelisted_model(
    client,
    property_dictionary_catalog,
    dictionary_key,
):
    """Expose every configured dictionary through the same public contract."""
    response = client.get(
        reverse(
            'api_v1:property_dictionary_list',
            kwargs={'dictionary_key': dictionary_key},
        )
    )

    assert response.status_code == 200
    assert response.json()['totalCount'] >= 1
    assert any(
        row['id'] == property_dictionary_catalog[dictionary_key].pk
        for row in response.json()['results']
    )


@pytest.mark.django_db
def test_property_dictionary_list_filters_and_uses_constant_query_count(
    client,
    property_dictionary_catalog,
    django_assert_num_queries,
):
    """Filter class entries with a bounded two-query paginated response."""
    with django_assert_num_queries(2):
        response = client.get(
            reverse(
                'api_v1:property_dictionary_list',
                kwargs={'dictionary_key': 'real-estate-classes'},
            ),
            {'q': 'Бизнес', 'status': 'active'},
        )

    assert response.status_code == 200
    assert response.json()['results'] == [
        {
            'id': property_dictionary_catalog['real-estate-classes'].pk,
            'name': 'Бизнес',
            'description': 'Повышенный комфорт',
            'weight': '1.20',
            'usageCount': 1,
            'isActive': True,
            'createdAt': response.json()['results'][0]['createdAt'],
            'updatedAt': response.json()['results'][0]['updatedAt'],
            'legacyEditUrl': (
                '/property/dictionaries/?model=real_estate_class&edit='
                f"{property_dictionary_catalog['real-estate-classes'].pk}"
            ),
        }
    ]


@pytest.mark.django_db
def test_property_dictionary_detail_is_public_and_unknown_key_is_hidden(
    client,
    property_dictionary_catalog,
):
    """Return a public entry and a generic 404 for unsupported models."""
    layout = property_dictionary_catalog['apartment-layouts']
    response = client.get(
        reverse(
            'api_v1:property_dictionary_detail',
            kwargs={
                'dictionary_key': 'apartment-layouts',
                'pk': layout.pk,
            },
        )
    )
    unknown_response = client.get(
        reverse(
            'api_v1:property_dictionary_list',
            kwargs={'dictionary_key': 'users'},
        )
    )

    assert response.status_code == 200
    assert response.json()['name'] == 'Студия'
    assert response.json()['weight'] is None
    assert unknown_response.status_code == 404


@pytest.mark.django_db
def test_property_dictionary_mutations_require_catalog_permission(
    client,
    property_dictionary_catalog,
):
    """Reject shared dictionary changes from a regular authenticated user."""
    regular_user = get_user_model().objects.create_user(
        email='dictionary-regular@example.com',
        password='safe-test-password',
        phone_number='+79990000112',
    )
    client.force_login(regular_user)
    response = client.post(
        reverse(
            'api_v1:property_dictionary_list',
            kwargs={'dictionary_key': 'apartment-layouts'},
        ),
        data={'name': 'Евродвушка'},
        content_type='application/json',
    )

    assert response.status_code == 403
    assert not ApartmentLayout.objects.filter(name='Евродвушка').exists()


@pytest.mark.django_db
def test_property_dictionary_manager_can_create_and_update_entries(
    client,
    property_dictionary_catalog,
):
    """Create a class and update a standard entry through validated writes."""
    client.force_login(create_catalog_manager())
    create_response = client.post(
        reverse(
            'api_v1:property_dictionary_list',
            kwargs={'dictionary_key': 'real-estate-classes'},
        ),
        data={
            'name': 'Премиум',
            'description': '  Высокий класс  ',
            'weight': '1.45',
            'isActive': True,
        },
        content_type='application/json',
    )
    layout = property_dictionary_catalog['apartment-layouts']
    update_response = client.patch(
        reverse(
            'api_v1:property_dictionary_detail',
            kwargs={
                'dictionary_key': 'apartment-layouts',
                'pk': layout.pk,
            },
        ),
        data={'description': '  Открытая планировка  ', 'isActive': False},
        content_type='application/json',
    )

    assert create_response.status_code == 201, create_response.json()
    assert create_response.json()['weight'] == '1.45'
    assert RealEstateClass.objects.get(name='Премиум').description == (
        'Высокий класс'
    )
    assert update_response.status_code == 200, update_response.json()
    layout.refresh_from_db()
    assert layout.description == 'Открытая планировка'
    assert layout.is_active is False


@pytest.mark.django_db
def test_property_dictionary_api_validates_shape_and_duplicate_names(
    client,
    property_dictionary_catalog,
):
    """Require class coefficients and reject case-insensitive duplicates."""
    client.force_login(create_catalog_manager())
    classes_url = reverse(
        'api_v1:property_dictionary_list',
        kwargs={'dictionary_key': 'real-estate-classes'},
    )
    layouts_url = reverse(
        'api_v1:property_dictionary_list',
        kwargs={'dictionary_key': 'apartment-layouts'},
    )

    missing_weight_response = client.post(
        classes_url,
        data={'name': 'Эконом'},
        content_type='application/json',
    )
    duplicate_response = client.post(
        layouts_url,
        data={'name': '  студия  '},
        content_type='application/json',
    )
    unexpected_weight_response = client.post(
        layouts_url,
        data={'name': 'Двухкомнатная', 'weight': '1.00'},
        content_type='application/json',
    )

    assert missing_weight_response.status_code == 400
    assert 'weight' in missing_weight_response.json()
    assert duplicate_response.status_code == 400
    assert 'name' in duplicate_response.json()
    assert unexpected_weight_response.status_code == 400
    assert 'weight' in unexpected_weight_response.json()


@pytest.mark.django_db
def test_property_dictionary_delete_reports_dependencies_and_deletes_unused(
    client,
    property_dictionary_catalog,
):
    """Return a conflict for used entries and delete an unused entry."""
    client.force_login(create_catalog_manager())
    used_type = property_dictionary_catalog['real-estate-types']
    unused_window_view = property_dictionary_catalog['window-views']

    conflict_response = client.delete(
        reverse(
            'api_v1:property_dictionary_detail',
            kwargs={
                'dictionary_key': 'real-estate-types',
                'pk': used_type.pk,
            },
        )
    )
    delete_response = client.delete(
        reverse(
            'api_v1:property_dictionary_detail',
            kwargs={
                'dictionary_key': 'window-views',
                'pk': unused_window_view.pk,
            },
        )
    )

    assert conflict_response.status_code == 409
    assert RealEstateType.objects.filter(pk=used_type.pk).exists()
    assert delete_response.status_code == 204
    assert not WindowView.objects.filter(pk=unused_window_view.pk).exists()
