"""Verify administrator-only location import and its shared Django fallback."""

from functools import partial
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse

from location.import_service import LocationImportError
from location.models import City, District, Metro, MetroLine, Region
from location.tests.source_fixtures import load_sources, source_reply
from users.roles import (
    APPLICATION_ADMINISTRATOR_GROUP_NAME,
    MODERATOR_GROUP_NAME,
)


@pytest.fixture
def import_user():
    """Build users using actual role groups rather than mocked permissions."""
    def create_user(role):
        """Create one isolated account for a requested access level."""
        if role == 'anonymous':
            return None
        user = get_user_model().objects.create_user(
            email=f'{role}@location-test.invalid', password='test-only-password',
            phone_number='+79990009101', is_staff=role == 'staff',
            is_superuser=role == 'superuser',
        )
        group_name = {
            'moderator': MODERATOR_GROUP_NAME,
            'administrator': APPLICATION_ADMINISTRATOR_GROUP_NAME,
        }.get(role)
        if group_name:
            group, _ = Group.objects.get_or_create(name=group_name)
            user.groups.add(group)
        return user
    return create_user


@pytest.mark.django_db
@pytest.mark.parametrize('role', [
    'anonymous', 'regular', 'staff', 'moderator', 'administrator', 'superuser',
])
@pytest.mark.parametrize('legacy', [False, True])
def test_import_access_matrix(client, import_user, role, legacy):
    """Protect both entrypoints before any external extraction is attempted."""
    user = import_user(role)
    if user:
        client.force_login(user)
    url = reverse('location:location_import') if legacy else reverse(
        'api_v1:location_dictionary_import', kwargs={'dictionary_key': 'regions'},
    )
    import_target = (
        'location.views.import_locations' if legacy
        else 'api_v1.views.import_locations'
    )
    with patch(import_target) as importer:
        importer.return_value = {
            'created': 0, 'updated': 0, 'unchanged': 0, 'skipped': 0,
        }
        if legacy:
            response = client.post(url, {'dictionary': 'regions'})
        else:
            response = client.post(url, {}, content_type='application/json')
    allowed = role in ('administrator', 'superuser')
    expected_status = (302 if legacy else 200) if allowed else 403
    assert response.status_code == expected_status
    assert importer.call_count == int(allowed)


@pytest.mark.django_db
@pytest.mark.parametrize('legacy', [False, True])
def test_import_requires_csrf_for_authorized_sessions(import_user, legacy):
    """An authenticated administrator still needs a valid CSRF token."""
    client = Client(enforce_csrf_checks=True)
    client.force_login(import_user('administrator'))
    url = reverse('location:location_import') if legacy else reverse(
        'api_v1:location_dictionary_import', kwargs={'dictionary_key': 'regions'},
    )
    with patch('api_v1.views.import_locations') as importer:
        response = client.post(url, {}, content_type='application/json')
    assert response.status_code == 403
    importer.assert_not_called()


@pytest.mark.django_db
@pytest.mark.parametrize('dictionary,parents', [
    ('cities', {}), ('districts', {}), ('metro', {}),
    ('regions', {'regionId': 1}), ('regions', {'sourceUrl': 'http://example.com'}),
])
def test_import_rejects_missing_parents_and_external_urls(
    client, import_user, dictionary, parents,
):
    """Reject ambiguous scopes and client-controlled sources before extraction."""
    client.force_login(import_user('administrator'))
    with patch('api_v1.views.import_locations') as importer:
        response = client.post(reverse(
            'api_v1:location_dictionary_import', kwargs={'dictionary_key': dictionary},
        ), parents, content_type='application/json')
    assert response.status_code == 400
    importer.assert_not_called()


@pytest.mark.django_db
def test_import_validates_city_belongs_to_selected_region(client, import_user):
    """An imported city from a different region is never accepted."""
    first = Region.objects.create(name='Москва', code='77', source_identifier='relation/1')
    second = Region.objects.create(
        name='Тверская область', code='69', source_identifier='relation/2',
    )
    city = City.objects.create(name='Тверь', region=second, source_identifier='node/3')
    client.force_login(import_user('administrator'))
    with patch('api_v1.views.import_locations') as importer:
        response = client.post(reverse(
            'api_v1:location_dictionary_import', kwargs={'dictionary_key': 'metro'},
        ), {'regionId': first.pk, 'cityId': city.pk}, content_type='application/json')
    assert response.status_code == 400
    assert 'cityId' in response.json()
    importer.assert_not_called()


@pytest.mark.django_db
def test_import_reports_source_failure_without_internal_details(client, import_user):
    """Return a useful failure and allow an explicit later retry."""
    client.force_login(import_user('administrator'))
    with patch(
        'api_v1.views.import_locations',
        side_effect=LocationImportError('Источник недоступен.'),
    ):
        response = client.post(reverse(
            'api_v1:location_dictionary_import', kwargs={'dictionary_key': 'regions'},
        ), {}, content_type='application/json')
    assert response.status_code == 502
    assert response.json() == {'detail': 'Источник недоступен.'}


@pytest.mark.django_db
def test_import_is_post_only_and_unsupported_dictionary_is_hidden(client, import_user):
    """Never run imports from a GET request or arbitrary model name."""
    client.force_login(import_user('administrator'))
    url = reverse('api_v1:location_dictionary_import', kwargs={'dictionary_key': 'regions'})
    assert client.get(url).status_code == 405
    assert client.post(reverse(
        'api_v1:location_dictionary_import', kwargs={'dictionary_key': 'users'},
    ), {}, content_type='application/json').status_code == 404


@pytest.mark.django_db
def test_fallback_parent_selection_does_not_expose_csrf_in_redirect(client, import_user):
    """Load city choices without running an import or putting CSRF in a URL."""
    client.force_login(import_user('administrator'))
    with patch('location.views.import_locations') as importer:
        response = client.post(reverse('location:location_import'), {
            'action': 'choose-city', 'dictionary': 'districts',
            'regionId': '2', 'csrfmiddlewaretoken': 'private-test-token',
        })
    assert response.status_code == 302
    assert response.url == '/locations/?dictionary=districts&regionId=2'
    importer.assert_not_called()


@pytest.mark.django_db
def test_full_api_import_pipeline_with_session_and_valid_csrf(import_user):
    """Run every real import handler and loader with only transport replaced."""
    payload = load_sources()

    client = Client(enforce_csrf_checks=True)
    client.force_login(import_user('administrator'))
    assert client.get('/api/v1/auth/session/').status_code == 200
    csrf_token = client.cookies['csrftoken'].value

    def import_dictionary(dictionary, parents=None):
        """Submit a protected API request and require its real success result."""
        response = client.post(reverse(
            'api_v1:location_dictionary_import',
            kwargs={'dictionary_key': dictionary},
        ), parents or {}, content_type='application/json', HTTP_X_CSRFTOKEN=csrf_token)
        assert response.status_code == 200, response.json()
        return response.json()

    with patch(
        'location.open_data.OpenLocationSource.download',
        side_effect=partial(source_reply, payload),
    ):
        assert import_dictionary('regions')['created'] == 3
        region = Region.objects.get(name='Москва')
        assert import_dictionary('cities', {'regionId': region.pk})['created'] == 1
        city = City.objects.get(name='Москва')
        parents = {'regionId': region.pk, 'cityId': city.pk}
        assert import_dictionary('districts', parents)['created'] == 2
        first_metro = import_dictionary('metro', parents)
        assert first_metro['created'] == 2
        assert first_metro['lines']['created'] == 1
        for dictionary, selection in (
            ('regions', {}), ('cities', {'regionId': region.pk}),
            ('districts', parents), ('metro', parents),
        ):
            repeated = import_dictionary(dictionary, selection)
            assert repeated['created'] == repeated['updated'] == 0
        payload['metro']['lines'][0]['color']['fillStyle'] = '#112233'
        updated = import_dictionary('metro', parents)
        assert updated['updated'] == 0
        assert updated['lines']['updated'] == 1

    assert District.objects.filter(city=city).count() == 2
    assert Metro.objects.get(station='Охотный Ряд').metro_line.city_id == city.pk
    assert MetroLine.objects.get(city=city).line_color == '#112233'
