from decimal import Decimal, ROUND_HALF_UP

from mortgage.mortgage_calculator import MortgageCalculator


MONEY_QUANTUM = Decimal('0.01')
PERCENT_QUANTUM = Decimal('0.01')


def _format_decimal(value, quantum=MONEY_QUANTUM):
    """Return a stable decimal string for the public API contract."""
    decimal_value = Decimal(str(value)).quantize(
        quantum,
        rounding=ROUND_HALF_UP,
    )
    return format(decimal_value, 'f')


def _calculate_price_adjustment(validated_data):
    """Return normalized adjustment values and the resulting object cost."""
    property_cost = validated_data['propertyCost']
    adjustment_value = validated_data['priceAdjustmentValue']
    if validated_data['priceAdjustmentUnit'] == 'rubles':
        adjustment_rubles = adjustment_value
        adjustment_percent = adjustment_rubles / property_cost * 100
    else:
        adjustment_percent = adjustment_value
        adjustment_rubles = property_cost * adjustment_percent / 100

    if validated_data['priceAdjustmentType'] == 'discount':
        final_property_cost = property_cost - adjustment_rubles
    else:
        final_property_cost = property_cost + adjustment_rubles

    return adjustment_percent, adjustment_rubles, final_property_cost


def _calculate_initial_payment(validated_data, final_property_cost):
    """Return normalized initial payment values in percent and rubles."""
    initial_payment_value = validated_data['initialPaymentValue']
    if validated_data['initialPaymentUnit'] == 'rubles':
        initial_payment_rubles = initial_payment_value
        initial_payment_percent = (
            initial_payment_rubles / final_property_cost * 100
        )
    else:
        initial_payment_percent = initial_payment_value
        initial_payment_rubles = (
            final_property_cost * initial_payment_percent / 100
        )
    return initial_payment_percent, initial_payment_rubles


def _serialize_payment_schedule(payment_schedule):
    """Serialize payment rows with ISO dates and stable money strings."""
    return [
        {
            'paymentNumber': payment['payment_number'],
            'paymentDate': payment['payment_date'].isoformat(),
            'paymentAmount': _format_decimal(payment['payment_amount']),
            'interestAmount': _format_decimal(payment['interest_amount']),
            'principalAmount': _format_decimal(payment['principal_amount']),
            'remainingDebt': _format_decimal(payment['remaining_debt']),
        }
        for payment in payment_schedule
    ]


def calculate_market_mortgage(validated_data):
    """Calculate a market mortgage through the established domain service."""
    (
        adjustment_percent,
        adjustment_rubles,
        final_property_cost,
    ) = _calculate_price_adjustment(validated_data)
    (
        initial_payment_percent,
        initial_payment_rubles,
    ) = _calculate_initial_payment(validated_data, final_property_cost)

    has_grace_period = validated_data['hasGracePeriod']
    grace_period_term = validated_data['gracePeriodTermMonths'] or 0
    grace_period_rate = validated_data['gracePeriodRate'] or Decimal('0')
    calculator = MortgageCalculator(
        property_cost=float(final_property_cost),
        initial_payment_percent=float(initial_payment_percent),
        initial_payment_date=validated_data['initialPaymentDate'],
        mortgage_term=validated_data['mortgageTermMonths'],
        annual_rate=float(validated_data['annualRate']),
        has_grace_period=has_grace_period,
        grace_period_term=grace_period_term,
        grace_period_rate=float(grace_period_rate),
    )
    calculation_result = calculator.calculate()
    loan_amount = Decimal(str(calculation_result['total_loan_amount']))
    overpayment = Decimal(str(calculation_result['total_overpayment']))

    return {
        'assumptions': {
            'basePropertyCost': _format_decimal(
                validated_data['propertyCost']
            ),
            'priceAdjustmentType': validated_data['priceAdjustmentType'],
            'priceAdjustmentPercent': _format_decimal(
                adjustment_percent,
                PERCENT_QUANTUM,
            ),
            'priceAdjustmentRubles': _format_decimal(adjustment_rubles),
            'finalPropertyCost': _format_decimal(final_property_cost),
            'initialPaymentPercent': _format_decimal(
                initial_payment_percent,
                PERCENT_QUANTUM,
            ),
            'initialPaymentRubles': _format_decimal(initial_payment_rubles),
            'initialPaymentDate': validated_data[
                'initialPaymentDate'
            ].isoformat(),
            'mortgageTermMonths': validated_data['mortgageTermMonths'],
            'annualRate': _format_decimal(
                validated_data['annualRate'],
                PERCENT_QUANTUM,
            ),
            'hasGracePeriod': has_grace_period,
            'gracePeriodTermMonths': grace_period_term,
            'gracePeriodRate': (
                _format_decimal(grace_period_rate, PERCENT_QUANTUM)
                if has_grace_period
                else None
            ),
        },
        'summary': {
            'loanAmount': _format_decimal(loan_amount),
            'mainMonthlyPayment': _format_decimal(
                calculation_result['main_monthly_payment']
            ),
            'graceMonthlyPayment': (
                _format_decimal(calculation_result['grace_monthly_payment'])
                if has_grace_period
                else None
            ),
            'overpayment': _format_decimal(overpayment),
            'totalPayments': _format_decimal(loan_amount + overpayment),
            'paymentsCount': (
                calculation_result['grace_payments_count']
                + calculation_result['main_payments_count']
            ),
            'mortgageEndDate': calculation_result[
                'mortgage_end_date'
            ].isoformat(),
            'gracePeriodEndDate': (
                calculation_result['grace_period_end_date'].isoformat()
                if calculation_result['grace_period_end_date']
                else None
            ),
        },
        'schedule': _serialize_payment_schedule(
            calculator.get_payment_schedule()
        ),
    }
