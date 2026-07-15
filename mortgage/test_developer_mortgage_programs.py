"""Tests for developer mortgage programs on the calculator form."""

from decimal import Decimal

import pytest
from django.urls import reverse

from bank.models import Bank, DeveloperMortgageProgram, MortgageProgram
from property.models import CompanyGroup, Developer


@pytest.fixture
def developer_with_company_group(db):
    """Create a developer linked to a company group."""
    company_group = CompanyGroup.objects.create(name='ГК Север')
    developer = Developer.objects.create(
        name='Север Девелопмент',
        company_group=company_group,
    )
    return developer, company_group


@pytest.mark.django_db
def test_developer_program_api_returns_only_active_group_programs(
    client,
    django_assert_num_queries,
    developer_with_company_group,
):
    """Return active group conditions with one bounded database query."""
    developer, company_group = developer_with_company_group
    bank = Bank.objects.create(name='Банк Север')
    inactive_bank = Bank.objects.create(name='Банк Архив')
    mortgage_program = MortgageProgram.objects.create(
        name='Семейная ипотека',
        condition='Условия программы',
        is_preferential=True,
    )
    developer_program = DeveloperMortgageProgram.objects.create(
        company_group=company_group,
        bank=bank,
        mortgage_program=mortgage_program,
        price_increase_percent=Decimal('-2.50'),
        minimum_initial_payment_percent=Decimal('25.00'),
        maximum_loan_term_years=20,
        interest_rate=Decimal('5.75'),
        grace_period_months=24,
        grace_period_interest_rate=Decimal('1.50'),
    )
    DeveloperMortgageProgram.objects.create(
        company_group=company_group,
        bank=inactive_bank,
        mortgage_program=mortgage_program,
        is_active=False,
    )
    other_company_group = CompanyGroup.objects.create(name='ГК Юг')
    DeveloperMortgageProgram.objects.create(
        company_group=other_company_group,
        bank=inactive_bank,
        mortgage_program=mortgage_program,
    )

    with django_assert_num_queries(1):
        response = client.get(
            reverse('mortgage:developer_mortgage_programs_api'),
            {'developer': developer.pk},
        )

    assert response.status_code == 200
    assert response.json() == {
        'has_programs': True,
        'bank_ids': [bank.pk],
        'programs': [
            {
                'id': developer_program.pk,
                'bank_id': bank.pk,
                'bank_name': bank.name,
                'mortgage_program_id': mortgage_program.pk,
                'mortgage_program_name': mortgage_program.name,
                'real_estate_complex_id': '',
                'real_estate_complex_name': '',
                'price_increase_percent': '-2.50',
                'minimum_initial_payment_percent': '25.00',
                'maximum_loan_term_years': 20,
                'interest_rate': '5.75',
                'grace_period_months': 24,
                'grace_period_interest_rate': '1.50',
            }
        ],
    }


@pytest.mark.django_db
@pytest.mark.parametrize('developer_value', ['', 'invalid', '-1', '999999'])
def test_developer_program_api_returns_full_bank_fallback(
    client,
    developer_value,
):
    """Return an empty payload when the developer has no directory rows."""
    response = client.get(
        reverse('mortgage:developer_mortgage_programs_api'),
        {'developer': developer_value},
    )

    assert response.status_code == 200
    assert response.json() == {
        'has_programs': False,
        'bank_ids': [],
        'programs': [],
    }


@pytest.mark.django_db
def test_mortgage_form_exposes_developer_program_integration(client):
    """Render the endpoint URL and status message target on the form."""
    response = client.get(reverse('mortgage:mortgage_calculator'))
    response_content = response.content.decode()

    assert response.status_code == 200
    assert 'id="developer-mortgage-program-message"' in response_content
    assert (
        'data-developer-mortgage-programs-api-url="'
        + reverse('mortgage:developer_mortgage_programs_api')
        + '"'
    ) in response_content
    assert '20260715-developer-programs-1' in response_content
