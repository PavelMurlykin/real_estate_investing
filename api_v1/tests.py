from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from location.models import City, District, Region
from property.models import (
    ApartmentDecoration,
    ApartmentLayout,
    CompanyGroup,
    Developer,
    Property,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateType,
    WindowView,
)


@pytest.fixture
def property_catalog():
    """Create a compact property catalog for API tests."""
    region = Region.objects.create(name='Тестовый регион', code='TEST')
    city = City.objects.create(name='Санкт-Петербург', region=region)
    district = District.objects.create(name='Петроградский', city=city)
    company_group = CompanyGroup.objects.create(name='Группа Север')
    developer = Developer.objects.create(
        name='Северный девелопер',
        company_group=company_group,
    )
    real_estate_type = RealEstateType.objects.create(name='Квартира')
    real_estate_class = RealEstateClass.objects.create(
        name='Бизнес',
        weight=Decimal('1.20'),
    )
    real_estate_complex = RealEstateComplex.objects.create(
        name='Белые ночи',
        developer=developer,
        district=district,
        real_estate_class=real_estate_class,
        real_estate_type=real_estate_type,
    )
    building = RealEstateComplexBuilding.objects.create(
        number='1',
        real_estate_complex=real_estate_complex,
    )
    layout = ApartmentLayout.objects.create(name='Евродвушка')
    decoration = ApartmentDecoration.objects.create(name='Чистовая')
    first_property = Property.objects.create(
        apartment_number='101',
        building=building,
        decoration=decoration,
        layout=layout,
        area=Decimal('42.50'),
        floor=10,
        property_cost=Decimal('12500000.00'),
    )
    second_property = Property.objects.create(
        apartment_number='202',
        building=building,
        decoration=decoration,
        layout=layout,
        area=Decimal('55.00'),
        floor=20,
        property_cost=Decimal('16800000.00'),
    )
    return first_property, second_property


@pytest.mark.django_db
def test_session_api_returns_anonymous_capabilities_and_sets_csrf_cookie(client):
    """Anonymous session responses should be safe and CSRF-ready."""
    response = client.get(reverse('api_v1:session'))

    assert response.status_code == 200
    assert response.json() == {
        'isAuthenticated': False,
        'user': None,
        'capabilities': {
            'manageCatalogs': False,
            'syncExternalData': False,
            'viewPrivateRecords': False,
            'viewAllPrivateRecords': False,
        },
    }
    assert 'csrftoken' in response.cookies


@pytest.mark.django_db
def test_session_api_returns_authenticated_user_capabilities(client):
    """Authenticated administrators should receive their full capabilities."""
    user = get_user_model().objects.create_superuser(
        email='admin@example.com',
        password='safe-test-password',
        phone_number='+79990000001',
        first_name='Анна',
        last_name='Иванова',
    )
    client.force_login(user)

    response = client.get(reverse('api_v1:session'))

    assert response.status_code == 200
    payload = response.json()
    assert payload['isAuthenticated'] is True
    assert payload['user']['displayName'] == 'Анна Иванова'
    assert payload['capabilities'] == {
        'manageCatalogs': True,
        'syncExternalData': True,
        'viewPrivateRecords': True,
        'viewAllPrivateRecords': True,
    }


@pytest.mark.django_db
def test_login_api_requires_csrf_token():
    """Anonymous login mutations must still pass Django CSRF protection."""
    csrf_client = Client(enforce_csrf_checks=True)

    response = csrf_client.post(
        reverse('api_v1:login'),
        data={
            'identifier': 'user@example.com',
            'password': 'safe-test-password',
        },
        content_type='application/json',
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_login_and_logout_api_use_existing_django_session():
    """The API should create and clear the established Django session."""
    get_user_model().objects.create_user(
        email='user@example.com',
        password='safe-test-password',
        phone_number='+79990000002',
        first_name='Павел',
        last_name='Смирнов',
    )
    csrf_client = Client(enforce_csrf_checks=True)
    session_response = csrf_client.get(reverse('api_v1:session'))
    csrf_token = session_response.cookies['csrftoken'].value

    login_response = csrf_client.post(
        reverse('api_v1:login'),
        data={
            'identifier': 'user@example.com',
            'password': 'safe-test-password',
        },
        content_type='application/json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )

    assert login_response.status_code == 200
    assert login_response.json()['isAuthenticated'] is True

    rotated_csrf_token = csrf_client.cookies['csrftoken'].value
    logout_response = csrf_client.post(
        reverse('api_v1:logout'),
        HTTP_X_CSRFTOKEN=rotated_csrf_token,
    )

    assert logout_response.status_code == 204
    assert '_auth_user_id' not in csrf_client.session


@pytest.mark.django_db
def test_property_list_api_returns_paginated_normalized_rows(
    client,
    property_catalog,
):
    """Property list rows should follow the documented frontend contract."""
    first_property, _ = property_catalog

    response = client.get(
        reverse('api_v1:property_list'),
        {'search': '101', 'pageSize': 10},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['page'] == 1
    assert payload['pageSize'] == 10
    assert payload['totalCount'] == 1
    assert payload['totalPages'] == 1
    assert payload['results'] == [
        {
            'id': first_property.pk,
            'city': 'Санкт-Петербург',
            'developer': 'Северный девелопер (Группа Север)',
            'realEstateComplex': 'Белые ночи',
            'building': '1',
            'apartmentNumber': '101',
            'layout': 'Евродвушка',
            'decoration': 'Чистовая',
            'area': '42.50',
            'floor': 10,
            'propertyCost': '12500000.00',
            'detailUrl': reverse(
                'property:detail',
                kwargs={'pk': first_property.pk},
            ),
        }
    ]


@pytest.mark.django_db
def test_property_list_api_rejects_unknown_ordering(client):
    """Invalid sorting values should produce a bounded validation error."""
    response = client.get(
        reverse('api_v1:property_list'),
        {'ordering': 'drop-table'},
    )

    assert response.status_code == 400
    assert 'ordering' in response.json()


@pytest.mark.django_db
def test_property_list_api_uses_constant_query_count(
    client,
    property_catalog,
    django_assert_num_queries,
):
    """Pagination and related labels should not introduce per-row queries."""
    with django_assert_num_queries(2):
        response = client.get(reverse('api_v1:property_list'))

    assert response.status_code == 200
    assert len(response.json()['results']) == 2


@pytest.mark.django_db
def test_property_detail_api_returns_complete_public_card(
    client,
    property_catalog,
    django_assert_num_queries,
):
    """Return related labels, images, safe links, and legacy fallbacks."""
    property_object, _ = property_catalog
    property_object.layout_image = 'property/layouts/layout.gif'
    property_object.floor_plan_image = (
        'property/floor_plans/floor-plan.gif'
    )
    property_object.window_view_image = (
        'property/window_views/window-view.gif'
    )
    property_object.save(
        update_fields=(
            'layout_image',
            'floor_plan_image',
            'window_view_image',
        )
    )
    window_view = WindowView.objects.create(name='Парк')
    property_object.window_views.add(window_view)
    building = property_object.building
    building.commissioning_year = 2027
    building.commissioning_quarter = (
        RealEstateComplexBuilding.Quarter.SECOND
    )
    building.key_handover_date = date(2027, 9, 1)
    building.save(
        update_fields=(
            'commissioning_year',
            'commissioning_quarter',
            'key_handover_date',
        )
    )
    real_estate_complex = building.real_estate_complex
    real_estate_complex.map_link = 'https://maps.example.com/complex'
    real_estate_complex.presentation_link = 'javascript:alert(1)'
    real_estate_complex.save(
        update_fields=('map_link', 'presentation_link')
    )

    with django_assert_num_queries(2):
        response = client.get(
            reverse(
                'api_v1:property_detail',
                kwargs={'pk': property_object.pk},
            )
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['id'] == property_object.pk
    assert payload['apartmentNumber'] == '101'
    assert payload['developer'] == (
        'Северный девелопер (Группа Север)'
    )
    assert payload['realEstateComplex'] == 'Белые ночи'
    assert payload['realEstateClass'] == 'Бизнес'
    assert payload['realEstateType'] == 'Квартира'
    assert payload['district'] == 'Петроградский'
    assert payload['city'] == 'Санкт-Петербург'
    assert payload['region'] == 'Тестовый регион'
    assert payload['commissioning'] == 'II кв. 2027'
    assert payload['keyHandover'] == '2027-09-01'
    assert payload['windowViews'] == ['Парк']
    assert payload['mapUrl'] == 'https://maps.example.com/complex'
    assert payload['presentationUrl'] is None
    assert payload['images'] == [
        {
            'kind': 'layout',
            'label': 'Планировка',
            'url': '/media/property/layouts/layout.gif',
        },
        {
            'kind': 'floorPlan',
            'label': 'План этажа',
            'url': '/media/property/floor_plans/floor-plan.gif',
        },
        {
            'kind': 'windowView',
            'label': 'Вид из окна',
            'url': '/media/property/window_views/window-view.gif',
        },
    ]
    assert payload['legacyDetailUrl'] == reverse(
        'property:detail',
        kwargs={'pk': property_object.pk},
    )
    assert payload['legacyEditUrl'] == reverse(
        'property:update',
        kwargs={'pk': property_object.pk},
    )
    assert payload['legacyDeleteUrl'] == reverse(
        'property:delete',
        kwargs={'pk': property_object.pk},
    )


@pytest.mark.django_db
def test_property_detail_api_returns_404_for_unknown_identifier(client):
    """Return a conventional 404 for a missing public property."""
    response = client.get(
        reverse('api_v1:property_detail', kwargs={'pk': 999999})
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_overview_api_returns_counts_and_bounded_recent_properties(
    client,
    property_catalog,
):
    """Overview should expose summary counts and a bounded recent list."""
    response = client.get(reverse('api_v1:overview'))

    assert response.status_code == 200
    payload = response.json()
    statistics = {item['key']: item['value'] for item in payload['statistics']}
    assert statistics['properties'] == 2
    assert statistics['complexes'] == 1
    assert statistics['developers'] == 1
    assert statistics['cities'] == 1
    assert len(payload['recentProperties']) == 2
