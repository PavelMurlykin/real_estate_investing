from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from bank.models import (
    Bank,
    BankProgram,
    DeveloperMortgageProgram,
    MortgageProgram,
)
from property.models import CompanyGroup
from users.roles import MODERATOR_GROUP_NAME


@pytest.fixture
def bank_catalog():
    """Create a bank with canonical programs and one empty bank."""
    family_program = MortgageProgram.objects.create(
        name='Семейная ипотека',
        condition='Для семей с детьми',
        is_preferential=True,
    )
    market_program = MortgageProgram.objects.create(
        name='Рыночная ипотека',
        condition='Стандартные условия',
    )
    bank = Bank.objects.create(
        name='Тест Банк',
        logo_url='https://example.com/test-bank.svg',
    )
    bank_program = BankProgram.objects.create(
        bank=bank,
        mortgage_program=family_program,
        interest_rate=Decimal('5.90'),
        minimum_initial_payment_percent=Decimal('20.10'),
        maximum_loan_term_years=30,
    )
    empty_bank = Bank.objects.create(
        name='Архив Банк',
        is_active=False,
    )
    return {
        'bank': bank,
        'bank_program': bank_program,
        'empty_bank': empty_bank,
        'family_program': family_program,
        'market_program': market_program,
    }


def create_catalog_manager():
    """Create a user allowed to mutate shared bank catalog data."""
    user = get_user_model().objects.create_user(
        email='bank-moderator@example.com',
        password='safe-test-password',
        phone_number='+79990000201',
    )
    moderator_group, _ = Group.objects.get_or_create(
        name=MODERATOR_GROUP_NAME
    )
    user.groups.add(moderator_group)
    return user


@pytest.mark.django_db
def test_bank_list_is_public_filtered_and_query_efficient(
    client,
    bank_catalog,
    django_assert_num_queries,
):
    """Return aggregate bank rows with bounded database work."""
    with django_assert_num_queries(2):
        response = client.get(
            reverse('api_v1:bank_list'),
            {
                'q': 'тест',
                'scope': 'withPrograms',
                'status': 'active',
                'ordering': 'minimumInterestRate',
            },
        )

    assert response.status_code == 200
    assert response.json()['totalCount'] == 1
    assert response.json()['results'] == [
        {
            'id': bank_catalog['bank'].pk,
            'name': 'Тест Банк',
            'logoUrl': 'https://example.com/test-bank.svg',
            'programCount': 1,
            'minimumInterestRate': '5.90',
            'isActive': True,
            'updatedAt': response.json()['results'][0]['updatedAt'],
            'detailUrl': f"/banks/{bank_catalog['bank'].pk}",
            'legacyDetailUrl': f"/bank/banks/{bank_catalog['bank'].pk}/",
        }
    ]


@pytest.mark.django_db
def test_bank_list_can_select_inactive_banks_without_programs(
    client,
    bank_catalog,
):
    """Support the old catalog's program scope and explicit status filter."""
    response = client.get(
        reverse('api_v1:bank_list'),
        {'scope': 'withoutPrograms', 'status': 'inactive'},
    )

    assert response.status_code == 200
    assert [row['id'] for row in response.json()['results']] == [
        bank_catalog['empty_bank'].pk
    ]
    assert response.json()['results'][0]['minimumInterestRate'] is None


@pytest.mark.django_db
def test_bank_detail_is_public_complete_and_query_efficient(
    client,
    bank_catalog,
    django_assert_num_queries,
):
    """Return the bank card and its ordered program conditions."""
    with django_assert_num_queries(2):
        response = client.get(
            reverse(
                'api_v1:bank_detail',
                kwargs={'pk': bank_catalog['bank'].pk},
            )
        )

    assert response.status_code == 200
    assert response.json()['name'] == 'Тест Банк'
    assert response.json()['programs'] == [
        {
            'id': bank_catalog['bank_program'].pk,
            'mortgageProgramId': bank_catalog['family_program'].pk,
            'mortgageProgramName': 'Семейная ипотека',
            'interestRate': '5.90',
            'minimumInitialPaymentPercent': '20.10',
            'maximumLoanTermYears': 30,
        }
    ]
    assert response.json()['legacyEditUrl'] == (
        f"/bank/banks/{bank_catalog['bank'].pk}/edit/"
    )
    assert response.json()['legacyDetailUrl'] == (
        f"/bank/banks/{bank_catalog['bank'].pk}/"
    )
    assert response.json()['legacyCatalogUrl'] == '/bank/?model=bank'


@pytest.mark.django_db
def test_bank_options_are_public_and_bounded(
    client,
    bank_catalog,
    settings,
):
    """Expose bounded canonical program choices with truncation metadata."""
    settings.PUBLIC_CATALOG_API_MAX_RESULTS = 1

    response = client.get(reverse('api_v1:bank_options'))

    assert response.status_code == 200
    assert len(response.json()['mortgagePrograms']) == 1
    assert response.json()['truncated'] is True
    assert set(response.json()['mortgagePrograms'][0]) == {'id', 'name'}


@pytest.mark.django_db
def test_bank_mutations_require_catalog_permission(client, bank_catalog):
    """Reject bank changes from a regular authenticated user."""
    regular_user = get_user_model().objects.create_user(
        email='bank-regular@example.com',
        password='safe-test-password',
        phone_number='+79990000202',
    )
    client.force_login(regular_user)

    response = client.post(
        reverse('api_v1:bank_list'),
        data={'name': 'Новый банк', 'programs': []},
        content_type='application/json',
    )

    assert response.status_code == 403
    assert not Bank.objects.filter(name='Новый банк').exists()


@pytest.mark.django_db
def test_catalog_manager_can_create_bank_with_programs(client, bank_catalog):
    """Create a normalized bank and its complete nested program table."""
    client.force_login(create_catalog_manager())

    response = client.post(
        reverse('api_v1:bank_list'),
        data={
            'name': '  Новый   банк  ',
            'logoUrl': 'https://example.com/new-bank.png',
            'isActive': True,
            'programs': [
                {
                    'mortgageProgramId': bank_catalog['family_program'].pk,
                    'interestRate': '6.00',
                    'minimumInitialPaymentPercent': '20.00',
                    'maximumLoanTermYears': 25,
                },
                {
                    'mortgageProgramId': bank_catalog['market_program'].pk,
                    'interestRate': '18.50',
                    'minimumInitialPaymentPercent': '30.00',
                    'maximumLoanTermYears': None,
                },
            ],
        },
        content_type='application/json',
    )

    assert response.status_code == 201, response.json()
    bank = Bank.objects.get(name='Новый банк')
    assert bank.logo_url == 'https://example.com/new-bank.png'
    assert response.json()['id'] == bank.pk
    assert len(response.json()['programs']) == 2
    assert BankProgram.objects.filter(bank=bank).count() == 2


@pytest.mark.django_db
def test_catalog_manager_patch_replaces_submitted_bank_programs(
    client,
    bank_catalog,
):
    """Replace nested program rows atomically while updating bank fields."""
    client.force_login(create_catalog_manager())
    response = client.patch(
        reverse(
            'api_v1:bank_detail',
            kwargs={'pk': bank_catalog['bank'].pk},
        ),
        data={
            'name': 'Тест Банк Обновлённый',
            'isActive': False,
            'programs': [
                {
                    'mortgageProgramId': bank_catalog['market_program'].pk,
                    'interestRate': '17.25',
                    'minimumInitialPaymentPercent': '25.00',
                    'maximumLoanTermYears': 20,
                }
            ],
        },
        content_type='application/json',
    )

    assert response.status_code == 200, response.json()
    bank_catalog['bank'].refresh_from_db()
    assert bank_catalog['bank'].name == 'Тест Банк Обновлённый'
    assert bank_catalog['bank'].is_active is False
    saved_programs = BankProgram.objects.filter(bank=bank_catalog['bank'])
    assert saved_programs.count() == 1
    assert saved_programs.get().mortgage_program == (
        bank_catalog['market_program']
    )
    assert response.json()['programs'][0]['interestRate'] == '17.25'


@pytest.mark.django_db
def test_bank_api_validates_duplicates_and_program_values(
    client,
    bank_catalog,
):
    """Reject duplicate names, duplicate program rows, and invalid values."""
    client.force_login(create_catalog_manager())
    list_url = reverse('api_v1:bank_list')

    duplicate_name_response = client.post(
        list_url,
        data={'name': '  тест банк  ', 'programs': []},
        content_type='application/json',
    )
    duplicate_program_response = client.post(
        list_url,
        data={
            'name': 'Ещё один банк',
            'programs': [
                {
                    'mortgageProgramId': bank_catalog['family_program'].pk,
                    'interestRate': '6.00',
                    'minimumInitialPaymentPercent': '20.00',
                    'maximumLoanTermYears': 30,
                },
                {
                    'mortgageProgramId': bank_catalog['family_program'].pk,
                    'interestRate': '7.00',
                    'minimumInitialPaymentPercent': '25.00',
                    'maximumLoanTermYears': 20,
                },
            ],
        },
        content_type='application/json',
    )
    invalid_values_response = client.post(
        list_url,
        data={
            'name': 'Банк с ошибками',
            'logoUrl': 'not-a-url',
            'programs': [
                {
                    'mortgageProgramId': bank_catalog['market_program'].pk,
                    'interestRate': '-1.00',
                    'minimumInitialPaymentPercent': '-5.00',
                    'maximumLoanTermYears': 0,
                }
            ],
        },
        content_type='application/json',
    )

    assert duplicate_name_response.status_code == 400
    assert 'name' in duplicate_name_response.json()
    assert duplicate_program_response.status_code == 400
    assert 'programs' in duplicate_program_response.json()
    assert invalid_values_response.status_code == 400
    assert 'logoUrl' in invalid_values_response.json()
    program_errors = invalid_values_response.json()['programs']['0']
    assert 'interestRate' in program_errors
    assert 'minimumInitialPaymentPercent' in (
        program_errors
    )
    assert 'maximumLoanTermYears' in (
        program_errors
    )


@pytest.mark.django_db
def test_bank_delete_reports_protected_links_and_deletes_unused(
    client,
    bank_catalog,
):
    """Return a conflict for referenced banks and delete unused banks."""
    client.force_login(create_catalog_manager())
    DeveloperMortgageProgram.objects.create(
        company_group=CompanyGroup.objects.create(name='Тестовая группа'),
        bank=bank_catalog['bank'],
        mortgage_program=bank_catalog['family_program'],
    )

    conflict_response = client.delete(
        reverse(
            'api_v1:bank_detail',
            kwargs={'pk': bank_catalog['bank'].pk},
        )
    )
    delete_response = client.delete(
        reverse(
            'api_v1:bank_detail',
            kwargs={'pk': bank_catalog['empty_bank'].pk},
        )
    )

    assert conflict_response.status_code == 409
    assert 'программах застройщиков' in conflict_response.json()['detail']
    assert Bank.objects.filter(pk=bank_catalog['bank'].pk).exists()
    assert delete_response.status_code == 204
    assert not Bank.objects.filter(pk=bank_catalog['empty_bank'].pk).exists()
    assert MortgageProgram.objects.count() == 2
