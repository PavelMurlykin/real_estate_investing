"""Verify isolation guards and synthetic acceptance fixture behavior."""

from types import SimpleNamespace

import pytest
from django.contrib.auth import get_user_model

from browser_acceptance import fixtures
from bank.models import MortgageProgram
from customer.models import Customer
from property.models import Property
from users.roles import can_manage_catalogs, can_view_all_private_records


@pytest.mark.parametrize(
    ('marker', 'database_name', 'vendor'),
    [
        ('', fixtures.DATABASE_NAME, 'postgresql'),
        ('1', 'real_estate_investing', 'postgresql'),
        ('1', fixtures.DATABASE_NAME, 'sqlite'),
    ],
)
def test_isolation_guard_rejects_unsafe_targets(
    monkeypatch, marker, database_name, vendor,
):
    """Reject every missing isolation condition before fixture writes."""
    monkeypatch.setenv('BROWSER_ACCEPTANCE_ISOLATED', marker)
    monkeypatch.setattr(
        fixtures, 'settings',
        SimpleNamespace(DATABASES={'default': {'NAME': database_name}}),
    )
    monkeypatch.setattr(fixtures, 'connection', SimpleNamespace(vendor=vendor))
    with pytest.raises(RuntimeError):
        fixtures.ensure_isolated_database()


def test_isolation_guard_accepts_dedicated_postgresql(monkeypatch):
    """Accept only the explicit test marker and dedicated PostgreSQL name."""
    monkeypatch.setenv('BROWSER_ACCEPTANCE_ISOLATED', '1')
    monkeypatch.setattr(
        fixtures, 'settings',
        SimpleNamespace(DATABASES={'default': {'NAME': fixtures.DATABASE_NAME}}),
    )
    monkeypatch.setattr(fixtures, 'connection', SimpleNamespace(vendor='postgresql'))
    fixtures.ensure_isolated_database()


def test_seed_rejects_short_password_before_database_writes(monkeypatch):
    """Require generated credentials rather than a committed test password."""
    monkeypatch.setattr(fixtures, 'ensure_isolated_database', lambda: None)
    monkeypatch.setenv('BROWSER_TEST_ACCOUNT_PASSWORD', 'short')
    with pytest.raises(RuntimeError, match='24\\+'):
        fixtures.seed_acceptance_fixtures()


@pytest.mark.django_db
def test_seed_is_idempotent_and_assigns_least_privilege(monkeypatch):
    """Keep fixture IDs stable and isolate private records from moderators."""
    # pytest already supplies its own database; never change connection settings.
    monkeypatch.setattr(fixtures, 'ensure_isolated_database', lambda: None)
    password = 'generated-acceptance-password-for-this-test'
    monkeypatch.setenv('BROWSER_TEST_ACCOUNT_PASSWORD', password)
    manifest = fixtures.seed_acceptance_fixtures()
    assert fixtures.seed_acceptance_fixtures() == manifest
    assert Property.objects.count() == 1
    assert Customer.objects.count() == 1
    assert MortgageProgram.objects.count() == 1
    assert MortgageProgram.objects.get(
        pk=manifest['mortgageProgramId'],
    ).name == 'E2E ипотечная программа'
    assert get_user_model().objects.count() == 3
    assert password not in str(manifest)
    for role, account in manifest['accounts'].items():
        user = get_user_model().objects.get(pk=account['id'])
        assert user.check_password(password)
        assert not user.is_staff
        assert not user.is_superuser
        assert can_manage_catalogs(user) == (role == 'moderator')
        assert not can_view_all_private_records(user)
    assert Customer.objects.get(pk=manifest['otherCustomerId']).user_id == (
        manifest['accounts']['other']['id']
    )
