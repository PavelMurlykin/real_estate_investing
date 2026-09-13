from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from bank.developer_mortgage_program_importer import (
    DeveloperMortgageProgramImportError,
    DeveloperMortgageProgramImportResult,
)
from users.roles import MODERATOR_GROUP_NAME


def create_catalog_manager():
    """Create a moderator allowed to import shared catalog data."""
    user = get_user_model().objects.create_user(
        email='developer-program-import@example.com',
        password='safe-test-password',
        phone_number='+79990000241',
    )
    moderator_group, _ = Group.objects.get_or_create(
        name=MODERATOR_GROUP_NAME
    )
    user.groups.add(moderator_group)
    return user


def build_upload(filename='developer-programs.xlsx'):
    """Build a compact multipart upload accepted by the Django form."""
    return SimpleUploadedFile(
        filename,
        b'workbook-placeholder',
        content_type=(
            'application/vnd.openxmlformats-officedocument.'
            'spreadsheetml.sheet'
        ),
    )


@pytest.mark.django_db
def test_catalog_manager_can_import_developer_program_workbook(client):
    """Return the complete importer summary using stable API field names."""
    client.force_login(create_catalog_manager())
    import_result = DeveloperMortgageProgramImportResult(
        total_rows=12,
        parsed_rows=11,
        created=3,
        updated=2,
        unchanged=4,
        skipped=3,
        duplicate_rows=1,
        source_warning_rows=2,
        inactive_rows=1,
        issue_messages=('банк «Неизвестный» отсутствует в базе: 2 строки',),
    )

    with patch(
        'api_v1.views.import_developer_mortgage_programs',
        return_value=import_result,
    ) as importer_mock:
        response = client.post(
            reverse('api_v1:developer_mortgage_program_import'),
            {'workbook_file': build_upload()},
        )

    assert response.status_code == 200
    assert response.json() == {
        'totalRows': 12,
        'parsedRows': 11,
        'created': 3,
        'updated': 2,
        'unchanged': 4,
        'skipped': 3,
        'duplicateRows': 1,
        'sourceWarningRows': 2,
        'inactiveRows': 1,
        'issueMessages': (
            ['банк «Неизвестный» отсутствует в базе: 2 строки']
        ),
    }
    uploaded_workbook = importer_mock.call_args.args[0]
    assert uploaded_workbook.name == 'developer-programs.xlsx'


@pytest.mark.django_db
def test_developer_program_import_requires_catalog_permission(client):
    """Reject an upload from a user without catalog management rights."""
    regular_user = get_user_model().objects.create_user(
        email='developer-program-import-user@example.com',
        password='safe-test-password',
        phone_number='+79990000242',
    )
    client.force_login(regular_user)

    with patch(
        'api_v1.views.import_developer_mortgage_programs'
    ) as importer_mock:
        response = client.post(
            reverse('api_v1:developer_mortgage_program_import'),
            {'workbook_file': build_upload()},
        )

    assert response.status_code == 403
    importer_mock.assert_not_called()


@pytest.mark.django_db
def test_developer_program_import_validates_file_extension(client):
    """Reject a non-XLSX upload before calling the importer."""
    client.force_login(create_catalog_manager())

    with patch(
        'api_v1.views.import_developer_mortgage_programs'
    ) as importer_mock:
        response = client.post(
            reverse('api_v1:developer_mortgage_program_import'),
            {'workbook_file': build_upload('developer-programs.csv')},
        )

    assert response.status_code == 400
    assert response.json() == {
        'workbookFile': ['Поддерживаются только файлы XLSX.']
    }
    importer_mock.assert_not_called()


@pytest.mark.django_db
def test_developer_program_import_returns_controlled_workbook_error(client):
    """Return a readable validation error for an invalid workbook body."""
    client.force_login(create_catalog_manager())

    with patch(
        'api_v1.views.import_developer_mortgage_programs',
        side_effect=DeveloperMortgageProgramImportError(
            'В файле отсутствует лист «db_import».'
        ),
    ):
        response = client.post(
            reverse('api_v1:developer_mortgage_program_import'),
            {'workbook_file': build_upload()},
        )

    assert response.status_code == 400
    assert response.json() == {
        'detail': 'В файле отсутствует лист «db_import».'
    }


@pytest.mark.django_db
def test_developer_program_import_preserves_csrf_protection():
    """Reject a moderator upload without a CSRF token when checks apply."""
    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(create_catalog_manager())

    response = csrf_client.post(
        reverse('api_v1:developer_mortgage_program_import'),
        {'workbook_file': build_upload()},
    )

    assert response.status_code == 403
