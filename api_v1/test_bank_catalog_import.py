import json
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from bank.catalog_import import MAX_CATALOG_BYTES
from bank.models import Bank, BankProgram, MortgageProgram
from users.roles import APPLICATION_ADMINISTRATOR_GROUP_NAME, MODERATOR_GROUP_NAME


@pytest.fixture
def catalog():
    """Provide a single file for both parts of the bank catalog."""
    return {
        'version': 1,
        'banks': [{'name': 'Тестовый банк', 'logo_url': 'https://example.com/logo.svg'}],
        'programs': [{
            'name': 'Семейная ипотека',
            'condition': 'Для семей с детьми',
            'is_preferential': True,
        }],
        'offers': [{
            'bank': 'Тестовый банк',
            'program': 'Семейная ипотека',
            'interest_rate': '6.00',
            'minimum_initial_payment_percent': '20.10',
            'maximum_loan_term_years': 30,
        }],
    }


def upload_catalog(client, route, catalog):
    """Submit a UTF-8 catalog through the multipart API."""
    content = json.dumps(catalog, ensure_ascii=False).encode('utf-8')
    upload = SimpleUploadedFile('catalog.json', content, 'application/json')
    return client.post(reverse(f'api_v1:{route}'), {'file': upload})


def login_with_role(client, role):
    """Authenticate the test user with the specified application role."""
    user = get_user_model().objects.create_user(
        email='bank-import@example.com',
        password='safe-test-password',
        phone_number='+79990000201',
    )
    group, _ = Group.objects.get_or_create(name=role)
    user.groups.add(group)
    client.force_login(user)


@pytest.fixture
def administrator(client):
    """Authenticate an application administrator for import tests."""
    login_with_role(client, APPLICATION_ADMINISTRATOR_GROUP_NAME)
    return client


@pytest.mark.django_db
@pytest.mark.parametrize('route', ['bank_import', 'mortgage_program_import'])
def test_only_administrators_can_import(client, catalog, route):
    """Deny anonymous users and catalog moderators access to both uploads."""
    assert upload_catalog(client, route, catalog).status_code == 403
    login_with_role(client, MODERATOR_GROUP_NAME)
    assert upload_catalog(client, route, catalog).status_code == 403
    assert not Bank.objects.exists()


@pytest.mark.django_db
def test_import_catalog_tabs_and_rerun(administrator, catalog):
    """Import sections independently and update only submitted terms."""
    first_response = upload_catalog(administrator, 'bank_import', catalog)
    assert first_response.json() == {'created': 1, 'updated': 0, 'unchanged': 0}
    assert not MortgageProgram.objects.exists()

    bank = Bank.objects.get(name='Тестовый банк')
    other_bank = Bank.objects.create(name='Вручную добавленный банк')
    other_program = MortgageProgram.objects.create(name='Другая программа')
    manual_offer = BankProgram.objects.create(bank=other_bank, mortgage_program=other_program)
    mortgage_program = MortgageProgram.objects.create(
        name='Семейная ипотека', credit_limit=Decimal('6000000'),
    )
    catalog['offers'][0]['program'] = '  семейная  ипотека '
    response = upload_catalog(administrator, 'mortgage_program_import', catalog)
    assert response.json() == {'created': 1, 'updated': 1, 'unchanged': 0}

    offer = BankProgram.objects.get(bank=bank)
    assert offer.interest_rate == Decimal('6')
    assert offer.mortgage_program_id == mortgage_program.pk
    offer.mortgage_program.refresh_from_db()
    assert offer.mortgage_program.credit_limit == Decimal('6000000')

    repeat_response = upload_catalog(administrator, 'mortgage_program_import', catalog)
    assert repeat_response.json() == {'created': 0, 'updated': 0, 'unchanged': 2}
    catalog['offers'][0]['interest_rate'] = '7.10'
    update_response = upload_catalog(administrator, 'mortgage_program_import', catalog)
    assert update_response.json() == {'created': 0, 'updated': 1, 'unchanged': 1}
    offer.refresh_from_db()
    assert offer.interest_rate == Decimal('7.10')
    assert BankProgram.objects.filter(pk=manual_offer.pk).exists()
    assert BankProgram.objects.count() == 2


@pytest.mark.django_db
@pytest.mark.parametrize('defect', ['unknown_bank', 'unknown_program', 'duplicate', 'invalid_rate'])
def test_invalid_catalog_does_not_apply_rows(administrator, catalog, defect):
    """Reject malformed, duplicate and unresolved offers before saving."""
    bank = Bank.objects.create(name='Тестовый банк')
    if defect == 'unknown_bank':
        catalog['offers'][0]['bank'] = 'Другой банк'
    elif defect == 'unknown_program':
        catalog['offers'][0]['program'] = 'Другая программа'
    elif defect == 'duplicate':
        catalog['offers'].append({**catalog['offers'][0], 'bank': ' тестовый  банк '})
    else:
        catalog['offers'][0]['interest_rate'] = '101.00'

    response = upload_catalog(administrator, 'mortgage_program_import', catalog)
    assert response.status_code == 400
    assert response.json()['detail']
    assert not MortgageProgram.objects.exists()
    assert not BankProgram.objects.filter(bank=bank).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(('filename', 'content'), [
    ('catalog.txt', b'{}'),
    ('catalog.json', b'\xff'),
    ('catalog.json', b'{"version": 1, "version": 1}'),
    ('catalog.json', b' ' * (MAX_CATALOG_BYTES + 1)),
], ids=['extension', 'encoding', 'repeated-key', 'size'])
def test_catalog_file_validation(administrator, filename, content):
    """Require a bounded JSON file with valid UTF-8 and unique properties."""
    response = administrator.post(
        reverse('api_v1:bank_import'),
        {'file': SimpleUploadedFile(filename, content)},
    )
    assert response.status_code == 400
    assert not Bank.objects.exists()


@pytest.mark.django_db
def test_prepared_catalog_imports_and_can_be_reused(administrator):
    """Load the delivered snapshot twice through both tab endpoints."""
    path = Path(__file__).resolve().parents[1] / 'data/bank-catalog-ru-2026-11.json'
    catalog = json.loads(path.read_text(encoding='utf-8'))
    for route, size in [
        ('bank_import', 30),
        ('mortgage_program_import', len(catalog['programs']) + len(catalog['offers'])),
    ]:
        response = upload_catalog(administrator, route, catalog)
        assert response.status_code == 200, response.json()
        assert response.json() == {'created': size, 'updated': 0, 'unchanged': 0}
        response = upload_catalog(administrator, route, catalog)
        assert response.json() == {'created': 0, 'updated': 0, 'unchanged': size}
    assert Bank.objects.exclude(logo_url='').count() == 30
    assert BankProgram.objects.count() == len(catalog['offers'])


@pytest.mark.django_db
def test_legacy_program_tab_imports_catalog(administrator, catalog):
    """Keep the Django upload on the selected tab with its success message."""
    catalog_url = reverse('bank:catalog')
    bank_tab = administrator.get(f'{catalog_url}?model=bank&legacy=1')
    programs_tab = administrator.get(f'{catalog_url}?model=mortgage_program&legacy=1')
    assert 'Импорт банков' in bank_tab.content.decode()
    assert 'Импорт ипотечных программ' in programs_tab.content.decode()

    Bank.objects.create(name='Тестовый банк')
    response = administrator.post(catalog_url, {
        'action': 'import_catalog',
        'model': 'mortgage_program',
        'file': SimpleUploadedFile('catalog.json', json.dumps(catalog).encode()),
    }, follow=True)
    assert response.status_code == 200
    assert 'Импорт завершён.' in response.content.decode()
    assert BankProgram.objects.count() == 1
