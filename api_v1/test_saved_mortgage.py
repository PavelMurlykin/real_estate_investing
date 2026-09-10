from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from location.models import City, District, Region
from mortgage.models import MortgageCalculation
from property.models import (
    ApartmentDecoration,
    ApartmentLayout,
    Developer,
    Property,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateType,
)

from .test_mortgage import build_mortgage_payload


@pytest.fixture
def saved_calculation_property():
    """Create a property with the relations used by history serializers."""
    region = Region.objects.create(name='Регион истории', code='HISTORY')
    city = City.objects.create(name='Казань', region=region)
    district = District.objects.create(name='Центральный', city=city)
    developer = Developer.objects.create(name='Надёжный застройщик')
    real_estate_type = RealEstateType.objects.create(name='Квартира')
    real_estate_class = RealEstateClass.objects.create(
        name='Комфорт',
        weight=Decimal('1.00'),
    )
    real_estate_complex = RealEstateComplex.objects.create(
        name='Зелёный квартал',
        developer=developer,
        district=district,
        real_estate_class=real_estate_class,
        real_estate_type=real_estate_type,
    )
    building = RealEstateComplexBuilding.objects.create(
        number='2',
        real_estate_complex=real_estate_complex,
    )
    layout = ApartmentLayout.objects.create(name='Евродвушка')
    decoration = ApartmentDecoration.objects.create(name='Чистовая')
    return Property.objects.create(
        apartment_number='42',
        building=building,
        decoration=decoration,
        layout=layout,
        area=Decimal('52.40'),
        floor=8,
        property_cost=Decimal('5000000.00'),
    )


@pytest.fixture
def calculation_user():
    """Create a regular owner of private mortgage calculations."""
    return get_user_model().objects.create_user(
        email='calculation-owner@example.com',
        password='safe-test-password',
        phone_number='+79991110001',
        first_name='Анна',
        last_name='Смирнова',
    )


def build_save_payload(property_object, **parameter_overrides):
    """Return a valid saved-calculation request payload."""
    return {
        'propertyId': property_object.pk,
        'parameters': build_mortgage_payload(**parameter_overrides),
    }


@pytest.mark.django_db
def test_saved_calculation_api_requires_authentication(
    client,
    saved_calculation_property,
):
    """Keep calculation history and writes private."""
    list_response = client.get(
        reverse('api_v1:saved_mortgage_calculation_list')
    )
    save_response = client.post(
        reverse('api_v1:saved_mortgage_calculation_list'),
        data=build_save_payload(saved_calculation_property),
        content_type='application/json',
    )

    assert list_response.status_code == 403
    assert save_response.status_code == 403
    assert not MortgageCalculation.objects.exists()


@pytest.mark.django_db
def test_saved_calculation_api_recalculates_and_persists_owner_data(
    client,
    calculation_user,
    saved_calculation_property,
):
    """Persist authoritative calculated values under the current owner."""
    client.force_login(calculation_user)

    response = client.post(
        reverse('api_v1:saved_mortgage_calculation_list'),
        data=build_save_payload(saved_calculation_property),
        content_type='application/json',
    )

    assert response.status_code == 201
    calculation = MortgageCalculation.objects.get()
    assert calculation.user == calculation_user
    assert calculation.property == saved_calculation_property
    assert calculation.final_property_cost == Decimal('4500000.00')
    assert calculation.total_loan_amount == Decimal('3600000.00')
    payload = response.json()
    assert payload['id'] == calculation.pk
    assert payload['property']['realEstateComplex'] == 'Зелёный квартал'
    assert payload['calculation']['summary']['paymentsCount'] == 12
    assert len(payload['calculation']['schedule']) == 12


@pytest.mark.django_db
def test_saved_calculation_api_rejects_unknown_property(
    client,
    calculation_user,
):
    """Validate property identifiers before a calculation is persisted."""
    client.force_login(calculation_user)

    response = client.post(
        reverse('api_v1:saved_mortgage_calculation_list'),
        data={
            'propertyId': 999999,
            'parameters': build_mortgage_payload(),
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'propertyId' in response.json()
    assert not MortgageCalculation.objects.exists()


@pytest.mark.django_db
def test_saved_calculation_list_and_detail_are_scoped_to_owner(
    client,
    calculation_user,
    saved_calculation_property,
):
    """Return 404 for another user's private calculation identifier."""
    client.force_login(calculation_user)
    created_response = client.post(
        reverse('api_v1:saved_mortgage_calculation_list'),
        data=build_save_payload(saved_calculation_property),
        content_type='application/json',
    )
    calculation_id = created_response.json()['id']
    other_user = get_user_model().objects.create_user(
        email='other-owner@example.com',
        password='safe-test-password',
        phone_number='+79991110002',
    )
    client.force_login(other_user)

    list_response = client.get(
        reverse('api_v1:saved_mortgage_calculation_list')
    )
    detail_response = client.get(
        reverse(
            'api_v1:saved_mortgage_calculation_detail',
            kwargs={'pk': calculation_id},
        )
    )

    assert list_response.status_code == 200
    assert list_response.json()['results'] == []
    assert detail_response.status_code == 404


@pytest.mark.django_db
def test_administrator_can_view_all_saved_calculations(
    client,
    calculation_user,
    saved_calculation_property,
):
    """Preserve the established administrator access to private records."""
    client.force_login(calculation_user)
    created_response = client.post(
        reverse('api_v1:saved_mortgage_calculation_list'),
        data=build_save_payload(saved_calculation_property),
        content_type='application/json',
    )
    calculation_id = created_response.json()['id']
    administrator = get_user_model().objects.create_superuser(
        email='calculation-admin@example.com',
        password='safe-test-password',
        phone_number='+79991110003',
    )
    client.force_login(administrator)

    list_response = client.get(
        reverse('api_v1:saved_mortgage_calculation_list')
    )
    detail_response = client.get(
        reverse(
            'api_v1:saved_mortgage_calculation_detail',
            kwargs={'pk': calculation_id},
        )
    )

    assert list_response.status_code == 200
    assert [item['id'] for item in list_response.json()['results']] == [
        calculation_id
    ]
    assert detail_response.status_code == 200


@pytest.mark.django_db
def test_saved_calculation_list_supports_search_and_pagination(
    client,
    calculation_user,
    saved_calculation_property,
):
    """Expose stable URL-driven history filters with bounded results."""
    client.force_login(calculation_user)
    list_url = reverse('api_v1:saved_mortgage_calculation_list')
    for annual_rate in ('10.00', '11.00'):
        response = client.post(
            list_url,
            data=build_save_payload(
                saved_calculation_property,
                annualRate=annual_rate,
            ),
            content_type='application/json',
        )
        assert response.status_code == 201

    response = client.get(
        list_url,
        {'q': 'Зелёный', 'pageSize': 1, 'ordering': 'annualRate'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['totalCount'] == 2
    assert payload['totalPages'] == 2
    assert len(payload['results']) == 1
    assert payload['results'][0]['annualRate'] == '10.00'


@pytest.mark.django_db
def test_saved_calculation_list_uses_constant_query_count(
    client,
    calculation_user,
    saved_calculation_property,
    django_assert_num_queries,
):
    """Load list relations eagerly instead of querying once per row."""
    client.force_login(calculation_user)
    list_url = reverse('api_v1:saved_mortgage_calculation_list')
    for annual_rate in ('10.00', '11.00', '12.00'):
        response = client.post(
            list_url,
            data=build_save_payload(
                saved_calculation_property,
                annualRate=annual_rate,
            ),
            content_type='application/json',
        )
        assert response.status_code == 201

    with django_assert_num_queries(5):
        response = client.get(list_url)

    assert response.status_code == 200
    assert len(response.json()['results']) == 3


@pytest.mark.django_db
def test_saved_calculation_save_requires_csrf_token(
    calculation_user,
    saved_calculation_property,
):
    """Preserve Django CSRF protection for session-authenticated writes."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(calculation_user)

    response = csrf_client.post(
        reverse('api_v1:saved_mortgage_calculation_list'),
        data=build_save_payload(saved_calculation_property),
        content_type='application/json',
    )

    assert response.status_code == 403
    assert not MortgageCalculation.objects.exists()
