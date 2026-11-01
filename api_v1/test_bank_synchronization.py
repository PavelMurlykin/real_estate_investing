from unittest.mock import patch

import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from bank.mortgage_offer_sync import BankMortgageSyncError
from users.roles import MODERATOR_GROUP_NAME

from .test_key_rates import create_administrator
from .test_saved_mortgage import calculation_user


@pytest.mark.django_db
@pytest.mark.parametrize('update_registry', [True, False])
def test_administrator_can_run_each_existing_bank_sync(client, update_registry):
    """Preserve the two service modes, counters and provider warnings."""
    client.force_login(create_administrator())
    with patch('api_v1.views.sync_bank_mortgage_offers', return_value={
        'created': 2, 'updated': 3, 'processed': 5,
        'reference_programs_processed': 12,
        'warnings': ['Один источник временно недоступен'],
    }) as synchronize:
        response = client.post(reverse('api_v1:bank_synchronization'), {
            'updateBankRegistry': update_registry,
        }, content_type='application/json')
    assert response.status_code == 200
    synchronize.assert_called_once_with(update_bank_registry=update_registry)
    result = response.json()
    assert result['updateBankRegistry'] is update_registry
    assert result['processed'] == 5
    assert result['referenceProgramsProcessed'] == 12
    assert result['warnings'] == ['Один источник временно недоступен']
    assert result['synchronizedAt']


@pytest.mark.django_db
@pytest.mark.parametrize('role', ['anonymous', 'owner', 'moderator'])
def test_bank_sync_never_calls_providers_without_admin_permission(
    client, calculation_user, role,
):
    """Keep both external writes restricted to the established admin role."""
    if role != 'anonymous':
        client.force_login(calculation_user)
    if role == 'moderator':
        calculation_user.groups.add(Group.objects.get(name=MODERATOR_GROUP_NAME))
    with patch('api_v1.views.sync_bank_mortgage_offers') as synchronize:
        response = client.post(reverse('api_v1:bank_synchronization'), {
            'updateBankRegistry': False,
        }, content_type='application/json')
    assert response.status_code == 403
    synchronize.assert_not_called()


@pytest.mark.django_db
def test_bank_sync_validates_modes_and_reports_provider_failure(client):
    """Expose a recoverable failure and reject malformed flags before sync."""
    client.force_login(create_administrator())
    url = reverse('api_v1:bank_synchronization')
    with patch('api_v1.views.sync_bank_mortgage_offers') as synchronize:
        response = client.post(url, {'updateBankRegistry': 'invalid'},
                               content_type='application/json')
    assert response.status_code == 400
    synchronize.assert_not_called()
    with patch('api_v1.views.sync_bank_mortgage_offers',
               side_effect=BankMortgageSyncError('Сервис недоступен')):
        response = client.post(url, {}, content_type='application/json')
    assert response.status_code == 502
    assert 'Сервис недоступен' in response.json()['detail']


@pytest.mark.django_db
def test_bank_sync_requires_csrf():
    """Do not let a privileged session trigger synchronization without CSRF."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(create_administrator())
    with patch('api_v1.views.sync_bank_mortgage_offers') as synchronize:
        response = client.post(reverse('api_v1:bank_synchronization'), {})
    assert response.status_code == 403
    synchronize.assert_not_called()
