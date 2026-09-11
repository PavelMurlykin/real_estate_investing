import json
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from location.models import City, District, Metro, MetroLine, Region
from property.models import (
    ApartmentDecoration,
    ApartmentLayout,
    CompanyGroup,
    Developer,
    Property,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateComplexMetroAvailability,
    RealEstateType,
    TransportAccessibilityType,
)
from users.roles import MODERATOR_GROUP_NAME


@pytest.fixture
def complex_catalog():
    """Create a compact residential-complex catalog for API tests."""
    region = Region.objects.create(name='Тестовый регион', code='TC')
    city = City.objects.create(name='Тестоград', region=region)
    district = District.objects.create(name='Центральный', city=city)
    company_group = CompanyGroup.objects.create(name='Группа Север')
    developer = Developer.objects.create(
        name='Северный девелопер', company_group=company_group
    )
    real_estate_class = RealEstateClass.objects.create(
        name='Бизнес', weight=Decimal('1.20')
    )
    real_estate_type = RealEstateType.objects.create(name='Квартира')
    accessibility_type, _ = (
        TransportAccessibilityType.objects.get_or_create(name='Пешком')
    )
    metro_line = MetroLine.objects.create(
        line='Зелёная', line_color='#118844', city=city
    )
    metro = Metro.objects.create(
        station='Тестовая', metro_line=metro_line
    )
    real_estate_complex = RealEstateComplex.objects.create(
        name='Белые ночи',
        description='Комплекс у парка',
        developer=developer,
        district=district,
        real_estate_class=real_estate_class,
        real_estate_type=real_estate_type,
        map_link='https://maps.example.com/complex',
        presentation_link='javascript:alert(1)',
        investment_potential='Стабильный спрос на аренду',
    )
    building = RealEstateComplexBuilding.objects.create(
        number='1',
        address='Тестовая улица, 1',
        commissioning_year=2028,
        commissioning_quarter=RealEstateComplexBuilding.Quarter.SECOND,
        key_handover_date=date(2028, 9, 1),
        real_estate_complex=real_estate_complex,
    )
    availability = RealEstateComplexMetroAvailability.objects.create(
        real_estate_complex=real_estate_complex,
        metro=metro,
        transport_accessibility_type=accessibility_type,
        walking_time_minutes=12,
    )
    return {
        'region': region,
        'city': city,
        'district': district,
        'developer': developer,
        'real_estate_class': real_estate_class,
        'real_estate_type': real_estate_type,
        'accessibility_type': accessibility_type,
        'metro': metro,
        'complex': real_estate_complex,
        'building': building,
        'availability': availability,
    }


def create_catalog_manager():
    """Create an authenticated user allowed to manage shared catalogs."""
    user = get_user_model().objects.create_user(
        email='complex-moderator@example.com',
        password='safe-test-password',
        phone_number='+79990000101',
    )
    moderator_group, _ = Group.objects.get_or_create(
        name=MODERATOR_GROUP_NAME
    )
    user.groups.add(moderator_group)
    return user


@pytest.mark.django_db
def test_complex_list_api_filters_and_uses_constant_query_count(
    client,
    complex_catalog,
    django_assert_num_queries,
):
    """Return normalized paginated rows without per-complex queries."""
    real_estate_complex = complex_catalog['complex']
    with django_assert_num_queries(2):
        response = client.get(
            reverse('api_v1:real_estate_complex_list'),
            {'search': 'Белые', 'buildingCount': 1},
        )

    assert response.status_code == 200
    assert response.json()['results'] == [
        {
            'id': real_estate_complex.pk,
            'name': 'Белые ночи',
            'developer': {
                'id': complex_catalog['developer'].pk,
                'name': 'Северный девелопер',
                'label': 'Северный девелопер (Группа Север)',
            },
            'city': 'Тестоград',
            'realEstateClass': 'Бизнес',
            'realEstateType': 'Квартира',
            'buildingCount': 1,
            'isActive': True,
        }
    ]


@pytest.mark.django_db
def test_complex_detail_api_returns_safe_links_and_related_rows(
    client,
    complex_catalog,
    django_assert_num_queries,
):
    """Return a complete public card through three bounded queries."""
    real_estate_complex = complex_catalog['complex']
    with django_assert_num_queries(3):
        response = client.get(
            reverse(
                'api_v1:real_estate_complex_detail',
                kwargs={'pk': real_estate_complex.pk},
            )
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['name'] == 'Белые ночи'
    assert payload['region'] == 'Тестовый регион'
    assert payload['mapUrl'] == 'https://maps.example.com/complex'
    assert payload['presentationUrl'] is None
    assert payload['buildings'][0]['commissioning'] == 'II кв. 2028'
    assert payload['buildings'][0]['keyHandover'] == '2028-09-01'
    assert payload['buildings'][0]['propertyCount'] == 0
    assert payload['metroAvailability'][0] == {
        'id': complex_catalog['availability'].pk,
        'metroId': complex_catalog['metro'].pk,
        'station': 'Тестовая',
        'line': 'Зелёная',
        'lineColor': '#118844',
        'transportAccessibilityTypeId': (
            complex_catalog['accessibility_type'].pk
        ),
        'transportAccessibilityType': 'Пешком',
        'walkingTimeMinutes': 12,
        'isActive': True,
    }
    assert payload['legacyDetailUrl'] == reverse(
        'property:complex_detail', kwargs={'pk': real_estate_complex.pk}
    )


@pytest.mark.django_db
def test_complex_options_api_returns_bounded_location_choices(
    client,
    complex_catalog,
):
    """Return form dictionaries filtered by region and city."""
    response = client.get(
        reverse('api_v1:real_estate_complex_options'),
        {
            'regionId': complex_catalog['region'].pk,
            'cityId': complex_catalog['city'].pk,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['cities'] == [
        {'id': complex_catalog['city'].pk, 'name': 'Тестоград'}
    ]
    assert payload['districts'] == [
        {'id': complex_catalog['district'].pk, 'name': 'Центральный'}
    ]
    assert payload['metroStations'] == [
        {
            'id': complex_catalog['metro'].pk,
            'station': 'Тестовая',
            'line': 'Зелёная',
            'lineColor': '#118844',
        }
    ]
    assert not any(payload['truncated'].values())


@pytest.mark.django_db
def test_complex_create_api_persists_photo_buildings_and_metro(
    client,
    complex_catalog,
    settings,
    tmp_path,
):
    """Catalog managers may create a complete complex with multipart data."""
    settings.MEDIA_ROOT = tmp_path
    client.force_login(create_catalog_manager())
    image = SimpleUploadedFile(
        'complex.gif',
        (
            b'GIF87a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00'
            b'\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00'
            b'\x02\x02D\x01\x00;'
        ),
        content_type='image/gif',
    )
    response = client.post(
        reverse('api_v1:real_estate_complex_list'),
        data={
            'name': 'Новый квартал',
            'developerId': complex_catalog['developer'].pk,
            'districtId': complex_catalog['district'].pk,
            'realEstateClassId': complex_catalog['real_estate_class'].pk,
            'realEstateTypeId': complex_catalog['real_estate_type'].pk,
            'photo': image,
            'buildings': json.dumps(
                [{'number': '2', 'address': 'Новая улица, 2'}]
            ),
            'metroAvailability': json.dumps(
                [
                    {
                        'metroId': complex_catalog['metro'].pk,
                        'transportAccessibilityTypeId': (
                            complex_catalog['accessibility_type'].pk
                        ),
                        'walkingTimeMinutes': 8,
                    }
                ]
            ),
        },
    )

    assert response.status_code == 201, response.json()
    created_complex = RealEstateComplex.objects.get(name='Новый квартал')
    assert response.json()['id'] == created_complex.pk
    assert created_complex.photo.name.startswith('property/complexes/')
    assert created_complex.realestatecomplexbuilding_set.get().number == '2'
    assert created_complex.metro_availability.get().walking_time_minutes == 8


@pytest.mark.django_db
def test_complex_create_api_rejects_unsafe_external_links(
    client,
    complex_catalog,
):
    """Do not persist links with schemes that browsers may execute."""
    client.force_login(create_catalog_manager())
    response = client.post(
        reverse('api_v1:real_estate_complex_list'),
        data={
            'name': 'Небезопасный квартал',
            'developerId': complex_catalog['developer'].pk,
            'districtId': complex_catalog['district'].pk,
            'realEstateClassId': complex_catalog['real_estate_class'].pk,
            'realEstateTypeId': complex_catalog['real_estate_type'].pk,
            'presentationLink': 'javascript:alert(1)',
            'buildings': [],
            'metroAvailability': [],
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'presentationLink' in response.json()
    assert not RealEstateComplex.objects.filter(
        name='Небезопасный квартал'
    ).exists()


@pytest.mark.django_db
def test_complex_mutations_require_catalog_management_permission(
    client,
    complex_catalog,
):
    """Regular authenticated users cannot mutate shared complexes."""
    regular_user = get_user_model().objects.create_user(
        email='complex-regular@example.com',
        password='safe-test-password',
        phone_number='+79990000102',
    )
    client.force_login(regular_user)
    response = client.patch(
        reverse(
            'api_v1:real_estate_complex_detail',
            kwargs={'pk': complex_catalog['complex'].pk},
        ),
        data={'name': 'Запрещённое изменение'},
        content_type='application/json',
    )

    assert response.status_code == 403
    complex_catalog['complex'].refresh_from_db()
    assert complex_catalog['complex'].name == 'Белые ночи'


@pytest.mark.django_db
def test_complex_update_replaces_related_rows_atomically(
    client,
    complex_catalog,
):
    """A submitted child list updates existing rows and creates new rows."""
    client.force_login(create_catalog_manager())
    response = client.patch(
        reverse(
            'api_v1:real_estate_complex_detail',
            kwargs={'pk': complex_catalog['complex'].pk},
        ),
        data={
            'buildings': [
                {
                    'id': complex_catalog['building'].pk,
                    'number': '1А',
                    'address': 'Обновлённый адрес',
                    'commissioningYear': 2029,
                    'commissioningQuarter': 3,
                    'isActive': True,
                },
                {'number': '2', 'address': None, 'isActive': True},
            ],
            'metroAvailability': [],
        },
        content_type='application/json',
    )

    assert response.status_code == 200, response.json()
    building_numbers = set(
        complex_catalog['complex'].realestatecomplexbuilding_set.values_list(
            'number', flat=True
        )
    )
    assert building_numbers == {'1А', '2'}
    assert not complex_catalog['complex'].metro_availability.exists()


@pytest.mark.django_db
def test_complex_update_cannot_remove_building_with_properties(
    client,
    complex_catalog,
):
    """Keep linked buildings when the replacement list omits them."""
    layout = ApartmentLayout.objects.create(name='Студия')
    decoration = ApartmentDecoration.objects.create(name='Чистовая')
    Property.objects.create(
        apartment_number='101',
        building=complex_catalog['building'],
        decoration=decoration,
        layout=layout,
        area=Decimal('30.00'),
        floor=3,
        property_cost=Decimal('7000000.00'),
    )
    client.force_login(create_catalog_manager())
    response = client.patch(
        reverse(
            'api_v1:real_estate_complex_detail',
            kwargs={'pk': complex_catalog['complex'].pk},
        ),
        data={'buildings': []},
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'buildings' in response.json()
    assert RealEstateComplexBuilding.objects.filter(
        pk=complex_catalog['building'].pk
    ).exists()


@pytest.mark.django_db
def test_complex_delete_reports_linked_property_conflict(
    client,
    complex_catalog,
):
    """Return a conflict instead of deleting a complex used by properties."""
    layout = ApartmentLayout.objects.create(name='Евродвушка')
    decoration = ApartmentDecoration.objects.create(name='Без отделки')
    Property.objects.create(
        apartment_number='202',
        building=complex_catalog['building'],
        decoration=decoration,
        layout=layout,
        area=Decimal('45.00'),
        floor=7,
        property_cost=Decimal('11000000.00'),
    )
    client.force_login(create_catalog_manager())
    response = client.delete(
        reverse(
            'api_v1:real_estate_complex_detail',
            kwargs={'pk': complex_catalog['complex'].pk},
        )
    )

    assert response.status_code == 409
    assert RealEstateComplex.objects.filter(
        pk=complex_catalog['complex'].pk
    ).exists()
