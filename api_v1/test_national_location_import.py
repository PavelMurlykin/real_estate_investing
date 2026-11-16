"""Check national job permissions, CSRF and the browser progress contract."""

import pytest
from django.test import Client
from django.urls import reverse

from api_v1.test_location_import import import_user
from location.models import LocationImportJob


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
