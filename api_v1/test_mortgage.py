from datetime import date
from decimal import Decimal

import pytest
from django.test import Client
from django.urls import reverse

from bank.models import (
    Bank, BankProgram, DeveloperMortgageProgram, KeyRate, MortgageProgram,
)
from property.models import CompanyGroup, Developer


def build_mortgage_payload(**overrides):
    """Return a valid API payload with optional field overrides."""
    payload = {
        'propertyCost': '5000000.00',
        'priceAdjustmentType': 'discount',
        'priceAdjustmentUnit': 'percent',
        'priceAdjustmentValue': '10.00',
        'initialPaymentUnit': 'percent',
        'initialPaymentValue': '20.00',
        'initialPaymentDate': '2026-01-15',
        'mortgageTermMonths': 12,
        'annualRate': '12.00',
        'hasGracePeriod': False,
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_mortgage_options_api_returns_active_programs_in_three_queries(
    client,
    django_assert_num_queries,
):
    """Return active bank programs without an unbounded query pattern."""
    bank = Bank.objects.create(name='Надёжный банк')
    inactive_bank = Bank.objects.create(name='Архивный банк', is_active=False)
    mortgage_program = MortgageProgram.objects.create(
        name='Семейная ипотека',
        condition='Для семей с детьми',
        is_preferential=True,
        credit_limit=Decimal('12000000.00'),
    )
    bank_program = BankProgram.objects.create(
        bank=bank,
        mortgage_program=mortgage_program,
        interest_rate=Decimal('6.00'),
        minimum_initial_payment_percent=Decimal('20.00'),
        maximum_loan_term_years=30,
    )
    BankProgram.objects.create(
        bank=inactive_bank,
        mortgage_program=mortgage_program,
        interest_rate=Decimal('8.00'),
    )
    KeyRate.objects.create(
        meeting_date=date(2026, 1, 1),
        key_rate=Decimal('16.00'),
    )

    with django_assert_num_queries(3):
        response = client.get(reverse('api_v1:mortgage_options'))

    assert response.status_code == 200
    payload = response.json()
    assert payload['keyRate'] == '16.00'
    assert payload['banks'] == [
        {'id': bank.pk, 'name': bank.name, 'logoUrl': ''}
    ]
    assert payload['programs'] == [
        {
            'id': bank_program.pk,
            'bankId': bank.pk,
            'programId': mortgage_program.pk,
            'programName': mortgage_program.name,
            'interestRate': '6.00',
            'minimumInitialPaymentPercent': '20.00',
            'maximumLoanTermYears': 30,
            'isPreferential': True,
            'creditLimit': '12000000.00',
            'regionalCreditLimits': [],
        }
    ]


@pytest.mark.django_db
def test_mortgage_calculation_api_returns_summary_and_schedule(client):
    """Calculate normalized monetary values and a bounded payment schedule."""
    response = client.post(
        reverse('api_v1:mortgage_calculate'),
        data=build_mortgage_payload(),
        content_type='application/json',
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['assumptions']['basePropertyCost'] == '5000000.00'
    assert payload['assumptions']['priceAdjustmentRubles'] == '500000.00'
    assert payload['assumptions']['finalPropertyCost'] == '4500000.00'
    assert payload['assumptions']['initialPaymentRubles'] == '900000.00'
    assert payload['summary']['loanAmount'] == '3600000.00'
    assert payload['summary']['loanAfterGrace'] == '3600000.00'
    assert payload['summary']['gracePaymentsCount'] == 0
    assert payload['summary']['mainPaymentsCount'] == 12
    assert payload['summary']['paymentsCount'] == 12
    assert payload['summary']['mortgageEndDate'] == '2027-01-15'
    assert len(payload['schedule']) == 12
    assert payload['schedule'][0]['paymentNumber'] == 1
    assert payload['schedule'][0]['paymentDate'] == '2026-01-15'
    assert payload['schedule'][-1]['paymentNumber'] == 12


@pytest.mark.django_db
def test_mortgage_calculation_api_normalizes_ruble_inputs(client):
    """Preserve ruble-locked price and initial payment behavior."""
    response = client.post(
        reverse('api_v1:mortgage_calculate'),
        data=build_mortgage_payload(
            priceAdjustmentType='markup',
            priceAdjustmentUnit='rubles',
            priceAdjustmentValue='500000.00',
            initialPaymentUnit='rubles',
            initialPaymentValue='1000000.00',
        ),
        content_type='application/json',
    )

    assert response.status_code == 200
    assumptions = response.json()['assumptions']
    assert assumptions['priceAdjustmentPercent'] == '10.00'
    assert assumptions['finalPropertyCost'] == '5500000.00'
    assert assumptions['initialPaymentPercent'] == '18.18'
    assert assumptions['initialPaymentRubles'] == '1000000.00'


@pytest.mark.django_db
def test_mortgage_calculation_api_supports_grace_period(client):
    """Return separate grace and main period values when requested."""
    response = client.post(
        reverse('api_v1:mortgage_calculate'),
        data=build_mortgage_payload(
            mortgageTermMonths=24,
            hasGracePeriod=True,
            gracePeriodTermMonths=6,
            gracePeriodRate='6.00',
        ),
        content_type='application/json',
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['assumptions']['gracePeriodTermMonths'] == 6
    assert payload['summary']['graceMonthlyPayment'] is not None
    assert payload['summary']['gracePeriodEndDate'] == '2026-07-15'
    assert payload['summary']['paymentsCount'] == 24
    assert payload['summary']['gracePaymentsCount'] == 6
    assert payload['summary']['mainPaymentsCount'] == 18
    assert Decimal(payload['summary']['loanAfterGrace']) < Decimal('3600000')


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('overrides', 'error_field'),
    [
        ({'priceAdjustmentValue': '100.00'}, 'priceAdjustmentValue'),
        ({'initialPaymentValue': '101.00'}, 'initialPaymentValue'),
        (
            {
                'mortgageTermMonths': 24,
                'hasGracePeriod': True,
                'gracePeriodTermMonths': 24,
                'gracePeriodRate': '6.00',
            },
            'gracePeriodTermMonths',
        ),
    ],
)
def test_mortgage_calculation_api_rejects_cross_field_errors(
    client,
    overrides,
    error_field,
):
    """Return field-level errors for invalid financial combinations."""
    response = client.post(
        reverse('api_v1:mortgage_calculate'),
        data=build_mortgage_payload(**overrides),
        content_type='application/json',
    )

    assert response.status_code == 400
    assert error_field in response.json()


@pytest.mark.django_db
def test_mortgage_calculation_api_requires_csrf_when_checks_are_enabled():
    """Require a CSRF token for the calculator POST endpoint."""
    csrf_client = Client(enforce_csrf_checks=True)

    response = csrf_client.post(
        reverse('api_v1:mortgage_calculate'),
        data=build_mortgage_payload(),
        content_type='application/json',
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_mortgage_options_scope_conditions_to_developer_group(
    client, django_assert_num_queries,
):
    """Return only active group conditions without a query per program."""
    group = CompanyGroup.objects.create(name='Группа условий')
    developer = Developer.objects.create(name='Застройщик', company_group=group)
    other_group = CompanyGroup.objects.create(name='Другая группа')
    bank = Bank.objects.create(name='Банк')
    program = MortgageProgram.objects.create(name='Семейная', condition='Условия')
    BankProgram.objects.create(bank=bank, mortgage_program=program)
    expected = DeveloperMortgageProgram.objects.create(
        company_group=group, bank=bank, mortgage_program=program,
        price_increase_percent=Decimal('8'), interest_rate=Decimal('3'),
        minimum_initial_payment_percent=Decimal('25'),
        maximum_loan_term_years=25, grace_period_months=24,
        grace_period_interest_rate=Decimal('0'),
    )
    DeveloperMortgageProgram.objects.create(
        company_group=other_group, bank=bank, mortgage_program=program,
    )
    DeveloperMortgageProgram.objects.create(
        company_group=group, bank=bank, mortgage_program=program,
        is_active=False,
    )
    with django_assert_num_queries(4):
        response = client.get(reverse('api_v1:mortgage_options'), {
            'developerId': developer.pk,
        })
    assert response.status_code == 200
    conditions = response.json()['developerPrograms']
    assert [item['id'] for item in conditions] == [expected.pk]
    assert conditions[0]['priceIncreasePercent'] == '8.00'
    assert conditions[0]['gracePeriodInterestRate'] == '0.00'
    assert conditions[0]['interestRate'] == '3.00'
    assert client.get(reverse('api_v1:mortgage_options'), {
        'developerId': 'invalid',
    }).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize('has_grace', [False, True])
def test_interest_free_program_calculates_without_division_by_zero(
    client, has_grace,
):
    """Support explicit zero rates from subsidized developer programs."""
    response = client.post(
        reverse('api_v1:mortgage_calculate'),
        build_mortgage_payload(
            annualRate='0', hasGracePeriod=has_grace,
            gracePeriodTermMonths=3, gracePeriodRate='0',
        ),
        content_type='application/json',
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload['summary']['overpayment'] == '0.00'
    assert payload['summary']['mainMonthlyPayment'] == '300000.00'
    assert len(payload['schedule']) == 12
    assert payload['schedule'][-1]['remainingDebt'] == '0.00'
