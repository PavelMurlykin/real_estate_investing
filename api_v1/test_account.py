import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse


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
