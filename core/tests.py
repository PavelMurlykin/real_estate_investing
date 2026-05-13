from django.urls import reverse

from real_estate_investing import settings as project_settings


def test_health_check_returns_ok(client):
    """Health endpoint returns a lightweight JSON response."""
    response = client.get(reverse('health_check'))

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}


def test_get_env_int_returns_default_for_blank_value(monkeypatch):
    """Integer environment helper treats blank values as missing."""
    monkeypatch.setenv('EMAIL_PORT', '')

    assert project_settings.get_env_int('EMAIL_PORT', 25) == 25


def test_get_env_int_returns_configured_value(monkeypatch):
    """Integer environment helper parses configured values."""
    monkeypatch.setenv('EMAIL_PORT', '2525')

    assert project_settings.get_env_int('EMAIL_PORT', 25) == 2525
