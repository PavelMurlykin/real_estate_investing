import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode


def registration_payload(**overrides):
    """Build a complete valid account registration payload."""
    payload = {
        'firstName': 'Анна',
        'lastName': 'Иванова',
        'email': 'ANNA@example.com',
        'phoneNumber': '+7 (999) 111-22-33',
        'isRealEstateAgent': True,
        'agencyName': 'Север',
        'password1': 'I9!galaxy-redwood-2026',
        'password2': 'I9!galaxy-redwood-2026',
    }
    payload.update(overrides)
    return payload


def profile_payload(**overrides):
    """Build a complete valid profile update payload."""
    payload = {
        'firstName': 'Павел',
        'lastName': 'Смирнов',
        'email': 'PAVEL.NEW@example.com',
        'phoneNumber': '+7 (999) 444-55-66',
        'isRealEstateAgent': False,
        'agencyName': 'Будет очищено',
    }
    payload.update(overrides)
    return payload


def password_reset_token_payload(user):
    """Build a valid encoded user identifier and one-time reset token."""
    return {
        'userIdentifier': urlsafe_base64_encode(force_bytes(user.pk)),
        'token': default_token_generator.make_token(user),
    }


@pytest.mark.django_db
def test_registration_api_creates_normalized_user_without_session(client):
    """Registration should reuse form normalization and keep users signed out."""
    response = client.post(
        reverse('api_v1:register'),
        data=registration_payload(),
        content_type='application/json',
    )

    assert response.status_code == 201
    assert response.json() == {'registered': True}
    user = get_user_model().objects.get(email='anna@example.com')
    assert user.phone_number == '+79991112233'
    assert user.agency_name == 'Север'
    assert user.check_password('I9!galaxy-redwood-2026')
    assert '_auth_user_id' not in client.session


@pytest.mark.django_db
def test_registration_api_returns_camel_case_form_errors(client):
    """Frontend fields should receive authoritative Django validation errors."""
    response = client.post(
        reverse('api_v1:register'),
        data=registration_payload(
            agencyName='',
            password2='different-password',
        ),
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'agencyName' in response.json()['errors']
    assert 'password2' in response.json()['errors']
    assert get_user_model().objects.count() == 0


@pytest.mark.django_db
def test_registration_api_rejects_authenticated_user(client):
    """An active session must not accidentally create a second account."""
    current_user = get_user_model().objects.create_user(
        email='current@example.com',
        password='safe-test-password',
        phone_number='+79990000010',
    )
    client.force_login(current_user)

    response = client.post(
        reverse('api_v1:register'),
        data=registration_payload(),
        content_type='application/json',
    )

    assert response.status_code == 409
    assert get_user_model().objects.count() == 1


@pytest.mark.django_db
def test_registration_api_requires_csrf_token():
    """Anonymous registration must be protected against cross-site requests."""
    csrf_client = Client(enforce_csrf_checks=True)

    response = csrf_client.post(
        reverse('api_v1:register'),
        data=registration_payload(),
        content_type='application/json',
    )

    assert response.status_code == 403
    assert get_user_model().objects.count() == 0


@pytest.mark.django_db
def test_profile_api_returns_only_current_user_profile(client):
    """Authenticated users should read their own editable profile fields."""
    user = get_user_model().objects.create_user(
        email='profile@example.com',
        password='safe-test-password',
        phone_number='+79990000011',
        first_name='Мария',
        last_name='Петрова',
        is_real_estate_agent=True,
        agency_name='Дом',
    )
    client.force_login(user)

    response = client.get(reverse('api_v1:profile'))

    assert response.status_code == 200
    assert response.json() == {
        'firstName': 'Мария',
        'lastName': 'Петрова',
        'email': 'profile@example.com',
        'phoneNumber': '+79990000011',
        'isRealEstateAgent': True,
        'agencyName': 'Дом',
    }


@pytest.mark.django_db
def test_profile_api_requires_authentication(client):
    """Anonymous visitors must not read or modify profile data."""
    assert client.get(reverse('api_v1:profile')).status_code == 403
    assert client.patch(
        reverse('api_v1:profile'),
        data=profile_payload(),
        content_type='application/json',
    ).status_code == 403


@pytest.mark.django_db
def test_profile_api_updates_current_user_and_normalizes_fields(client):
    """Profile updates should target the session user and reuse Django forms."""
    current_user = get_user_model().objects.create_user(
        email='current@example.com',
        password='safe-test-password',
        phone_number='+79990000012',
        is_real_estate_agent=True,
        agency_name='Старая компания',
    )
    other_user = get_user_model().objects.create_user(
        email='other@example.com',
        password='safe-test-password',
        phone_number='+79990000013',
        first_name='Другой',
    )
    client.force_login(current_user)

    response = client.patch(
        reverse('api_v1:profile'),
        data=profile_payload(),
        content_type='application/json',
    )

    assert response.status_code == 200
    current_user.refresh_from_db()
    other_user.refresh_from_db()
    assert current_user.first_name == 'Павел'
    assert current_user.email == 'pavel.new@example.com'
    assert current_user.phone_number == '+79994445566'
    assert current_user.agency_name == ''
    assert other_user.first_name == 'Другой'


@pytest.mark.django_db
def test_invalid_profile_update_preserves_existing_data(client):
    """A rejected profile must not partially change persisted user data."""
    user = get_user_model().objects.create_user(
        email='unchanged@example.com',
        password='safe-test-password',
        phone_number='+79990000014',
        first_name='До',
    )
    client.force_login(user)

    response = client.patch(
        reverse('api_v1:profile'),
        data=profile_payload(
            email='not-an-email',
            isRealEstateAgent=True,
            agencyName='',
        ),
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'email' in response.json()['errors']
    assert 'agencyName' in response.json()['errors']
    user.refresh_from_db()
    assert user.email == 'unchanged@example.com'
    assert user.first_name == 'До'


@pytest.mark.django_db
def test_profile_api_requires_csrf_token():
    """Session-authenticated profile updates must enforce CSRF protection."""
    csrf_client = Client(enforce_csrf_checks=True)
    user = get_user_model().objects.create_user(
        email='csrf-profile@example.com',
        password='safe-test-password',
        phone_number='+79990000015',
    )
    csrf_client.force_login(user)

    response = csrf_client.patch(
        reverse('api_v1:profile'),
        data=profile_payload(),
        content_type='application/json',
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_password_change_api_updates_password_and_retains_session(client):
    """A valid password change should keep the current session authenticated."""
    user = get_user_model().objects.create_user(
        email='password-change@example.com',
        password='old-safe-password',
        phone_number='+79990000016',
    )
    client.force_login(user)

    response = client.post(
        reverse('api_v1:password_change'),
        data={
            'oldPassword': 'old-safe-password',
            'newPassword1': 'N3w!orbits-redwood-2026',
            'newPassword2': 'N3w!orbits-redwood-2026',
        },
        content_type='application/json',
    )

    assert response.status_code == 200
    assert response.json() == {'changed': True}
    user.refresh_from_db()
    assert user.check_password('N3w!orbits-redwood-2026')
    session_response = client.get(reverse('api_v1:session'))
    assert session_response.json()['isAuthenticated'] is True


@pytest.mark.django_db
def test_password_change_api_rejects_invalid_current_password(client):
    """An invalid current password must not update stored credentials."""
    user = get_user_model().objects.create_user(
        email='invalid-password-change@example.com',
        password='old-safe-password',
        phone_number='+79990000017',
    )
    client.force_login(user)

    response = client.post(
        reverse('api_v1:password_change'),
        data={
            'oldPassword': 'wrong-password',
            'newPassword1': 'N3w!orbits-redwood-2026',
            'newPassword2': 'N3w!orbits-redwood-2026',
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'oldPassword' in response.json()['errors']
    user.refresh_from_db()
    assert user.check_password('old-safe-password')


@pytest.mark.django_db
def test_password_change_api_rejects_mismatched_new_passwords(client):
    """Django validation errors should map to the React confirmation field."""
    user = get_user_model().objects.create_user(
        email='mismatch-password-change@example.com',
        password='old-safe-password',
        phone_number='+79990000018',
    )
    client.force_login(user)

    response = client.post(
        reverse('api_v1:password_change'),
        data={
            'oldPassword': 'old-safe-password',
            'newPassword1': 'N3w!orbits-redwood-2026',
            'newPassword2': 'different-new-password',
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'newPassword2' in response.json()['errors']
    user.refresh_from_db()
    assert user.check_password('old-safe-password')


@pytest.mark.django_db
def test_password_change_api_requires_authentication(client):
    """Anonymous visitors must not submit password changes."""
    response = client.post(
        reverse('api_v1:password_change'),
        data={
            'oldPassword': 'old-safe-password',
            'newPassword1': 'N3w!orbits-redwood-2026',
            'newPassword2': 'N3w!orbits-redwood-2026',
        },
        content_type='application/json',
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_password_change_api_requires_csrf_token():
    """Session-authenticated password changes must enforce CSRF protection."""
    csrf_client = Client(enforce_csrf_checks=True)
    user = get_user_model().objects.create_user(
        email='csrf-password-change@example.com',
        password='old-safe-password',
        phone_number='+79990000019',
    )
    csrf_client.force_login(user)

    response = csrf_client.post(
        reverse('api_v1:password_change'),
        data={
            'oldPassword': 'old-safe-password',
            'newPassword1': 'N3w!orbits-redwood-2026',
            'newPassword2': 'N3w!orbits-redwood-2026',
        },
        content_type='application/json',
    )

    assert response.status_code == 403
    user.refresh_from_db()
    assert user.check_password('old-safe-password')


@pytest.mark.django_db
def test_password_reset_request_sends_react_link_without_enumerating_users(
    client,
):
    """Known and unknown email addresses should receive the same API response."""
    get_user_model().objects.create_user(
        email='reset@example.com',
        password='old-safe-password',
        phone_number='+79990000020',
    )

    known_response = client.post(
        reverse('api_v1:password_reset'),
        data={'email': 'reset@example.com'},
        content_type='application/json',
        REMOTE_ADDR='192.0.2.20',
    )
    unknown_response = client.post(
        reverse('api_v1:password_reset'),
        data={'email': 'unknown@example.com'},
        content_type='application/json',
        REMOTE_ADDR='192.0.2.21',
    )

    assert known_response.status_code == 200
    assert unknown_response.status_code == 200
    assert known_response.json() == unknown_response.json() == {
        'requested': True
    }
    assert len(mail.outbox) == 1
    assert '/app/password/reset/' in mail.outbox[0].body
    assert '/users/password/reset/' not in mail.outbox[0].body


@pytest.mark.django_db
def test_password_reset_request_rejects_invalid_email(client):
    """Malformed addresses should return a field error without sending mail."""
    response = client.post(
        reverse('api_v1:password_reset'),
        data={'email': 'not-an-email'},
        content_type='application/json',
        REMOTE_ADDR='192.0.2.22',
    )

    assert response.status_code == 400
    assert 'email' in response.json()['errors']
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_password_reset_request_is_rate_limited(client):
    """Repeated email requests from one network identity should be bounded."""
    cache.clear()
    request_url = reverse('api_v1:password_reset')
    for request_number in range(5):
        response = client.post(
            request_url,
            data={'email': f'unknown-{request_number}@example.com'},
            content_type='application/json',
            REMOTE_ADDR='192.0.2.23',
        )
        assert response.status_code == 200

    blocked_response = client.post(
        request_url,
        data={'email': 'unknown-final@example.com'},
        content_type='application/json',
        REMOTE_ADDR='192.0.2.23',
    )

    assert blocked_response.status_code == 429


@pytest.mark.django_db
def test_password_reset_request_requires_csrf_token():
    """Anonymous reset email requests must enforce CSRF protection."""
    csrf_client = Client(enforce_csrf_checks=True)

    response = csrf_client.post(
        reverse('api_v1:password_reset'),
        data={'email': 'reset@example.com'},
        content_type='application/json',
        REMOTE_ADDR='192.0.2.24',
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_password_reset_token_exchange_and_confirmation_change_password(client):
    """A valid link should become session-bound before setting a password."""
    user = get_user_model().objects.create_user(
        email='confirm-reset@example.com',
        password='old-safe-password',
        phone_number='+79990000025',
    )

    token_response = client.post(
        reverse('api_v1:password_reset_token'),
        data=password_reset_token_payload(user),
        content_type='application/json',
    )
    confirm_response = client.post(
        reverse('api_v1:password_reset_confirm'),
        data={
            'newPassword1': 'R3set!orbits-redwood-2026',
            'newPassword2': 'R3set!orbits-redwood-2026',
        },
        content_type='application/json',
    )

    assert token_response.status_code == 200
    assert token_response.json() == {'valid': True}
    assert confirm_response.status_code == 200
    assert confirm_response.json()['changed'] is True
    assert confirm_response.json()['session']['isAuthenticated'] is False
    user.refresh_from_db()
    assert user.check_password('R3set!orbits-redwood-2026')
    assert '_react_password_reset_user_identifier' not in client.session
    assert '_react_password_reset_token' not in client.session


@pytest.mark.django_db
def test_invalid_password_reset_token_clears_previous_authorization(client):
    """An invalid replacement link must clear any earlier reset session."""
    user = get_user_model().objects.create_user(
        email='invalid-reset@example.com',
        password='old-safe-password',
        phone_number='+79990000026',
    )
    client.post(
        reverse('api_v1:password_reset_token'),
        data=password_reset_token_payload(user),
        content_type='application/json',
    )

    response = client.post(
        reverse('api_v1:password_reset_token'),
        data={
            'userIdentifier': 'invalid',
            'token': 'invalid-token',
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'token' in response.json()['errors']
    assert '_react_password_reset_user_identifier' not in client.session
    assert '_react_password_reset_token' not in client.session


@pytest.mark.django_db
def test_password_reset_validation_error_preserves_one_time_authorization(
    client,
):
    """Users should be able to correct new-password validation errors."""
    user = get_user_model().objects.create_user(
        email='retry-reset@example.com',
        password='old-safe-password',
        phone_number='+79990000027',
    )
    client.post(
        reverse('api_v1:password_reset_token'),
        data=password_reset_token_payload(user),
        content_type='application/json',
    )

    invalid_response = client.post(
        reverse('api_v1:password_reset_confirm'),
        data={
            'newPassword1': 'R3set!orbits-redwood-2026',
            'newPassword2': 'different-password',
        },
        content_type='application/json',
    )
    valid_response = client.post(
        reverse('api_v1:password_reset_confirm'),
        data={
            'newPassword1': 'R3set!orbits-redwood-2026',
            'newPassword2': 'R3set!orbits-redwood-2026',
        },
        content_type='application/json',
    )

    assert invalid_response.status_code == 400
    assert 'newPassword2' in invalid_response.json()['errors']
    assert valid_response.status_code == 200


@pytest.mark.django_db
def test_password_reset_confirmation_requires_valid_session_authorization(
    client,
):
    """A direct confirmation request without token exchange must fail safely."""
    response = client.post(
        reverse('api_v1:password_reset_confirm'),
        data={
            'newPassword1': 'R3set!orbits-redwood-2026',
            'newPassword2': 'R3set!orbits-redwood-2026',
        },
        content_type='application/json',
    )

    assert response.status_code == 400
    assert 'token' in response.json()['errors']


@pytest.mark.django_db
def test_password_reset_token_and_confirmation_require_csrf():
    """Both unsafe reset steps should require a valid CSRF token."""
    user = get_user_model().objects.create_user(
        email='csrf-reset@example.com',
        password='old-safe-password',
        phone_number='+79990000028',
    )
    csrf_client = Client(enforce_csrf_checks=True)
    token_payload = password_reset_token_payload(user)

    rejected_token_response = csrf_client.post(
        reverse('api_v1:password_reset_token'),
        data=token_payload,
        content_type='application/json',
    )
    session_response = csrf_client.get(reverse('api_v1:session'))
    csrf_token = session_response.cookies['csrftoken'].value
    accepted_token_response = csrf_client.post(
        reverse('api_v1:password_reset_token'),
        data=token_payload,
        content_type='application/json',
        HTTP_X_CSRFTOKEN=csrf_token,
    )
    rejected_confirmation_response = csrf_client.post(
        reverse('api_v1:password_reset_confirm'),
        data={
            'newPassword1': 'R3set!orbits-redwood-2026',
            'newPassword2': 'R3set!orbits-redwood-2026',
        },
        content_type='application/json',
    )

    assert rejected_token_response.status_code == 403
    assert accepted_token_response.status_code == 200
    assert rejected_confirmation_response.status_code == 403
