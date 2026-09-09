import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_react_frontend_serves_shell_for_root_and_nested_routes(client):
    """Django should preserve browser refreshes for client-side routes."""
    root_response = client.get(reverse('react_frontend:index'))
    nested_response = client.get('/app/properties/')

    assert root_response.status_code == 200
    assert nested_response.status_code == 200
    assert b'id="root"' in root_response.content
    assert b'/static/react/app.js' in nested_response.content


@pytest.mark.django_db
def test_existing_django_home_page_remains_available(client):
    """The legacy server-rendered application must remain operational."""
    response = client.get(reverse('homepage:index'))

    assert response.status_code == 200
    assert b'id="root"' not in response.content
