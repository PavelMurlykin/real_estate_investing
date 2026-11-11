"""Compare legacy form output and React API schedules through both HTTP views."""

from decimal import Decimal

import pytest


BASE_PARAMETERS = {
    'propertyCost': '5000000.00',
    'priceAdjustmentType': 'discount',
    'priceAdjustmentUnit': 'percent',
    'priceAdjustmentValue': '0',
    'initialPaymentUnit': 'percent',
    'initialPaymentValue': '20',
    'initialPaymentDate': '2026-10-01',
    'mortgageTermMonths': 360,
    'annualRate': '15.00',
    'hasGracePeriod': False,
}

MARKET_CASES = [
    pytest.param({}, id='standard'),
    pytest.param({'priceAdjustmentValue': '3.37'}, id='discount-percent'),
    pytest.param({
        'priceAdjustmentType': 'markup', 'priceAdjustmentUnit': 'rubles',
        'priceAdjustmentValue': '123456.78',
    }, id='markup-rubles'),
    pytest.param({
        'initialPaymentUnit': 'rubles', 'initialPaymentValue': '1234567.89',
    }, id='down-payment-rubles'),
    pytest.param({
        'hasGracePeriod': True, 'gracePeriodTermMonths': 12,
        'gracePeriodRate': '6.00',
    }, id='grace'),
    pytest.param({
        'mortgageTermMonths': 13, 'initialPaymentDate': '2028-01-31',
    }, id='leap-year-end-of-month'),
    pytest.param({'initialPaymentValue': '0'}, id='zero-down-payment'),
    pytest.param({'initialPaymentValue': '100'}, id='full-down-payment'),
    pytest.param({'mortgageTermMonths': 600}, id='maximum-term'),
    pytest.param({'annualRate': '0'}, id='zero-interest'),
    pytest.param({
        'annualRate': '100', 'mortgageTermMonths': 600,
    }, id='maximum-rate-and-term'),
    pytest.param({
        'propertyCost': '9999999999999.99', 'annualRate': '0.01',
    }, id='maximum-price-and-low-rate'),
    pytest.param({
        'propertyCost': '9999999999999.99', 'annualRate': '100',
        'mortgageTermMonths': 600,
    }, id='maximum-price-rate-and-term'),
    pytest.param({
        'hasGracePeriod': True, 'gracePeriodTermMonths': 12,
        'gracePeriodRate': '0',
    }, id='zero-grace-interest'),
]

TRENCH_CASES = [
    pytest.param([
        {'date': '2026-10-01', 'amountUnit': 'percent',
         'amountValue': None, 'annualRate': '15'},
    ], id='single'),
    pytest.param([
        {'date': '2026-10-01', 'amountUnit': 'percent',
         'amountValue': '30', 'annualRate': '1'},
        {'date': '2027-10-01', 'amountUnit': 'percent',
         'amountValue': None, 'annualRate': '15'},
    ], id='two'),
    pytest.param([
        {'date': '2026-10-01', 'amountUnit': 'rubles',
         'amountValue': '123456.78', 'annualRate': '1'},
        {'date': '2027-04-01', 'amountUnit': 'rubles',
         'amountValue': None, 'annualRate': '15'},
    ], id='rubles'),
    pytest.param([
        {'date': f'{2026 + index}-10-01', 'amountUnit': 'percent',
         'amountValue': '15' if index < 4 else None,
         'annualRate': str(index + 1)}
        for index in range(5)
    ], id='five'),
    pytest.param([
        {'date': '2026-10-01', 'amountUnit': 'percent',
         'amountValue': '90', 'annualRate': '30'},
        {'date': '2027-10-01', 'amountUnit': 'percent',
         'amountValue': None, 'annualRate': '1'},
    ], id='decreasing-rate'),
    pytest.param([
        {'date': '2026-10-01', 'amountUnit': 'percent',
         'amountValue': '30', 'annualRate': '0'},
        {'date': '2027-10-01', 'amountUnit': 'percent',
         'amountValue': None, 'annualRate': '0'},
    ], id='zero-interest'),
]


def build_legacy_parameters(parameters, calculation_type):
    """Translate one input scenario to the existing Django form field names."""
    result = {
        'CALCULATION_TYPE': calculation_type,
        'calculate': calculation_type,
        'PROPERTY_COST': parameters['propertyCost'],
        'DISCOUNT_MARKUP_TYPE': parameters['priceAdjustmentType'],
        'DISCOUNT_MARKUP_SOURCE': parameters['priceAdjustmentUnit'],
        'DISCOUNT_MARKUP_VALUE': '0',
        'DISCOUNT_MARKUP_RUBLES': '0',
        'INITIAL_PAYMENT_SOURCE': parameters['initialPaymentUnit'],
        'INITIAL_PAYMENT_PERCENT': '0',
        'INITIAL_PAYMENT_RUBLES': '0',
        'INITIAL_PAYMENT_DATE': parameters['initialPaymentDate'],
        'MORTGAGE_TERM': parameters['mortgageTermMonths'],
        'ANNUAL_RATE': parameters['annualRate'],
        'HAS_GRACE_PERIOD': 'yes' if parameters['hasGracePeriod'] else 'no',
        'GRACE_PERIOD_TERM': parameters.get('gracePeriodTermMonths', ''),
        'GRACE_PERIOD_RATE': parameters.get('gracePeriodRate', ''),
        'TRENCH_COUNT': len(parameters.get('trenches', [None, None])),
    }
    adjustment_field = (
        'DISCOUNT_MARKUP_RUBLES'
        if parameters['priceAdjustmentUnit'] == 'rubles'
        else 'DISCOUNT_MARKUP_VALUE'
    )
    result[adjustment_field] = parameters['priceAdjustmentValue']
    payment_field = (
        'INITIAL_PAYMENT_RUBLES'
        if parameters['initialPaymentUnit'] == 'rubles'
        else 'INITIAL_PAYMENT_PERCENT'
    )
    result[payment_field] = parameters['initialPaymentValue']
    for number, trench in enumerate(parameters.get('trenches', []), start=1):
        result[f'trench_date_{number}'] = trench['date']
        result[f'annual_rate_{number}'] = trench['annualRate']
        result[f'trench_amount_source_{number}'] = trench['amountUnit']
        amount_field = (
            'trench_amount' if trench['amountUnit'] == 'rubles'
            else 'trench_percent'
        )
        result[f'{amount_field}_{number}'] = trench['amountValue'] or ''
    return result


def normalized_money(value):
    """Remove legacy presentation separators and preserve kopeck precision."""
    return Decimal(str(value).replace(' ', '').replace(',', '.'))


def assert_http_calculation_parity(client, parameters, calculation_type):
    """Compare summaries and every number/date/amount/balance in both schedules."""
    legacy = client.post(
        '/mortgage/', build_legacy_parameters(parameters, calculation_type),
    )
    api_prefix = '/api/v1/mortgage/'
    if calculation_type == 'trench':
        api_prefix += 'trench/'
    response = client.post(
        api_prefix + 'calculate/', parameters, content_type='application/json',
    )
    assert legacy.status_code == 200
    assert response.status_code == 200, response.content
    context = legacy.context
    assert not context['mortgage_form'].errors
    legacy_result = context[f'{calculation_type}_result']
    assert legacy_result, context.get('error_message')
    payload = response.json()
    schedule = context[f'{calculation_type}_payment_schedule']
    assert len(schedule) == len(payload['schedule'])
    for old, new in zip(schedule, payload['schedule'], strict=True):
        assert old['payment_number'] == new['paymentNumber']
        payment_date = old['payment_date']
        if hasattr(payment_date, 'isoformat'):
            payment_date = payment_date.isoformat()
        elif '.' in payment_date:
            payment_date = '-'.join(reversed(payment_date.split('.')))
        assert payment_date == new['paymentDate']
        for legacy_field, api_field in (
            ('payment_amount', 'paymentAmount'),
            ('interest_amount', 'interestAmount'),
            ('principal_amount', 'principalAmount'),
            ('remaining_debt', 'remainingDebt'),
        ):
            assert normalized_money(old[legacy_field]) == Decimal(new[api_field])
    summary_fields = [
        ('total_loan_amount', 'loanAmount'),
        ('total_overpayment', 'overpayment'),
    ]
    if calculation_type == 'market':
        summary_fields.append(('main_monthly_payment', 'mainMonthlyPayment'))
    for legacy_field, api_field in summary_fields:
        assert normalized_money(legacy_result[legacy_field]) == Decimal(
            payload['summary'][api_field]
        )
    return len(schedule)


@pytest.mark.django_db
@pytest.mark.parametrize('overrides', MARKET_CASES)
def test_market_form_and_api_parity(client, settings, overrides, record_property):
    """Preserve legacy market values, grace periods, cents and boundary dates."""
    settings.REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED = False
    rows = assert_http_calculation_parity(
        client, BASE_PARAMETERS | overrides, 'market',
    )
    record_property('schedule_rows', rows)


@pytest.mark.django_db
@pytest.mark.parametrize('trenches', TRENCH_CASES)
def test_trench_form_and_api_parity(client, settings, trenches, record_property):
    """Preserve one-to-five tranche schedules and zero/decreasing rate cases."""
    settings.REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED = False
    rows = assert_http_calculation_parity(
        client, BASE_PARAMETERS | {'trenches': trenches}, 'trench',
    )
    record_property('schedule_rows', rows)
