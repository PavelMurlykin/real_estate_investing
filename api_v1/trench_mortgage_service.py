from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction
from django.urls import reverse

from mortgage.views import _build_saved_trench_calculation_data
from trench_mortgage.views import (
    _calculate_trench_mortgage,
    _parse_trench_inputs,
    _prepare_mortgage_data,
    _save_trench_calculation,
)

from .mortgage_service import serialize_saved_property


MONEY_QUANTUM = Decimal('0.01')
PERCENT_QUANTUM = Decimal('0.01')


class TrenchMortgageValidationError(Exception):
    """Carry established trench-calculation validation messages."""

    def __init__(self, messages):
        """Store immutable messages for translation at the API boundary."""
        self.messages = tuple(messages)
        super().__init__(' '.join(self.messages))


def _format_decimal(value, quantum=MONEY_QUANTUM):
    """Return a stable decimal string for the frontend contract."""
    decimal_value = Decimal(str(value)).quantize(
        quantum,
        rounding=ROUND_HALF_UP,
    )
    return format(decimal_value, 'f')


def _build_legacy_mortgage_data(parameters, property_object):
    """Map typed API parameters to the established trench domain input."""
    price_adjustment_value = parameters['priceAdjustmentValue']
    price_adjustment_percent = Decimal('0')
    price_adjustment_rubles = Decimal('0')
    if parameters['priceAdjustmentUnit'] == 'rubles':
        price_adjustment_rubles = price_adjustment_value
    else:
        price_adjustment_percent = price_adjustment_value

    initial_payment_value = parameters['initialPaymentValue']
    initial_payment_percent = Decimal('0')
    initial_payment_rubles = Decimal('0')
    if parameters['initialPaymentUnit'] == 'rubles':
        initial_payment_rubles = initial_payment_value
    else:
        initial_payment_percent = initial_payment_value

    return {
        'PROPERTY': property_object,
        'PROPERTY_COST': parameters['propertyCost'],
        'DISCOUNT_MARKUP_TYPE': parameters['priceAdjustmentType'],
        'DISCOUNT_MARKUP_VALUE': price_adjustment_percent,
        'DISCOUNT_MARKUP_RUBLES': price_adjustment_rubles,
        'DISCOUNT_MARKUP_SOURCE': parameters['priceAdjustmentUnit'],
        'INITIAL_PAYMENT_PERCENT': initial_payment_percent,
        'INITIAL_PAYMENT_RUBLES': initial_payment_rubles,
        'INITIAL_PAYMENT_SOURCE': parameters['initialPaymentUnit'],
        'INITIAL_PAYMENT_DATE': parameters['initialPaymentDate'],
        'MORTGAGE_TERM': parameters['mortgageTermMonths'],
        'ANNUAL_RATE': parameters['annualRate'],
        'TRENCH_COUNT': len(parameters['trenches']),
    }


def _build_legacy_trench_data(trenches):
    """Map nested tranche rows to the existing parser field names."""
    post_data = {}
    last_trench_index = len(trenches)
    for trench_index, trench in enumerate(trenches, start=1):
        post_data[f'trench_date_{trench_index}'] = (
            trench['date'].isoformat()
        )
        post_data[f'annual_rate_{trench_index}'] = str(
            trench['annualRate']
        )
        post_data[f'trench_amount_source_{trench_index}'] = trench[
            'amountUnit'
        ]
        post_data[f'trench_percent_{trench_index}'] = ''
        post_data[f'trench_amount_{trench_index}'] = ''
        if trench_index == last_trench_index:
            continue
        if trench['amountUnit'] == 'rubles':
            post_data[f'trench_amount_{trench_index}'] = str(
                trench['amountValue']
            )
        else:
            post_data[f'trench_percent_{trench_index}'] = str(
                trench['amountValue']
            )
    return post_data


def _serialize_payment_schedule(payment_schedule):
    """Serialize schedule rows with ISO dates and stable money values."""
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


def _serialize_trench_result(calculation):
    """Build the stable React response from the established calculation."""
    payment_schedule = _serialize_payment_schedule(
        calculation['payment_schedule']
    )
    maximum_monthly_payment = max(
        (
            Decimal(payment['paymentAmount'])
            for payment in payment_schedule
        ),
        default=Decimal('0'),
    )
    loan_amount = Decimal(str(calculation['total_loan_amount']))
    overpayment = Decimal(str(calculation['total_overpayment']))
    return {
        'assumptions': {
            'basePropertyCost': _format_decimal(
                calculation['base_property_cost']
            ),
            'priceAdjustmentType': calculation['discount_markup_type'],
            'priceAdjustmentPercent': _format_decimal(
                calculation['discount_markup_value'],
                PERCENT_QUANTUM,
            ),
            'priceAdjustmentRubles': _format_decimal(
                abs(
                    calculation['final_property_cost']
                    - calculation['base_property_cost']
                )
            ),
            'finalPropertyCost': _format_decimal(
                calculation['final_property_cost']
            ),
            'initialPaymentPercent': _format_decimal(
                calculation['initial_payment_percent'],
                PERCENT_QUANTUM,
            ),
            'initialPaymentRubles': _format_decimal(
                calculation['initial_payment']
            ),
            'initialPaymentDate': calculation[
                'initial_payment_date'
            ].isoformat(),
            'mortgageTermMonths': calculation['mortgage_term'],
            'annualRate': _format_decimal(
                calculation['annual_rate'],
                PERCENT_QUANTUM,
            ),
            'trenchCount': calculation['trench_count'],
        },
        'summary': {
            'loanAmount': _format_decimal(loan_amount),
            'maximumMonthlyPayment': _format_decimal(
                maximum_monthly_payment
            ),
            'overpayment': _format_decimal(overpayment),
            'totalPayments': _format_decimal(loan_amount + overpayment),
            'paymentsCount': len(payment_schedule),
            'mortgageEndDate': calculation['mortgage_end_date'].isoformat(),
        },
        'trenches': [
            {
                'number': trench['number'],
                'date': trench['date'].isoformat(),
                'percent': _format_decimal(
                    trench['percent'],
                    PERCENT_QUANTUM,
                ),
                'amount': _format_decimal(trench['amount']),
                'annualRate': _format_decimal(
                    trench['annual_rate'],
                    PERCENT_QUANTUM,
                ),
                'monthlyPayment': _format_decimal(
                    trench['monthly_payment']
                ),
                'paymentsCount': trench['payments_count'],
                'remainingDebt': _format_decimal(trench['remaining_debt']),
                'overpayment': _format_decimal(trench['overpayment']),
            }
            for trench in calculation['trenches']
        ],
        'schedule': payment_schedule,
    }


def calculate_trench_mortgage(parameters, property_object=None):
    """Calculate a trench mortgage through the established domain code."""
    mortgage_data, preparation_errors = _prepare_mortgage_data(
        _build_legacy_mortgage_data(parameters, property_object)
    )
    trench_entries, _, trench_errors = _parse_trench_inputs(
        post_data=_build_legacy_trench_data(parameters['trenches']),
        trench_count=len(parameters['trenches']),
        loan_amount=mortgage_data['total_loan_amount'],
        default_annual_rate=mortgage_data['annual_rate'],
    )
    validation_errors = preparation_errors + trench_errors
    if validation_errors:
        raise TrenchMortgageValidationError(validation_errors)

    calculation, calculation_errors = _calculate_trench_mortgage(
        mortgage_data,
        trench_entries,
    )
    if calculation_errors:
        raise TrenchMortgageValidationError(calculation_errors)
    return calculation, _serialize_trench_result(calculation)


@transaction.atomic
def create_saved_trench_mortgage(parameters, property_object, user):
    """Recalculate and atomically persist a property-backed scenario."""
    calculation, response_payload = calculate_trench_mortgage(
        parameters,
        property_object=property_object,
    )
    saved_calculation = _save_trench_calculation(calculation, user=user)
    return {
        'id': saved_calculation.pk,
        'legacyDetailUrl': reverse(
            'mortgage:trench_calculation_detail',
            kwargs={'pk': saved_calculation.pk},
        ),
        'calculation': response_payload,
    }


def serialize_saved_trench_mortgage_list_item(
    calculation,
    is_linked=False,
):
    """Serialize one owner-scoped history row without extra queries."""
    maximum_monthly_payment = max(
        (
            trench.monthly_payment
            for trench in calculation.trenches.all()
        ),
        default=None,
    )
    return {
        'id': calculation.pk,
        'createdAt': calculation.timestamp.isoformat(),
        'property': serialize_saved_property(calculation.property),
        'finalPropertyCost': _format_decimal(
            calculation.final_property_cost
        ),
        'initialPaymentRubles': _format_decimal(
            calculation.initial_payment_amount
        ),
        'maximumMonthlyPayment': (
            _format_decimal(maximum_monthly_payment)
            if maximum_monthly_payment is not None
            else None
        ),
        'mortgageTermMonths': calculation.mortgage_term,
        'annualRate': _format_decimal(
            calculation.annual_rate,
            PERCENT_QUANTUM,
        ),
        'trenchCount': calculation.trench_count,
        'isLinked': is_linked,
    }


def build_saved_trench_mortgage_data(calculation):
    """Rebuild the established report payload for detail and export."""
    return _build_saved_trench_calculation_data(calculation)


def serialize_saved_trench_mortgage_detail(calculation):
    """Serialize a saved tranche scenario with its bounded schedule."""
    calculation_data = build_saved_trench_mortgage_data(calculation)
    return {
        'id': calculation.pk,
        'createdAt': calculation.timestamp.isoformat(),
        'property': serialize_saved_property(calculation.property),
        'legacyDetailUrl': reverse(
            'mortgage:trench_calculation_detail',
            kwargs={'pk': calculation.pk},
        ),
        'calculation': _serialize_trench_result(calculation_data),
    }
