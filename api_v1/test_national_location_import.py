"""Check national job permissions, CSRF and the browser progress contract."""

from unittest.mock import patch

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from api_v1.test_location_import import import_user
from location.jobs import run_import_job
from location.models import LocationImportJob
from location.tests.test_gar import SPB


@pytest.mark.django_db
@pytest.mark.parametrize('role', [
    'anonymous', 'regular', 'staff', 'moderator', 'administrator', 'superuser',
])
def test_national_import_access(client, import_user, role):
    """Require external synchronization rights for both state and writes."""
    user = import_user(role)
    if user:
        client.force_login(user)
    url = reverse('api_v1:location_import_job')
    allowed = role in ('administrator', 'superuser')
    assert client.get(url).status_code == (200 if allowed else 403)
    assert client.post(url, {}, content_type='application/json').status_code == (
        202 if allowed else 403
    )
    assert LocationImportJob.objects.count() == int(allowed)


@pytest.mark.django_db
def test_national_job_survives_reload_and_is_not_duplicated(import_user):
    """Use a real session and CSRF and recover the same state after GET."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(import_user('administrator'))
    url = reverse('api_v1:location_import_job')
    assert client.post(url, {}, content_type='application/json').status_code == 403
    client.get('/api/v1/auth/session/')
    token = client.cookies['csrftoken'].value
    first = client.post(url, {}, content_type='application/json', HTTP_X_CSRFTOKEN=token)
    second = client.post(url, {}, content_type='application/json', HTTP_X_CSRFTOKEN=token)
    assert first.status_code == second.status_code == 202
    assert first.json()['job']['id'] == second.json()['job']['id']
    assert client.get(url).json()['job']['status'] == 'queued'
    assert client.post(url, {'sourceUrl': 'http://example.com'},
                       content_type='application/json', HTTP_X_CSRFTOKEN=token).status_code == 400


@pytest.mark.django_db
@pytest.mark.parametrize('role', ['moderator', 'administrator'])
def test_fallback_national_import_uses_the_same_access_rule(client, import_user, role):
    """Queue the same job from Django pages without granting moderators access."""
    client.force_login(import_user(role))
    response = client.post(reverse('location:location_import'), {'action': 'national'})
    assert response.status_code == (302 if role == 'administrator' else 403)
    assert LocationImportJob.objects.count() == int(role == 'administrator')


@pytest.mark.django_db
def test_national_import_finishes_without_templates_or_old_tables(client, import_user):
    """Use both entrypoints with rendering disabled and compare successive GAR imports."""
    client.force_login(import_user('administrator'))
    with (
        patch('django.template.Template.render', side_effect=AssertionError('Template rendered')),
        patch('location.jobs.latest_snapshot', return_value=('20261113', 'https://fias-file.nalog.ru/test.zip')),
        patch('location.jobs.GarSource') as factory,
        CaptureQueriesContext(connection) as queries,
    ):
        source = factory.return_value
        source.regions.return_value = ['78']
        source.extract_region.return_value = SPB
        assert client.post(reverse('location:location_import'), {'action': 'national'}).status_code == 302
        first_job = LocationImportJob.objects.get()
        run_import_job(first_job)
        assert first_job.status == 'completed' and first_job.counts['cities']['created'] == 2
        url = reverse('api_v1:location_import_job')
        assert client.post(url, {}, content_type='application/json').status_code == 202
        second_job = LocationImportJob.objects.exclude(pk=first_job.pk).get()
        run_import_job(second_job)
        assert second_job.status == 'completed'
        assert all(not counts['created'] and not counts['updated'] for counts in second_job.counts.values())
        assert client.get(url).json()['job']['status'] == 'completed'
    legacy_queries = [
        query['sql'] for query in queries
        if any(f'{verb} "{table}"' in query['sql'] for verb in ('FROM', 'JOIN', 'UPDATE', 'INTO')
               for table in ('region', 'city', 'district'))
    ]
    assert not legacy_queries
