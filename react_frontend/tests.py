import json

import pytest
from django.test import Client, override_settings
from django.urls import reverse


@pytest.mark.django_db
@pytest.mark.parametrize(
    ('shell_path', 'calculation_path'),
    [
        ('/app/mortgage/', '/api/v1/mortgage/calculate/'),
        ('/app/mortgage/trench/', '/api/v1/mortgage/trench/calculate/'),
    ],
)
def test_shell_initializes_csrf_before_the_session_request(
    settings, shell_path, calculation_path,
):
    """Allow the first API request while retaining mandatory CSRF headers."""
    protected_client = Client(enforce_csrf_checks=True)
    response = protected_client.get(shell_path)
    assert response.status_code == 200
    cookie_name = settings.CSRF_COOKIE_NAME
    assert cookie_name in response.cookies
    token = protected_client.cookies[cookie_name].value
    rejected = protected_client.post(
        calculation_path, {}, content_type='application/json',
    )
    assert rejected.status_code == 403
    validated = protected_client.post(
        calculation_path, {}, content_type='application/json',
        HTTP_X_CSRFTOKEN=token,
    )
    assert validated.status_code == 400
    assert 'propertyCost' in validated.json()


@pytest.mark.django_db
def test_react_frontend_serves_shell_for_root_and_nested_routes(client):
    """Django should preserve browser refreshes for client-side routes."""
    root_response = client.get(reverse('react_frontend:index'))
    nested_response = client.get('/app/properties/')
    mortgage_response = client.get('/app/mortgage/')
    calculation_list_response = client.get('/app/mortgage/calculations/')
    calculation_detail_response = client.get(
        '/app/mortgage/calculations/42/'
    )

    assert root_response.status_code == 200
    assert nested_response.status_code == 200
    assert mortgage_response.status_code == 200
    assert calculation_list_response.status_code == 200
    assert calculation_detail_response.status_code == 200
    assert b'id="root"' in root_response.content
    for response in (
        nested_response, mortgage_response,
        calculation_list_response, calculation_detail_response,
    ):
        script = response.context['react_script']
        assert f'/static/{script}'.encode() in response.content


@pytest.mark.django_db
@override_settings(REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED=False)
def test_existing_django_home_page_remains_available(client):
    """The legacy server-rendered application must remain operational."""
    response = client.get(reverse('homepage:index'))

    assert response.status_code == 200
    assert b'id="root"' not in response.content


@pytest.mark.django_db
def test_react_build_manifest_updates_script_and_stylesheet_urls(
    client, settings, tmp_path, django_assert_num_queries,
):
    """Refresh content-hashed asset URLs after a build without database access."""
    settings.BASE_DIR = tmp_path
    asset_directory = tmp_path / 'static' / 'react' / '.vite'
    asset_directory.mkdir(parents=True)
    manifest_path = asset_directory / 'manifest.json'
    manifest = {'src/main.tsx': {
        'file': 'app-first.js', 'css': ['app-first.css'], 'isEntry': True,
    }}
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')

    with django_assert_num_queries(0):
        response = client.get('/app/properties/')
    assert b'/static/react/app-first.js' in response.content
    assert b'/static/react/app-first.css' in response.content
    manifest['src/main.tsx']['css'] = ['app-second.css']
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    assert b'/static/react/app-second.css' in client.get('/app/').content
    manifest['src/main.tsx']['file'] = 'app-third-version.js'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    assert b'/static/react/app-third-version.js' in client.get(
        '/app/mortgage/'
    ).content


@pytest.mark.django_db
def test_react_shell_handles_assets_before_the_first_build(
    client, settings, tmp_path,
):
    """Keep the shell available when local frontend output is not built yet."""
    settings.BASE_DIR = tmp_path
    response = client.get('/app/')
    assert response.status_code == 200
    assert response.context['react_script'] == 'react/app.js'


@pytest.mark.django_db
def test_react_shell_links_global_stylesheet_with_css_splitting_disabled(
    client, settings, tmp_path,
):
    """Include Vite's standalone style.css manifest entry for a single CSS file."""
    settings.BASE_DIR = tmp_path
    manifest_directory = tmp_path / 'static' / 'react' / '.vite'
    manifest_directory.mkdir(parents=True)
    (manifest_directory / 'manifest.json').write_text(json.dumps({
        'src/main.tsx': {'file': 'app-script.js', 'isEntry': True},
        'style.css': {'file': 'app-global.css'},
    }), encoding='utf-8')
    response = client.get('/app/')
    assert b'/static/react/app-global.css' in response.content
