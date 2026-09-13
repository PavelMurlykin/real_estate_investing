from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from bank.key_rate_sync import KeyRateSyncError
from bank.models import KeyRate


@pytest.fixture
def key_rate_history(db):
    """Create chronological key rates including one inactive newest row."""
    oldest_rate = KeyRate.objects.create(
        meeting_date=date(2026, 1, 1),
        key_rate=Decimal('10.00'),
    )
    current_rate = KeyRate.objects.create(
        meeting_date=date(2026, 2, 1),
        key_rate=Decimal('12.00'),
    )
    inactive_rate = KeyRate.objects.create(
        meeting_date=date(2026, 3, 1),
        key_rate=Decimal('11.00'),
        is_active=False,
    )
    return {
        'oldest': oldest_rate,
        'current': current_rate,
        'inactive': inactive_rate,
    }


def create_administrator():
    """Create a user allowed to synchronize external source data."""
    return get_user_model().objects.create_superuser(
        email='key-rate-admin@example.com',
        password='safe-test-password',
        phone_number='+79990000231',
    )


@pytest.mark.django_db
def test_key_rate_list_is_public_paginated_and_query_efficient(
    client,
    key_rate_history,
    django_assert_num_queries,
):
    """Return rate deltas and current-rate metadata in four queries."""
    with django_assert_num_queries(4):
        response = client.get(
            reverse('api_v1:key_rate_list'),
            {'pageSize': 2},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload['page'] == 1
    assert payload['pageSize'] == 2
    assert payload['totalCount'] == 3
    assert payload['totalPages'] == 2
    assert payload['currentRate'] == {
        'meetingDate': '2026-02-01',
        'keyRate': '12.00',
    }
    assert payload['lastSyncedAt'] is not None
    assert payload['legacyUrl'] == '/bank/key-rate/'
    assert payload['results'][0] == {
        'id': key_rate_history['inactive'].pk,
        'meetingDate': '2026-03-01',
        'keyRate': '11.00',
        'rateChange': '-1.00',
        'isActive': False,
        'updatedAt': payload['results'][0]['updatedAt'],
    }
    assert payload['results'][1]['id'] == key_rate_history['current'].pk
    assert payload['results'][1]['rateChange'] == '2.00'


@pytest.mark.django_db
def test_key_rate_list_validates_page_size(client):
    """Reject an unbounded key-rate page request."""
    response = client.get(
        reverse('api_v1:key_rate_list'),
        {'pageSize': 101},
    )

    assert response.status_code == 400
    assert 'pageSize' in response.json()


@pytest.mark.django_db
def test_key_rate_sync_requires_administrator(client, key_rate_history):
    """Reject external synchronization from a regular authenticated user."""
    regular_user = get_user_model().objects.create_user(
        email='key-rate-user@example.com',
        password='safe-test-password',
        phone_number='+79990000232',
    )
    client.force_login(regular_user)

    with patch('api_v1.views.sync_key_rates') as sync_mock:
        response = client.post(reverse('api_v1:key_rate_sync'))

    assert response.status_code == 403
    sync_mock.assert_not_called()


@pytest.mark.django_db
def test_administrator_can_synchronize_key_rates(client, key_rate_history):
    """Return synchronization counts and the active current rate."""
    client.force_login(create_administrator())

    with patch(
        'api_v1.views.sync_key_rates',
        return_value={'created': 2, 'updated': 1, 'processed': 8},
    ) as sync_mock:
        response = client.post(reverse('api_v1:key_rate_sync'))

    assert response.status_code == 200
    assert response.json()['created'] == 2
    assert response.json()['updated'] == 1
    assert response.json()['processed'] == 8
    assert response.json()['currentRate']['keyRate'] == '12.00'
    assert response.json()['synchronizedAt']
    sync_mock.assert_called_once_with()


@pytest.mark.django_db
def test_key_rate_sync_returns_source_failure(client):
    """Represent a controlled source error without changing Django pages."""
    client.force_login(create_administrator())

    with patch(
        'api_v1.views.sync_key_rates',
        side_effect=KeyRateSyncError('Сервис недоступен'),
    ):
        response = client.post(reverse('api_v1:key_rate_sync'))

    assert response.status_code == 502
    assert response.json() == {
        'detail': (
            'Не удалось обновить данные ключевой ставки: Сервис недоступен'
        )
    }


@pytest.mark.django_db
def test_key_rate_sync_preserves_csrf_protection():
    """Reject an administrator POST without a CSRF token when checks apply."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(create_administrator())

    response = csrf_client.post(reverse('api_v1:key_rate_sync'))

    assert response.status_code == 403
