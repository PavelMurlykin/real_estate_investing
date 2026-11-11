from datetime import date
from decimal import Decimal, localcontext

import pytest

from mortgage.mortgage_calculator import MortgageCalculator


@pytest.mark.parametrize(
    ('price', 'rate', 'months', 'grace_months', 'grace_rate'),
    [
        ('5000000', '100', 600, 0, '0'),
        ('5000000', '100', 360, 0, '0'),
        ('5000000', '50', 600, 0, '0'),
        ('9999999999999.99', '0.01', 360, 0, '0'),
        ('9999999999999.99', '100', 600, 0, '0'),
        ('5000000', '0', 13, 0, '0'),
        ('0.01', '0', 3, 0, '0'),
        ('5000000', '100', 600, 599, '0'),
        ('5000000', '15', 360, 12, '6'),
    ],
)
def test_schedule_repays_principal_and_balances_every_kopeck(
    price, rate, months, grace_months, grace_rate,
):
    """Keep every row and the public summary balanced at supported boundaries."""
    calculator = MortgageCalculator(
        property_cost=Decimal(price),
        initial_payment_percent=Decimal('20'),
        initial_payment_date=date(2026, 11, 11),
        mortgage_term=months,
        annual_rate=Decimal(rate),
        has_grace_period=bool(grace_months),
        grace_period_term=grace_months,
        grace_period_rate=Decimal(grace_rate),
    )
    summary = calculator.calculate()
    schedule = calculator.get_payment_schedule()
    principal = Decimal(str(summary['total_loan_amount']))
    balance = principal
    total_interest = Decimal('0')
    total_payments = Decimal('0')
    for row in schedule:
        payment = Decimal(str(row['payment_amount']))
        interest = Decimal(str(row['interest_amount']))
        repaid = Decimal(str(row['principal_amount']))
        remaining = Decimal(str(row['remaining_debt']))
        assert payment == interest + repaid
        assert remaining == balance - repaid
        assert min(payment, interest, repaid, remaining) >= 0
        balance = remaining
        total_interest += interest
        total_payments += payment
    assert len(schedule) == months
    assert balance == 0
    assert total_payments == principal + total_interest
    assert Decimal(str(summary['total_overpayment'])) == total_interest
    assert calculator.calculate() == summary


def test_maximum_rate_keeps_the_expected_annuity_payment():
    """Cross-check the nominal payment with a discounted cash flow reference."""
    with localcontext() as context:
        context.prec = 80
        principal = Decimal('4000000')
        monthly_rate = Decimal(1) / 12
        expected = principal / sum(
            ((1 + monthly_rate) ** -number for number in range(1, 601)),
            Decimal(0),
        )
    calculator = MortgageCalculator(
        property_cost=5000000,
        initial_payment_percent=20,
        initial_payment_date=date(2026, 11, 11),
        mortgage_term=600,
        annual_rate=100,
    )
    assert Decimal(str(calculator.calculate()['main_monthly_payment'])) == (
        expected.quantize(Decimal('0.01'))
    )
