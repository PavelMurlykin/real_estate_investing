from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from django.urls import reverse

from mortgage.mortgage_calculator import MortgageCalculator
from mortgage.models import MortgageCalculation


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


def create_saved_market_mortgage(parameters, property_object, user):
    """Recalculate and persist a property-backed mortgage scenario."""
    response_payload = calculate_market_mortgage(parameters)
    assumptions = response_payload['assumptions']
    summary = response_payload['summary']
    grace_payments_count = (
        assumptions['gracePeriodTermMonths']
        if assumptions['hasGracePeriod']
        else 0
    )
    loan_after_grace = summary['loanAmount']
    if grace_payments_count:
        loan_after_grace = response_payload['schedule'][
            grace_payments_count - 1
        ]['remainingDebt']

    return MortgageCalculation.objects.create(
        user=user,
        property=property_object,
        base_property_cost=Decimal(assumptions['basePropertyCost']),
        initial_payment_percent=Decimal(
            assumptions['initialPaymentPercent']
        ),
        initial_payment_date=parameters['initialPaymentDate'],
        mortgage_term=parameters['mortgageTermMonths'],
        annual_rate=parameters['annualRate'],
        has_grace_period=parameters['hasGracePeriod'],
        grace_period_term=parameters['gracePeriodTermMonths'] or 0,
        grace_period_rate=parameters['gracePeriodRate'] or Decimal('0'),
        discount_markup_type=parameters['priceAdjustmentType'],
        discount_markup_value=Decimal(
            assumptions['priceAdjustmentPercent']
        ),
        final_property_cost=Decimal(assumptions['finalPropertyCost']),
        grace_payments_count=grace_payments_count,
        grace_period_end_date=(
            date.fromisoformat(summary['gracePeriodEndDate'])
            if summary['gracePeriodEndDate']
            else None
        ),
        grace_monthly_payment=Decimal(
            summary['graceMonthlyPayment'] or '0'
        ),
        loan_after_grace=Decimal(loan_after_grace),
        main_payments_count=(
            assumptions['mortgageTermMonths'] - grace_payments_count
        ),
        mortgage_end_date=date.fromisoformat(summary['mortgageEndDate']),
        main_monthly_payment=Decimal(summary['mainMonthlyPayment']),
        total_loan_amount=Decimal(summary['loanAmount']),
        total_overpayment=Decimal(summary['overpayment']),
    )


def serialize_saved_property(property_object):
    """Return the property context shared by list and detail responses."""
    real_estate_complex = property_object.building.real_estate_complex
    return {
        'id': property_object.pk,
        'city': real_estate_complex.district.city.name,
        'developer': (
            real_estate_complex.developer
            .get_display_name_with_company_group()
        ),
        'realEstateComplex': real_estate_complex.name,
        'realEstateClass': real_estate_complex.real_estate_class.name,
        'building': property_object.building.number,
        'apartmentNumber': property_object.apartment_number,
        'layout': property_object.layout.name,
        'decoration': property_object.decoration.name,
        'area': _format_decimal(property_object.area),
        'floor': property_object.floor,
        'detailUrl': property_object.get_absolute_url(),
    }


def serialize_saved_mortgage_list_item(calculation, is_linked=False):
    """Serialize one bounded history row without additional queries."""
    initial_payment = (
        calculation.final_property_cost
        * calculation.initial_payment_percent
        / Decimal('100')
    )
    return {
        'id': calculation.pk,
        'createdAt': calculation.timestamp.isoformat(),
        'property': serialize_saved_property(calculation.property),
        'finalPropertyCost': _format_decimal(
            calculation.final_property_cost
        ),
        'initialPaymentRubles': _format_decimal(initial_payment),
        'mainMonthlyPayment': (
            _format_decimal(calculation.main_monthly_payment)
            if calculation.main_monthly_payment is not None
            else None
        ),
        'mortgageTermMonths': calculation.mortgage_term,
        'annualRate': _format_decimal(
            calculation.annual_rate,
            PERCENT_QUANTUM,
        ),
        'isLinked': is_linked,
    }


def _build_saved_mortgage_calculator(calculation):
    """Rebuild the calculator used by saved-detail and export views."""
    return MortgageCalculator(
        property_cost=float(calculation.final_property_cost),
        initial_payment_percent=float(calculation.initial_payment_percent),
        initial_payment_date=calculation.initial_payment_date,
        mortgage_term=calculation.mortgage_term,
        annual_rate=float(calculation.annual_rate),
        has_grace_period=calculation.has_grace_period,
        grace_period_term=calculation.grace_period_term or 0,
        grace_period_rate=float(calculation.grace_period_rate or 0),
    )


def build_saved_mortgage_payment_schedule(calculation):
    """Return the payment schedule expected by the existing file exporters."""
    calculator = _build_saved_mortgage_calculator(calculation)
    calculator.calculate()
    return calculator.get_payment_schedule()


def serialize_saved_mortgage_detail(calculation):
    """Serialize a saved scenario and rebuild its bounded payment schedule."""
    calculator = _build_saved_mortgage_calculator(calculation)
    recalculated_result = calculator.calculate()
    loan_amount = calculation.total_loan_amount
    if loan_amount is None:
        loan_amount = Decimal(str(recalculated_result['total_loan_amount']))
    overpayment = calculation.total_overpayment
    if overpayment is None:
        overpayment = Decimal(str(recalculated_result['total_overpayment']))
    main_monthly_payment = calculation.main_monthly_payment
    if main_monthly_payment is None:
        main_monthly_payment = Decimal(
            str(recalculated_result['main_monthly_payment'])
        )
    grace_monthly_payment = calculation.grace_monthly_payment
    if calculation.has_grace_period and grace_monthly_payment is None:
        grace_monthly_payment = Decimal(
            str(recalculated_result['grace_monthly_payment'])
        )
    mortgage_end_date = (
        calculation.mortgage_end_date
        or recalculated_result['mortgage_end_date']
    )
    grace_period_end_date = (
        calculation.grace_period_end_date
        or recalculated_result['grace_period_end_date']
    )
    price_adjustment_rubles = abs(
        calculation.final_property_cost - calculation.base_property_cost
    )
    initial_payment_rubles = (
        calculation.final_property_cost
        * calculation.initial_payment_percent
        / Decimal('100')
    )

    return {
        'id': calculation.pk,
        'createdAt': calculation.timestamp.isoformat(),
        'property': serialize_saved_property(calculation.property),
        'legacyDetailUrl': reverse(
            'mortgage:calculation_detail',
            kwargs={'pk': calculation.pk},
        ),
        'legacySampleUrl': (
            f"{reverse('mortgage:mortgage_calculator')}"
            f'?sample={calculation.pk}'
        ),
        'calculation': {
            'assumptions': {
                'basePropertyCost': _format_decimal(
                    calculation.base_property_cost
                ),
                'priceAdjustmentType': calculation.discount_markup_type,
                'priceAdjustmentPercent': _format_decimal(
                    calculation.discount_markup_value,
                    PERCENT_QUANTUM,
                ),
                'priceAdjustmentRubles': _format_decimal(
                    price_adjustment_rubles
                ),
                'finalPropertyCost': _format_decimal(
                    calculation.final_property_cost
                ),
                'initialPaymentPercent': _format_decimal(
                    calculation.initial_payment_percent,
                    PERCENT_QUANTUM,
                ),
                'initialPaymentRubles': _format_decimal(
                    initial_payment_rubles
                ),
                'initialPaymentDate': (
                    calculation.initial_payment_date.isoformat()
                ),
                'mortgageTermMonths': calculation.mortgage_term,
                'annualRate': _format_decimal(
                    calculation.annual_rate,
                    PERCENT_QUANTUM,
                ),
                'hasGracePeriod': calculation.has_grace_period,
                'gracePeriodTermMonths': (
                    calculation.grace_period_term or 0
                ),
                'gracePeriodRate': (
                    _format_decimal(
                        calculation.grace_period_rate or Decimal('0'),
                        PERCENT_QUANTUM,
                    )
                    if calculation.has_grace_period
                    else None
                ),
            },
            'summary': {
                'loanAmount': _format_decimal(loan_amount),
                'mainMonthlyPayment': _format_decimal(
                    main_monthly_payment
                ),
                'graceMonthlyPayment': (
                    _format_decimal(grace_monthly_payment)
                    if calculation.has_grace_period
                    else None
                ),
                'overpayment': _format_decimal(overpayment),
                'totalPayments': _format_decimal(
                    loan_amount + overpayment
                ),
                'paymentsCount': (
                    calculation.grace_payments_count
                    if calculation.grace_payments_count is not None
                    else recalculated_result['grace_payments_count']
                ) + (
                    calculation.main_payments_count
                    if calculation.main_payments_count is not None
                    else recalculated_result['main_payments_count']
                ),
                'mortgageEndDate': mortgage_end_date.isoformat(),
                'gracePeriodEndDate': (
                    grace_period_end_date.isoformat()
                    if grace_period_end_date
                    else None
                ),
            },
            'schedule': _serialize_payment_schedule(
                calculator.get_payment_schedule()
            ),
        },
    }
