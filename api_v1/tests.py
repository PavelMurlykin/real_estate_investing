from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from location.models import City, District, Region
from mortgage.models import MortgageCalculation
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
from users.roles import MODERATOR_GROUP_NAME


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


def create_catalog_manager(email='moderator@example.com'):
    """Create a user who may mutate shared property catalogs."""
    user = get_user_model().objects.create_user(
        email=email,
        password='safe-test-password',
        phone_number='+79990000009',
    )
    moderator_group, _ = Group.objects.get_or_create(
        name=MODERATOR_GROUP_NAME
    )
    user.groups.add(moderator_group)
    return user


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
    assert payload['regionId'] == real_estate_complex.district.city.region_id
    assert payload['cityId'] == real_estate_complex.district.city_id
    assert payload['districtId'] == real_estate_complex.district_id
    assert payload['developerId'] == real_estate_complex.developer_id
    assert payload['realEstateComplexId'] == real_estate_complex.pk
    assert payload['buildingId'] == building.pk
    assert payload['layoutId'] == property_object.layout_id
    assert payload['decorationId'] == property_object.decoration_id
    assert payload['windowViewIds'] == [window_view.pk]
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
def test_property_form_options_are_manager_only_and_hierarchical(
    client,
    property_catalog,
):
    """Return only bounded choices for the selected location hierarchy."""
    property_object, _ = property_catalog
    building = property_object.building
    real_estate_complex = building.real_estate_complex
    district = real_estate_complex.district
    city = district.city
    layout = property_object.layout
    decoration = property_object.decoration
    window_view = WindowView.objects.create(name='Парк')

    anonymous_response = client.get(
        reverse('api_v1:property_form_options')
    )
    assert anonymous_response.status_code == 403

    client.force_login(create_catalog_manager())
    response = client.get(
        reverse('api_v1:property_form_options'),
        {
            'regionId': city.region_id,
            'cityId': city.pk,
            'districtId': district.pk,
            'developerId': real_estate_complex.developer_id,
            'realEstateComplexId': real_estate_complex.pk,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['regions'] == [
        {'id': city.region_id, 'name': 'Тестовый регион'}
    ]
    assert payload['cities'] == [
        {'id': city.pk, 'name': 'Санкт-Петербург'}
    ]
    assert payload['districts'] == [
        {'id': district.pk, 'name': 'Петроградский'}
    ]
    assert payload['developers'] == [
        {
            'id': real_estate_complex.developer_id,
            'label': 'Северный девелопер (Группа Север)',
        }
    ]
    assert payload['realEstateComplexes'] == [
        {'id': real_estate_complex.pk, 'name': 'Белые ночи'}
    ]
    assert payload['buildings'] == [
        {'id': building.pk, 'number': '1'}
    ]
    assert payload['layouts'] == [{'id': layout.pk, 'name': 'Евродвушка'}]
    assert payload['decorations'] == [
        {'id': decoration.pk, 'name': 'Чистовая'}
    ]
    assert payload['windowViews'] == [
        {'id': window_view.pk, 'name': 'Парк'}
    ]
    assert not any(payload['truncated'].values())


@pytest.mark.django_db
def test_property_create_api_persists_form_data_and_image(
    client,
    property_catalog,
    settings,
    tmp_path,
):
    """A moderator should create a property through the multipart API."""
    settings.MEDIA_ROOT = tmp_path
    property_object, _ = property_catalog
    window_view = WindowView.objects.create(name='Двор')
    client.force_login(create_catalog_manager())
    image = SimpleUploadedFile(
        'layout.gif',
        (
            b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00'
            b'\x02\x02D\x01\x00;'
        ),
        content_type='image/gif',
    )

    response = client.post(
        reverse('api_v1:property_list'),
        data={
            'apartmentNumber': '303',
            'buildingId': property_object.building_id,
            'decorationId': property_object.decoration_id,
            'layoutId': property_object.layout_id,
            'area': '61.25',
            'floor': '12',
            'propertyCost': '19000000.00',
            'windowViewIds': [window_view.pk],
            'replaceWindowViews': 'true',
            'layoutImage': image,
        },
    )

    assert response.status_code == 201
    created_property = Property.objects.get(apartment_number='303')
    assert response.json()['id'] == created_property.pk
    assert created_property.window_views.get() == window_view
    assert created_property.layout_image.name.startswith('property/layouts/')


@pytest.mark.django_db
def test_property_create_api_rejects_unsafe_image_and_non_manager(
    client,
    property_catalog,
):
    """Reject invalid uploads and users without catalog permissions."""
    property_object, _ = property_catalog
    initial_count = Property.objects.count()
    regular_user = get_user_model().objects.create_user(
        email='regular@example.com',
        password='safe-test-password',
        phone_number='+79990000008',
    )
    client.force_login(regular_user)
    forbidden_response = client.post(
        reverse('api_v1:property_list'),
        data={'apartmentNumber': 'blocked'},
    )
    assert forbidden_response.status_code == 403

    client.force_login(create_catalog_manager())
    invalid_response = client.post(
        reverse('api_v1:property_list'),
        data={
            'apartmentNumber': 'unsafe',
            'buildingId': property_object.building_id,
            'decorationId': property_object.decoration_id,
            'layoutId': property_object.layout_id,
            'area': '40.00',
            'floor': '4',
            'propertyCost': '9000000.00',
            'layoutImage': SimpleUploadedFile(
                'payload.exe',
                b'not-an-image',
                content_type='image/png',
            ),
        },
    )

    assert invalid_response.status_code == 400
    assert 'layoutImage' in invalid_response.json()
    assert Property.objects.count() == initial_count


@pytest.mark.django_db
def test_property_update_api_can_clear_images_and_window_views(
    client,
    django_capture_on_commit_callbacks,
    property_catalog,
    settings,
    tmp_path,
):
    """Explicit clear flags should remove stored values on partial update."""
    settings.MEDIA_ROOT = tmp_path
    property_object, _ = property_catalog
    window_view = WindowView.objects.create(name='Река')
    property_object.window_views.add(window_view)
    property_object.layout_image = SimpleUploadedFile(
        'old-layout.gif',
        (
            b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00'
            b'\x02\x02D\x01\x00;'
        ),
        content_type='image/gif',
    )
    property_object.save(update_fields=('layout_image',))
    previous_image_name = property_object.layout_image.name
    previous_image_storage = property_object.layout_image.storage
    assert previous_image_storage.exists(previous_image_name)
    client.force_login(create_catalog_manager())

    with django_capture_on_commit_callbacks(execute=True):
        response = client.patch(
            reverse(
                'api_v1:property_detail',
                kwargs={'pk': property_object.pk},
            ),
            data={
                'apartmentNumber': '101-А',
                'replaceWindowViews': True,
                'clearLayoutImage': True,
            },
            content_type='application/json',
        )

    assert response.status_code == 200
    property_object.refresh_from_db()
    assert property_object.apartment_number == '101-А'
    assert not property_object.layout_image
    assert not property_object.window_views.exists()
    assert not previous_image_storage.exists(previous_image_name)
    assert response.json()['windowViewIds'] == []


@pytest.mark.django_db
def test_property_mutations_require_csrf_and_report_protected_delete(
    property_catalog,
):
    """Unsafe property requests require CSRF and explain protected deletes."""
    property_object, deletable_property = property_catalog
    manager = create_catalog_manager()
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(manager)
    csrf_response = csrf_client.patch(
        reverse(
            'api_v1:property_detail',
            kwargs={'pk': property_object.pk},
        ),
        data={'apartmentNumber': 'blocked'},
        content_type='application/json',
    )
    assert csrf_response.status_code == 403

    MortgageCalculation.objects.create(
        property=property_object,
        base_property_cost=property_object.property_cost,
        initial_payment_percent=Decimal('20.00'),
        initial_payment_date=date(2026, 1, 1),
        mortgage_term=240,
        annual_rate=Decimal('18.00'),
        has_grace_period=False,
        final_property_cost=property_object.property_cost,
    )
    client = Client()
    client.force_login(manager)
    protected_response = client.delete(
        reverse(
            'api_v1:property_detail',
            kwargs={'pk': property_object.pk},
        )
    )
    deleted_response = client.delete(
        reverse(
            'api_v1:property_detail',
            kwargs={'pk': deletable_property.pk},
        )
    )

    assert protected_response.status_code == 409
    assert 'расчёты' in protected_response.json()['detail']
    assert deleted_response.status_code == 204
    assert not Property.objects.filter(pk=deletable_property.pk).exists()


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
