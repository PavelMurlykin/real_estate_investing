from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from bank.models import (
    KeyRate,
    MortgageProgram,
    MortgageProgramRegionalCreditLimit,
)
from customer.models import Customer
from location.models import City, District, Region
from property.models import ApartmentLayout


@pytest.fixture
def customer_users():
    """Create two customer owners for access-control tests."""
    owner = get_user_model().objects.create_user(
        email='customer-owner@example.com',
        password='safe-test-password',
        phone_number='+79992220001',
        first_name='Анна',
        last_name='Агент',
    )
    other_owner = get_user_model().objects.create_user(
        email='customer-other@example.com',
        password='safe-test-password',
        phone_number='+79992220002',
        first_name='Ольга',
        last_name='Агент',
    )
    return owner, other_owner


@pytest.fixture
def customer_profile(customer_users):
    """Create a complete customer profile with preference relations."""
    owner, _other_owner = customer_users
    region = Region.objects.create(name='Москва', code='CUST77')
    residence_city = City.objects.create(
        name='Химки',
        region=region,
    )
    desired_city = City.objects.create(
        name='Москва',
        region=region,
    )
    desired_district = District.objects.create(
        name='Хамовники',
        city=desired_city,
    )
    desired_layout = ApartmentLayout.objects.create(name='Евро-3')
    preferential_program = MortgageProgram.objects.create(
        name='Семейная ипотека',
        condition='Льготные условия',
        is_preferential=True,
        credit_limit=Decimal('6000000.00'),
    )
    MortgageProgramRegionalCreditLimit.objects.create(
        mortgage_program=preferential_program,
        region=region,
        credit_limit=Decimal('12000000.00'),
    )
    KeyRate.objects.create(
        meeting_date=date(2026, 9, 1),
        key_rate=Decimal('16.00'),
    )
    customer = Customer.objects.create(
        user=owner,
        first_name='Иван',
        last_name='Петров',
        phone='+79995554433',
        email='ivan@example.com',
        age=35,
        residence_city=residence_city,
        initial_payment_amount=Decimal('2000000.00'),
        max_monthly_payment=Decimal('150000.00'),
        has_owned_property=False,
        purchase_goal=Customer.PURCHASE_GOAL_INVESTMENT,
        desired_city=desired_city,
        desired_district=desired_district,
        area_min=Decimal('55.00'),
        area_max=Decimal('80.00'),
        desired_floor='Не первый',
        cardinal_directions='Юг, Восток',
        comment='Нужен тихий двор',
    )
    customer.preferential_programs.add(preferential_program)
    customer.desired_layouts.add(desired_layout)
    return customer


@pytest.mark.django_db
def test_customer_api_requires_authentication(client, customer_profile):
    """Keep customer contact and financial data private."""
    list_response = client.get(reverse('api_v1:customer_list'))
    detail_response = client.get(
        reverse(
            'api_v1:customer_detail',
            kwargs={'pk': customer_profile.pk},
        )
    )

    assert list_response.status_code == 403
    assert detail_response.status_code == 403


@pytest.mark.django_db
def test_customer_list_is_searchable_paginated_and_owner_scoped(
    client,
    customer_users,
    customer_profile,
):
    """Return only matching customers owned by the signed-in user."""
    owner, other_owner = customer_users
    Customer.objects.create(
        user=owner,
        first_name='Мария',
        last_name='Соколова',
    )
    Customer.objects.create(
        user=other_owner,
        first_name='Иван',
        last_name='Чужой',
        email='hidden@example.com',
    )
    client.force_login(owner)

    response = client.get(
        reverse('api_v1:customer_list'),
        {'q': 'Иван', 'ordering': 'name', 'pageSize': 1},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['page'] == 1
    assert payload['pageSize'] == 1
    assert payload['totalCount'] == 1
    assert payload['totalPages'] == 1
    assert payload['results'][0]['id'] == customer_profile.pk
    assert payload['results'][0]['fullName'] == 'Иван Петров'
    assert payload['results'][0]['residenceCity'] == 'Химки'


@pytest.mark.django_db
def test_customer_detail_returns_profile_and_calculated_capacity(
    client,
    customer_users,
    customer_profile,
):
    """Return normalized profile fields and authoritative calculations."""
    owner, other_owner = customer_users
    client.force_login(owner)

    response = client.get(
        reverse(
            'api_v1:customer_detail',
            kwargs={'pk': customer_profile.pk},
        )
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['fullName'] == 'Иван Петров'
    assert payload['phone'] == '+79995554433'
    assert payload['purchaseGoal'] == 'investment'
    assert payload['purchaseGoalLabel'] == 'Для инвестиций'
    assert payload['desiredCity'] == 'Москва'
    assert payload['desiredDistrict'] == 'Хамовники'
    assert payload['desiredLayouts'] == [
        {
            'id': customer_profile.desired_layouts.get().pk,
            'name': 'Евро-3',
        }
    ]
    assert payload['preferentialPrograms'] == [
        {
            'id': customer_profile.preferential_programs.get().pk,
            'name': 'Семейная ипотека',
        }
    ]
    assert payload['calculated']['maximumTermYears'] == 30
    assert payload['calculated']['actualKeyRate'] == '16.00'
    assert payload['calculated']['annualRate'] == '18.00'
    assert payload['calculated']['maximumPropertyCost'] is not None
    assert payload['calculated']['preferentialCreditLimit'] == '12000000.00'
    assert (
        payload['calculated']['preferentialMaximumPropertyCost']
        == '14000000.00'
    )
    assert payload['legacyDetailUrl'] == reverse(
        'customer:detail',
        kwargs={'pk': customer_profile.pk},
    )

    client.force_login(other_owner)
    hidden_response = client.get(
        reverse(
            'api_v1:customer_detail',
            kwargs={'pk': customer_profile.pk},
        )
    )

    assert hidden_response.status_code == 404


@pytest.mark.django_db
def test_application_administrator_can_view_all_customers(
    client,
    customer_users,
    customer_profile,
):
    """Preserve established administrator access to all customer records."""
    _owner, other_owner = customer_users
    other_customer = Customer.objects.create(
        user=other_owner,
        first_name='Елена',
        last_name='Волкова',
    )
    administrator = get_user_model().objects.create_superuser(
        email='customer-admin-api@example.com',
        password='safe-test-password',
        phone_number='+79992220003',
    )
    client.force_login(administrator)

    list_response = client.get(
        reverse('api_v1:customer_list'),
        {'ordering': 'name'},
    )
    detail_response = client.get(
        reverse(
            'api_v1:customer_detail',
            kwargs={'pk': other_customer.pk},
        )
    )

    assert list_response.status_code == 200
    assert {
        result['id']
        for result in list_response.json()['results']
    } == {customer_profile.pk, other_customer.pk}
    assert detail_response.status_code == 200


@pytest.mark.django_db
def test_customer_endpoints_use_bounded_query_counts(
    client,
    customer_users,
    customer_profile,
    django_assert_num_queries,
):
    """Prevent list and detail endpoints from adding per-customer queries."""
    owner, _other_owner = customer_users
    client.force_login(owner)

    with django_assert_num_queries(5):
        list_response = client.get(reverse('api_v1:customer_list'))
    with django_assert_num_queries(10):
        detail_response = client.get(
            reverse(
                'api_v1:customer_detail',
                kwargs={'pk': customer_profile.pk},
            )
        )

    assert list_response.status_code == 200
    assert detail_response.status_code == 200
