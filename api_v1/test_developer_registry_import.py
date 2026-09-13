from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client
from django.urls import reverse

from property.forms import DeveloperRegistryImportForm
from property.models import CompanyGroup, Developer
from property.services.developer_registry_importer import (
    DeveloperRegistryImportError,
)
from users.roles import (
    APPLICATION_ADMINISTRATOR_GROUP_NAME,
    MODERATOR_GROUP_NAME,
)


def create_user_in_group(email, phone_number, group_name):
    """Create an authenticated user in one application role group."""
    user = get_user_model().objects.create_user(
        email=email,
        password='safe-test-password',
        phone_number=phone_number,
    )
    group, _ = Group.objects.get_or_create(name=group_name)
    user.groups.add(group)
    return user


def build_registry_upload(filename='developers.csv'):
    """Build a compact developer registry source upload."""
    return SimpleUploadedFile(
        filename,
        (
            'Застройщик;Группа компаний;ИНН\n'
            'ООО React Реестр;ГК React;7711000000\n'
        ).encode('utf-8'),
        content_type='text/csv',
    )


@pytest.mark.django_db
def test_administrator_imports_developer_registry_file_through_api(client):
    """Import a source file and return the complete stable API summary."""
    administrator = create_user_in_group(
        'developer-registry-api-admin@example.com',
        '+79990000251',
        APPLICATION_ADMINISTRATOR_GROUP_NAME,
    )
    client.force_login(administrator)

    response = client.post(
        reverse('api_v1:developer_registry_import'),
        {'source_file': build_registry_upload()},
    )

    assert response.status_code == 200
    assert response.json() == {
        'sourceRecords': 1,
        'normalizedRecords': 1,
        'createdDevelopers': 1,
        'updatedDevelopers': 0,
        'unchangedDevelopers': 0,
        'createdCompanyGroups': 1,
        'createdDeveloperRegionLinks': 0,
        'skippedRecords': 0,
        'errors': [],
        'dryRun': False,
    }
    repeated_response = client.post(
        reverse('api_v1:developer_registry_import'),
        {'source_file': build_registry_upload()},
    )

    assert repeated_response.status_code == 200
    assert repeated_response.json() == {
        'sourceRecords': 1,
        'normalizedRecords': 1,
        'createdDevelopers': 0,
        'updatedDevelopers': 0,
        'unchangedDevelopers': 1,
        'createdCompanyGroups': 0,
        'createdDeveloperRegionLinks': 0,
        'skippedRecords': 0,
        'errors': [],
        'dryRun': False,
    }
    developer = Developer.objects.get(name='ООО React Реестр')
    assert developer.company_group.name == 'ГК React'
    assert developer.taxpayer_identification_number == '7711000000'
    assert CompanyGroup.objects.filter(name='ГК React').count() == 1


@pytest.mark.django_db
def test_developer_registry_import_requires_external_sync_permission(client):
    """Reject registry imports from catalog moderators."""
    moderator = create_user_in_group(
        'developer-registry-api-moderator@example.com',
        '+79990000252',
        MODERATOR_GROUP_NAME,
    )
    client.force_login(moderator)

    with patch(
        'api_v1.views.import_developer_registry_uploaded_file'
    ) as import_mock:
        response = client.post(
            reverse('api_v1:developer_registry_import'),
            {'source_file': build_registry_upload()},
        )

    assert response.status_code == 403
    import_mock.assert_not_called()


@pytest.mark.django_db
def test_developer_registry_import_rejects_unsupported_extension(client):
    """Reject an unsupported source before starting the importer."""
    administrator = create_user_in_group(
        'developer-registry-api-extension@example.com',
        '+79990000253',
        APPLICATION_ADMINISTRATOR_GROUP_NAME,
    )
    client.force_login(administrator)

    with patch(
        'api_v1.views.import_developer_registry_uploaded_file'
    ) as import_mock:
        response = client.post(
            reverse('api_v1:developer_registry_import'),
            {'source_file': build_registry_upload('developers.txt')},
        )

    assert response.status_code == 400
    assert response.json() == {
        'sourceFile': [
            'Файл импорта должен быть в формате .csv, .json, .xlsx.'
        ]
    }
    import_mock.assert_not_called()


def test_developer_registry_import_form_rejects_oversized_upload():
    """Reject a registry source larger than the server-side limit."""
    source_file = build_registry_upload()
    source_file.size = 20 * 1024 * 1024 + 1

    import_form = DeveloperRegistryImportForm(
        files={'source_file': source_file}
    )

    assert not import_form.is_valid()
    assert import_form.errors['source_file'] == [
        'Файл импорта не должен превышать 20 МБ.'
    ]


@pytest.mark.django_db
def test_developer_registry_import_returns_controlled_source_error(client):
    """Return a readable parser failure without leaking internals."""
    administrator = create_user_in_group(
        'developer-registry-api-error@example.com',
        '+79990000255',
        APPLICATION_ADMINISTRATOR_GROUP_NAME,
    )
    client.force_login(administrator)

    with patch(
        'api_v1.views.import_developer_registry_uploaded_file',
        side_effect=DeveloperRegistryImportError(
            'Файл реестра содержит некорректные данные.'
        ),
    ):
        response = client.post(
            reverse('api_v1:developer_registry_import'),
            {'source_file': build_registry_upload()},
        )

    assert response.status_code == 400
    assert response.json() == {
        'detail': 'Файл реестра содержит некорректные данные.'
    }


@pytest.mark.django_db
def test_developer_registry_import_preserves_csrf_protection():
    """Reject an administrator upload without a CSRF token."""
    csrf_client = Client(enforce_csrf_checks=True)
    administrator = create_user_in_group(
        'developer-registry-api-csrf@example.com',
        '+79990000256',
        APPLICATION_ADMINISTRATOR_GROUP_NAME,
    )
    csrf_client.force_login(administrator)

    response = csrf_client.post(
        reverse('api_v1:developer_registry_import'),
        {'source_file': build_registry_upload()},
    )

    assert response.status_code == 403
