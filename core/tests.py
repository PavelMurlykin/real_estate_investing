from django.urls import reverse


def test_health_check_returns_ok(client):
    """Health endpoint returns a lightweight JSON response."""
    response = client.get(reverse('health_check'))

    assert response.status_code == 200
    assert response.json() == {'status': 'ok'}
