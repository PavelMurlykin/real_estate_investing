from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from trench_mortgage.models import Trench, TrenchMortgageCalculation

from .test_saved_mortgage import calculation_user, saved_calculation_property


def build_trench_mortgage_payload(**overrides):
    """Return a valid two-tranche API payload with optional overrides."""
    payload = {
        'propertyCost': '5000000.00',
        'priceAdjustmentType': 'discount',
        'priceAdjustmentUnit': 'percent',
        'priceAdjustmentValue': '10.00',
        'initialPaymentUnit': 'percent',
        'initialPaymentValue': '20.00',
        'initialPaymentDate': '2026-01-15',
        'mortgageTermMonths': 24,
        'annualRate': '12.00',
        'trenches': [
            {
                'date': '2026-01-15',
                'amountUnit': 'percent',
                'amountValue': '40.00',
                'annualRate': '12.00',
            },
            {
                'date': '2026-07-15',
                'amountUnit': 'rubles',
                'amountValue': None,
                'annualRate': '10.00',
            },
        ],
    }
    payload.update(overrides)
    return payload


def build_saved_trench_mortgage_payload(property_object, **overrides):
    """Return a property-backed request for saving a trench scenario."""
    return {
        'propertyId': property_object.pk,
        'parameters': build_trench_mortgage_payload(**overrides),
    }


@pytest.mark.django_db
def test_trench_mortgage_api_returns_normalized_result_and_schedule(client):
    """Calculate tranche amounts, cumulative payments, and ISO schedule."""
    response = client.post(
        reverse('api_v1:trench_mortgage_calculate'),
        data=build_trench_mortgage_payload(),
        content_type='application/json',
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['assumptions']['finalPropertyCost'] == '4500000.00'
    assert payload['assumptions']['initialPaymentRubles'] == '900000.00'
    assert payload['assumptions']['trenchCount'] == 2
    assert payload['summary']['loanAmount'] == '3600000.00'
    assert payload['summary']['mortgageEndDate'] == '2028-01-15'
    assert payload['summary']['paymentsCount'] == 24
    assert payload['trenches'][0]['amount'] == '1440000.00'
    assert payload['trenches'][1]['amount'] == '2160000.00'
    assert payload['trenches'][1]['percent'] == '60.00'
    assert len(payload['schedule']) == 24
    assert payload['schedule'][0]['paymentDate'] == '2026-01-15'


@pytest.mark.django_db
def test_trench_mortgage_api_normalizes_ruble_locked_values(client):
    """Preserve ruble-locked deal values and derive tranche percentages."""
    trenches = build_trench_mortgage_payload()['trenches']
    trenches[0] = {
        'date': '2026-01-15',
        'amountUnit': 'rubles',
        'amountValue': '1000000.00',
        'annualRate': '12.00',
    }
    response = client.post(
        reverse('api_v1:trench_mortgage_calculate'),
        data=build_trench_mortgage_payload(
            priceAdjustmentType='markup',
            priceAdjustmentUnit='rubles',
            priceAdjustmentValue='500000.00',
            initialPaymentUnit='rubles',
            initialPaymentValue='1000000.00',
            trenches=trenches,
        ),
        content_type='application/json',
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['assumptions']['priceAdjustmentPercent'] == '10.00'
    assert payload['assumptions']['finalPropertyCost'] == '5500000.00'
    assert payload['assumptions']['initialPaymentPercent'] == '18.18'
    assert payload['trenches'][0]['percent'] == '22.22'
    assert payload['trenches'][1]['amount'] == '3500000.00'


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('trenches', 'expected_error_text'),
    [
        (
            [
                {
                    'date': '2026-01-15',
                    'amountUnit': 'percent',
                    'amountValue': None,
                    'annualRate': '12.00',
                },
                {
                    'date': '2026-07-15',
                    'amountUnit': 'percent',
                    'amountValue': None,
                    'annualRate': '12.00',
                },
            ],
            'amountValue',
        ),
        (
            [
                {
                    'date': '2026-07-15',
                    'amountUnit': 'percent',
                    'amountValue': '40.00',
                    'annualRate': '12.00',
                },
                {
                    'date': '2026-01-15',
                    'amountUnit': 'percent',
                    'amountValue': None,
                    'annualRate': '12.00',
                },
            ],
            'Даты траншей',
        ),
        (
            [
                {
                    'date': '2025-12-15',
                    'amountUnit': 'percent',
                    'amountValue': '40.00',
                    'annualRate': '12.00',
                },
                {
                    'date': '2026-07-15',
                    'amountUnit': 'percent',
                    'amountValue': None,
                    'annualRate': '12.00',
                },
            ],
            'раньше даты первоначального взноса',
        ),
        (
            [
                {
                    'date': '2026-01-15',
                    'amountUnit': 'percent',
                    'amountValue': '100.00',
                    'annualRate': '12.00',
                },
                {
                    'date': '2026-07-15',
                    'amountUnit': 'percent',
                    'amountValue': None,
                    'annualRate': '12.00',
                },
            ],
            'превышает или равна 100%',
        ),
    ],
)
def test_trench_mortgage_api_rejects_invalid_tranche_sequences(
    client,
    trenches,
    expected_error_text,
):
    """Return useful validation errors without partial persistence."""
    response = client.post(
        reverse('api_v1:trench_mortgage_calculate'),
        data=build_trench_mortgage_payload(trenches=trenches),
        content_type='application/json',
    )

    assert response.status_code == 400
    assert expected_error_text in str(response.json())
    assert not TrenchMortgageCalculation.objects.exists()


@pytest.mark.django_db
def test_saved_trench_mortgage_api_requires_authentication(
    client,
    saved_calculation_property,
):
    """Keep saved trench calculations private to authenticated users."""
    response = client.post(
        reverse('api_v1:saved_trench_mortgage_calculation_create'),
        data=build_saved_trench_mortgage_payload(
            saved_calculation_property
        ),
        content_type='application/json',
    )

    assert response.status_code == 403
    assert not TrenchMortgageCalculation.objects.exists()


@pytest.mark.django_db
def test_saved_trench_mortgage_api_persists_owner_and_trenches(
    client,
    calculation_user,
    saved_calculation_property,
):
    """Atomically save authoritative values and all tranche rows."""
    client.force_login(calculation_user)

    response = client.post(
        reverse('api_v1:saved_trench_mortgage_calculation_create'),
        data=build_saved_trench_mortgage_payload(
            saved_calculation_property
        ),
        content_type='application/json',
    )

    assert response.status_code == 201
    calculation = TrenchMortgageCalculation.objects.get()
    assert calculation.user == calculation_user
    assert calculation.property == saved_calculation_property
    assert calculation.final_property_cost == Decimal('4500000.00')
    assert calculation.total_loan_amount == Decimal('3600000.00')
    assert calculation.trenches.count() == 2
    assert list(
        calculation.trenches.values_list('trench_amount', flat=True)
    ) == [Decimal('1440000.00'), Decimal('2160000.00')]
    payload = response.json()
    assert payload['id'] == calculation.pk
    assert payload['legacyDetailUrl'].endswith(
        f'/mortgage/trench-calculations/{calculation.pk}/'
    )
    assert payload['calculation']['summary']['paymentsCount'] == 24


@pytest.mark.django_db
def test_saved_trench_mortgage_api_rejects_unknown_property(
    client,
    calculation_user,
):
    """Validate the property identifier before starting a database write."""
    client.force_login(calculation_user)

    response = client.post(
        reverse('api_v1:saved_trench_mortgage_calculation_create'),
        data={
            'propertyId': 999999,
            'parameters': build_trench_mortgage_payload(),
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'propertyId' in response.json()
    assert not TrenchMortgageCalculation.objects.exists()


@pytest.mark.django_db
def test_trench_mortgage_writes_require_csrf_when_checks_are_enabled(
    calculation_user,
    saved_calculation_property,
):
    """Require CSRF for public calculation and authenticated persistence."""
    csrf_client = Client(enforce_csrf_checks=True)
    calculate_response = csrf_client.post(
        reverse('api_v1:trench_mortgage_calculate'),
        data=build_trench_mortgage_payload(),
        content_type='application/json',
    )
    csrf_client.force_login(calculation_user)
    save_response = csrf_client.post(
        reverse('api_v1:saved_trench_mortgage_calculation_create'),
        data=build_saved_trench_mortgage_payload(
            saved_calculation_property
        ),
        content_type='application/json',
    )

    assert calculate_response.status_code == 403
    assert save_response.status_code == 403
    assert not Trench.objects.exists()


@pytest.mark.django_db
def test_saved_trench_history_supports_search_ordering_and_detail(
    client,
    calculation_user,
    saved_calculation_property,
):
    """Return stable owner history and a rebuilt detail schedule."""
    client.force_login(calculation_user)
    list_url = reverse('api_v1:saved_trench_mortgage_calculation_create')
    for annual_rate in ('12.00', '10.00'):
        response = client.post(
            list_url,
            data=build_saved_trench_mortgage_payload(
                saved_calculation_property,
                annualRate=annual_rate,
            ),
            content_type='application/json',
        )
        assert response.status_code == 201

    response = client.get(
        list_url,
        {'q': 'Зелёный', 'pageSize': 1, 'ordering': 'annualRate'},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload['totalCount'] == 2
    assert payload['totalPages'] == 2
    assert payload['results'][0]['annualRate'] == '10.00'
    assert payload['results'][0]['trenchCount'] == 2
    assert payload['results'][0]['maximumMonthlyPayment'] is not None

    calculation_identifier = payload['results'][0]['id']
    detail_response = client.get(
        reverse(
            'api_v1:saved_trench_mortgage_calculation_detail',
            kwargs={'pk': calculation_identifier},
        )
    )

    assert detail_response.status_code == 200
    detail_payload = detail_response.json()
    assert detail_payload['property']['realEstateComplex'] == (
        'Зелёный квартал'
    )
    assert detail_payload['calculation']['summary']['paymentsCount'] == 24
    assert len(detail_payload['calculation']['trenches']) == 2


@pytest.mark.django_db
def test_saved_trench_history_and_detail_are_scoped_to_owner(
    client,
    calculation_user,
    saved_calculation_property,
):
    """Hide guessed tranche calculation identifiers from other owners."""
    client.force_login(calculation_user)
    created_response = client.post(
        reverse('api_v1:saved_trench_mortgage_calculation_create'),
        data=build_saved_trench_mortgage_payload(
            saved_calculation_property
        ),
        content_type='application/json',
    )
    calculation_identifier = created_response.json()['id']
    other_user = get_user_model().objects.create_user(
        email='other-trench-owner@example.com',
        password='safe-test-password',
        phone_number='+79991110008',
    )
    client.force_login(other_user)

    list_response = client.get(
        reverse('api_v1:saved_trench_mortgage_calculation_create')
    )
    detail_response = client.get(
        reverse(
            'api_v1:saved_trench_mortgage_calculation_detail',
            kwargs={'pk': calculation_identifier},
        )
    )

    assert list_response.status_code == 200
    assert list_response.json()['results'] == []
    assert detail_response.status_code == 404


@pytest.mark.django_db
def test_saved_trench_history_uses_constant_query_count(
    client,
    calculation_user,
    saved_calculation_property,
    django_assert_num_queries,
):
    """Prefetch tranche rows instead of querying once per history item."""
    client.force_login(calculation_user)
    list_url = reverse('api_v1:saved_trench_mortgage_calculation_create')
    for annual_rate in ('10.00', '11.00', '12.00'):
        response = client.post(
            list_url,
            data=build_saved_trench_mortgage_payload(
                saved_calculation_property,
                annualRate=annual_rate,
            ),
            content_type='application/json',
        )
        assert response.status_code == 201

    with django_assert_num_queries(6):
        response = client.get(list_url)

    assert response.status_code == 200
    assert len(response.json()['results']) == 3


@pytest.mark.django_db
def test_saved_trench_owner_can_delete_with_csrf_protection(
    client,
    calculation_user,
    saved_calculation_property,
):
    """Delete owned scenarios while rejecting tokenless session writes."""
    client.force_login(calculation_user)
    created_response = client.post(
        reverse('api_v1:saved_trench_mortgage_calculation_create'),
        data=build_saved_trench_mortgage_payload(
            saved_calculation_property
        ),
        content_type='application/json',
    )
    calculation_identifier = created_response.json()['id']
    detail_url = reverse(
        'api_v1:saved_trench_mortgage_calculation_detail',
        kwargs={'pk': calculation_identifier},
    )
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(calculation_user)

    rejected_response = csrf_client.delete(detail_url)
    deleted_response = client.delete(detail_url)

    assert rejected_response.status_code == 403
    assert deleted_response.status_code == 204
    assert not TrenchMortgageCalculation.objects.filter(
        pk=calculation_identifier
    ).exists()


@pytest.mark.django_db
def test_saved_trench_exports_are_downloadable_and_owner_scoped(
    client,
    calculation_user,
    saved_calculation_property,
):
    """Reuse established exporters without exposing another user's data."""
    client.force_login(calculation_user)
    created_response = client.post(
        reverse('api_v1:saved_trench_mortgage_calculation_create'),
        data=build_saved_trench_mortgage_payload(
            saved_calculation_property
        ),
        content_type='application/json',
    )
    calculation_identifier = created_response.json()['id']

    excel_response = client.get(
        reverse(
            'api_v1:saved_trench_mortgage_calculation_export_excel',
            kwargs={'pk': calculation_identifier},
        )
    )
    word_response = client.get(
        reverse(
            'api_v1:saved_trench_mortgage_calculation_export_word',
            kwargs={'pk': calculation_identifier},
        )
    )

    assert excel_response.status_code == 200
    assert excel_response['Content-Type'] == (
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )
    assert excel_response.content.startswith(b'PK')
    assert word_response.status_code == 200
    assert word_response['Content-Type'] == (
        'application/vnd.openxmlformats-officedocument.'
        'wordprocessingml.document'
    )
    assert word_response.content.startswith(b'PK')

    other_user = get_user_model().objects.create_user(
        email='export-trench-owner@example.com',
        password='safe-test-password',
        phone_number='+79991110009',
    )
    client.force_login(other_user)
    hidden_response = client.get(
        reverse(
            'api_v1:saved_trench_mortgage_calculation_export_excel',
            kwargs={'pk': calculation_identifier},
        )
    )

    assert hidden_response.status_code == 404
