from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from bank.models import Bank, DeveloperMortgageProgram, MortgageProgram
from location.models import City, District, Region
from property.models import (
    CompanyGroup,
    Developer,
    RealEstateClass,
    RealEstateComplex,
    RealEstateType,
)
from users.roles import MODERATOR_GROUP_NAME


def create_complex(company_group, suffix):
    """Create one complete residential complex for an API fixture."""
    region = Region.objects.create(name=f'Регион {suffix}', code=f'R{suffix}')
    city = City.objects.create(name=f'Город {suffix}', region=region)
    district = District.objects.create(name=f'Район {suffix}', city=city)
    developer = Developer.objects.create(
        name=f'Застройщик {suffix}',
        company_group=company_group,
    )
    real_estate_class = RealEstateClass.objects.create(
        name=f'Класс {suffix}',
        weight=Decimal('1'),
    )
    real_estate_type = RealEstateType.objects.create(name=f'Тип {suffix}')
    return RealEstateComplex.objects.create(
        name=f'ЖК {suffix}',
        developer=developer,
        district=district,
        real_estate_class=real_estate_class,
        real_estate_type=real_estate_type,
    )


@pytest.fixture
def developer_program_catalog(db):
    """Create related catalogs and two representative developer programs."""
    company_group = CompanyGroup.objects.create(name='Группа Север')
    other_company_group = CompanyGroup.objects.create(name='Группа Юг')
    real_estate_complex = create_complex(company_group, 'Север')
    other_complex = create_complex(other_company_group, 'Юг')
    bank = Bank.objects.create(name='Тест Банк')
    other_bank = Bank.objects.create(name='Архив Банк', is_active=False)
    mortgage_program = MortgageProgram.objects.create(
        name='Семейная ипотека',
        condition='Для семей с детьми',
        is_preferential=True,
    )
    market_program = MortgageProgram.objects.create(
        name='Рыночная ипотека',
        condition='Стандартные условия',
    )
    developer_program = DeveloperMortgageProgram.objects.create(
        company_group=company_group,
        real_estate_complex=real_estate_complex,
        bank=bank,
        mortgage_program=mortgage_program,
        price_increase_percent=Decimal('-1.25'),
        grace_period_months=24,
        grace_period_interest_rate=Decimal('0.10'),
        minimum_initial_payment_percent=Decimal('20.10'),
        interest_rate=Decimal('4.30'),
        maximum_loan_term_years=30,
        maximum_loan_amount=Decimal('12000000.00'),
        rate_discount_percent=Decimal('0.50'),
        source_key='fixture-source-key',
        source_record_id=91,
    )
    inactive_program = DeveloperMortgageProgram.objects.create(
        company_group=other_company_group,
        bank=other_bank,
        mortgage_program=market_program,
        is_active=False,
    )
    return {
        'bank': bank,
        'company_group': company_group,
        'developer_program': developer_program,
        'inactive_program': inactive_program,
        'market_program': market_program,
        'mortgage_program': mortgage_program,
        'other_complex': other_complex,
        'other_company_group': other_company_group,
        'real_estate_complex': real_estate_complex,
    }


def create_catalog_manager():
    """Create a user allowed to manage shared catalog records."""
    user = get_user_model().objects.create_user(
        email='developer-program-manager@example.com',
        password='safe-test-password',
        phone_number='+79990000221',
    )
    moderator_group, _ = Group.objects.get_or_create(
        name=MODERATOR_GROUP_NAME
    )
    user.groups.add(moderator_group)
    return user


@pytest.mark.django_db
def test_developer_program_list_is_public_filtered_and_query_efficient(
    client,
    developer_program_catalog,
    django_assert_num_queries,
):
    """Return one filtered row with all references in two queries."""
    with django_assert_num_queries(2):
        response = client.get(
            reverse('api_v1:developer_mortgage_program_list'),
            {
                'q': 'семейная',
                'companyGroupId': (
                    developer_program_catalog['company_group'].pk
                ),
                'bankId': developer_program_catalog['bank'].pk,
                'status': 'active',
                'ordering': 'interestRate',
            },
        )

    assert response.status_code == 200
    assert response.json()['totalCount'] == 1
    row = response.json()['results'][0]
    assert row['id'] == developer_program_catalog['developer_program'].pk
    assert row['companyGroupName'] == 'Группа Север'
    assert row['realEstateComplexName'] == 'ЖК Север'
    assert row['bankName'] == 'Тест Банк'
    assert row['mortgageProgramName'] == 'Семейная ипотека'
    assert row['interestRate'] == '4.30'
    assert row['detailUrl'] == (
        '/developer-programs/'
        f"{developer_program_catalog['developer_program'].pk}"
    )


@pytest.mark.django_db
def test_developer_program_list_serializes_group_wide_inactive_conditions(
    client,
    developer_program_catalog,
):
    """Represent an inactive group-wide program with explicit null scope."""
    response = client.get(
        reverse('api_v1:developer_mortgage_program_list'),
        {'status': 'inactive'},
    )

    assert response.status_code == 200
    assert response.json()['totalCount'] == 1
    row = response.json()['results'][0]
    assert row['id'] == developer_program_catalog['inactive_program'].pk
    assert row['realEstateComplexId'] is None
    assert row['realEstateComplexName'] is None
    assert row['complexDeveloperName'] is None


@pytest.mark.django_db
def test_developer_program_detail_is_public_safe_and_query_efficient(
    client,
    developer_program_catalog,
    django_assert_num_queries,
):
    """Expose full conditions without internal import identity fields."""
    with django_assert_num_queries(1):
        response = client.get(
            reverse(
                'api_v1:developer_mortgage_program_detail',
                kwargs={
                    'pk': developer_program_catalog['developer_program'].pk,
                },
            )
        )

    assert response.status_code == 200
    assert response.json()['maximumLoanAmount'] == '12000000.00'
    assert response.json()['gracePeriodMonths'] == 24
    assert 'sourceKey' not in response.json()
    assert 'sourceRecordId' not in response.json()
    assert response.json()['legacyCatalogUrl'] == '/bank/developer-programs/'


@pytest.mark.django_db
def test_developer_program_options_are_public_bounded_and_group_scoped(
    client,
    developer_program_catalog,
    settings,
):
    """Bound all option lists and restrict complexes to their group."""
    settings.PUBLIC_CATALOG_API_MAX_RESULTS = 1
    response = client.get(
        reverse('api_v1:developer_mortgage_program_options'),
        {
            'companyGroupId': (
                developer_program_catalog['company_group'].pk
            )
        },
    )

    assert response.status_code == 200
    assert len(response.json()['companyGroups']) == 1
    assert len(response.json()['banks']) == 1
    assert len(response.json()['mortgagePrograms']) == 1
    assert response.json()['realEstateComplexes'] == [
        {
            'id': developer_program_catalog['real_estate_complex'].pk,
            'name': 'ЖК Север (Застройщик Север)',
        }
    ]
    assert response.json()['truncated']['companyGroups'] is True
    assert response.json()['truncated']['banks'] is True


@pytest.mark.django_db
def test_developer_program_mutations_require_catalog_permission(
    client,
    developer_program_catalog,
):
    """Reject writes from an authenticated user without catalog rights."""
    regular_user = get_user_model().objects.create_user(
        email='developer-program-user@example.com',
        password='safe-test-password',
        phone_number='+79990000222',
    )
    client.force_login(regular_user)
    response = client.post(
        reverse('api_v1:developer_mortgage_program_list'),
        data={
            'companyGroupId': developer_program_catalog['company_group'].pk,
            'bankId': developer_program_catalog['bank'].pk,
            'mortgageProgramId': (
                developer_program_catalog['mortgage_program'].pk
            ),
        },
        content_type='application/json',
    )

    assert response.status_code == 403
    assert DeveloperMortgageProgram.objects.count() == 2


@pytest.mark.django_db
def test_catalog_manager_can_create_update_and_delete_developer_program(
    client,
    developer_program_catalog,
):
    """Support the complete manager lifecycle without changing source data."""
    client.force_login(create_catalog_manager())
    create_response = client.post(
        reverse('api_v1:developer_mortgage_program_list'),
        data={
            'companyGroupId': developer_program_catalog['company_group'].pk,
            'realEstateComplexId': None,
            'bankId': developer_program_catalog['bank'].pk,
            'mortgageProgramId': (
                developer_program_catalog['market_program'].pk
            ),
            'priceIncreasePercent': '-2.25',
            'gracePeriodMonths': 18,
            'gracePeriodInterestRate': '1.50',
            'minimumInitialPaymentPercent': '25.00',
            'interestRate': '7.20',
            'maximumLoanTermYears': 25,
            'maximumLoanAmount': '10000000.00',
            'rateDiscountPercent': '0.75',
            'isActive': True,
        },
        content_type='application/json',
    )

    assert create_response.status_code == 201, create_response.json()
    created_program = DeveloperMortgageProgram.objects.get(
        pk=create_response.json()['id']
    )
    assert created_program.real_estate_complex is None
    assert created_program.price_increase_percent == Decimal('-2.25')

    source_program = developer_program_catalog['developer_program']
    update_response = client.patch(
        reverse(
            'api_v1:developer_mortgage_program_detail',
            kwargs={'pk': source_program.pk},
        ),
        data={
            'interestRate': '4.10',
            'gracePeriodMonths': None,
            'isActive': False,
        },
        content_type='application/json',
    )
    assert update_response.status_code == 200, update_response.json()
    source_program.refresh_from_db()
    assert source_program.interest_rate == Decimal('4.10')
    assert source_program.grace_period_months is None
    assert source_program.source_key == 'fixture-source-key'
    assert source_program.source_record_id == 91

    delete_response = client.delete(
        reverse(
            'api_v1:developer_mortgage_program_detail',
            kwargs={'pk': created_program.pk},
        )
    )
    assert delete_response.status_code == 204
    assert not DeveloperMortgageProgram.objects.filter(
        pk=created_program.pk
    ).exists()


@pytest.mark.django_db
def test_developer_program_api_validates_scope_and_financial_ranges(
    client,
    developer_program_catalog,
):
    """Reject a foreign complex and invalid percentage values."""
    client.force_login(create_catalog_manager())
    list_url = reverse('api_v1:developer_mortgage_program_list')
    scope_response = client.post(
        list_url,
        data={
            'companyGroupId': developer_program_catalog['company_group'].pk,
            'realEstateComplexId': (
                developer_program_catalog['other_complex'].pk
            ),
            'bankId': developer_program_catalog['bank'].pk,
            'mortgageProgramId': (
                developer_program_catalog['mortgage_program'].pk
            ),
        },
        content_type='application/json',
    )
    ranges_response = client.post(
        list_url,
        data={
            'companyGroupId': developer_program_catalog['company_group'].pk,
            'bankId': developer_program_catalog['bank'].pk,
            'mortgageProgramId': (
                developer_program_catalog['mortgage_program'].pk
            ),
            'interestRate': '101.00',
            'minimumInitialPaymentPercent': '-1.00',
            'maximumLoanAmount': '-100.00',
            'gracePeriodMonths': 0,
        },
        content_type='application/json',
    )

    assert scope_response.status_code == 400
    assert 'realEstateComplexId' in scope_response.json()
    assert ranges_response.status_code == 400
    assert 'interestRate' in ranges_response.json()
    assert 'minimumInitialPaymentPercent' in ranges_response.json()
    assert 'maximumLoanAmount' in ranges_response.json()
    assert 'gracePeriodMonths' in ranges_response.json()
    assert DeveloperMortgageProgram.objects.count() == 2
