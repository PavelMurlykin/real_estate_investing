import pytest

from .test_calculation_parity import BASE_PARAMETERS, build_legacy_parameters


@pytest.mark.django_db
@pytest.mark.parametrize('mode', ['market', 'trench'])
@pytest.mark.parametrize(
    ('initial_date', 'months', 'expected_status'),
    [
        ('9999-12-31', 360, 400),
        ('9999-12-01', 1, 400),
        ('9999-11-30', 1, 200),
    ],
)
def test_both_forms_validate_the_entire_mortgage_date_range(
    client, settings, mode, initial_date, months, expected_status,
):
    """Reject overflowing maturity dates and retain the last valid month."""
    settings.REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED = False
    parameters = BASE_PARAMETERS | {
        'initialPaymentDate': initial_date,
        'mortgageTermMonths': months,
    }
    if mode == 'trench':
        parameters['trenches'] = [{
            'date': initial_date, 'amountUnit': 'percent',
            'amountValue': None, 'annualRate': '15',
        }]
    prefix = '/api/v1/mortgage/' + ('trench/' if mode == 'trench' else '')
    response = client.post(
        prefix + 'calculate/', parameters, content_type='application/json',
    )
    assert response.status_code == expected_status
    legacy = client.post(
        '/mortgage/?legacy=1', build_legacy_parameters(parameters, mode),
    )
    assert legacy.status_code == 200
    if expected_status == 400:
        assert 'initialPaymentDate' in response.json()
        assert 'INITIAL_PAYMENT_DATE' in legacy.context['mortgage_form'].errors
        assert not legacy.context.get(mode + '_result')
    else:
        assert response.json()['summary']['mortgageEndDate'] == '9999-12-30'
        assert legacy.context[mode + '_result']


@pytest.mark.parametrize('tranche_date', [None, ''])
def test_missing_tranche_date_has_a_clear_field_error(client, tranche_date):
    """Keep missing dates attached to the affected tranche with useful copy."""
    tranche = {
        'amountUnit': 'percent', 'amountValue': None, 'annualRate': '15',
    }
    if tranche_date is not None:
        tranche['date'] = tranche_date
    response = client.post(
        '/api/v1/mortgage/trench/calculate/',
        BASE_PARAMETERS | {'trenches': [tranche]},
        content_type='application/json',
    )
    assert response.status_code == 400
    assert 'Укажите дату транша' in str(response.json()['trenches']['0']['date'])
