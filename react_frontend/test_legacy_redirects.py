from urllib.parse import parse_qs, urlsplit

import pytest
from django.http import HttpResponse, QueryDict
from django.test import RequestFactory, override_settings
from django.urls import resolve, reverse

from .middleware import (
    LEGACY_VIEW_TO_REACT_ROUTE,
    LegacyFrontendRedirectMiddleware,
    build_react_frontend_url,
)


LEGACY_PAGE_REDIRECT_CASES = (
    ('/', '/app/'),
    ('/users/register/', '/app/register/'),
    ('/users/login/', '/app/login/'),
    ('/users/profile/edit/', '/app/profile/'),
    ('/users/password/change/', '/app/password/change/'),
    ('/users/password/change/done/', '/app/profile/'),
    ('/users/password/reset/', '/app/password/reset/'),
    ('/users/password/reset/done/', '/app/password/reset/'),
    (
        '/users/password/reset/user-token/reset-token/',
        '/app/password/reset/user-token/reset-token/',
    ),
    ('/users/password/reset/complete/', '/app/login/'),
    ('/property/dictionaries/', '/app/dictionaries/real-estate-types/'),
    ('/property/company-groups/', '/app/company-groups/'),
    ('/property/company-groups/create/', '/app/company-groups/new/'),
    ('/property/company-groups/11/update/', '/app/company-groups/11/edit/'),
    ('/property/company-groups/11/delete/', '/app/company-groups/'),
    ('/property/developers/', '/app/developers/'),
    ('/property/developers/create/', '/app/developers/new/'),
    ('/property/developers/import-registry/', '/app/developers/'),
    ('/property/developers/11/update/', '/app/developers/11/edit/'),
    ('/property/developers/11/delete/', '/app/developers/'),
    ('/property/complexes/', '/app/complexes/'),
    ('/property/complexes/create/', '/app/complexes/new/'),
    ('/property/complexes/11/update/', '/app/complexes/11/edit/'),
    ('/property/complexes/11/', '/app/complexes/11/'),
    ('/property/complexes/11/delete/', '/app/complexes/11/'),
    ('/property/', '/app/properties/'),
    ('/property/create/', '/app/properties/new/'),
    ('/property/11/', '/app/properties/11/'),
    ('/property/11/update/', '/app/properties/11/edit/'),
    ('/property/11/delete/', '/app/properties/11/'),
    ('/locations/', '/app/locations/regions/'),
    ('/bank/', '/app/banks/'),
    ('/bank/banks/create/', '/app/banks/new/'),
    ('/bank/banks/11/', '/app/banks/11/'),
    ('/bank/banks/11/edit/', '/app/banks/11/edit/'),
    ('/bank/developer-programs/', '/app/developer-programs/'),
    ('/bank/developer-programs/create/', '/app/developer-programs/new/'),
    ('/bank/developer-programs/import/', '/app/developer-programs/'),
    (
        '/bank/developer-programs/11/edit/',
        '/app/developer-programs/11/edit/',
    ),
    ('/bank/developer-programs/11/delete/', '/app/developer-programs/11/'),
    ('/bank/key-rate/', '/app/key-rate/'),
    ('/mortgage/', '/app/mortgage/'),
    ('/mortgage/calculations/', '/app/mortgage/calculations/'),
    ('/mortgage/calculations/11/', '/app/mortgage/calculations/11/'),
    ('/mortgage/trench-calculations/', '/app/mortgage/trench/calculations/'),
    (
        '/mortgage/trench-calculations/11/',
        '/app/mortgage/trench/calculations/11/',
    ),
    ('/customers/', '/app/customers/'),
    ('/customers/create/', '/app/customers/new/'),
    ('/customers/11/', '/app/customers/11/'),
    ('/customers/11/update/', '/app/customers/11/edit/'),
    ('/customers/11/delete/', '/app/customers/11/'),
)


def empty_response(request):
    """Return an inert response for isolated middleware checks."""
    del request
    return HttpResponse()


@pytest.mark.parametrize(
    ('legacy_path', 'expected_location'),
    LEGACY_PAGE_REDIRECT_CASES,
)
@override_settings(REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED=True)
def test_cutover_redirects_every_migrated_legacy_page(
    client,
    legacy_path,
    expected_location,
):
    """Every declared legacy page should resolve to its React destination."""
    response = client.get(legacy_path)

    assert response.status_code == 302
    assert response['Location'] == expected_location


def test_redirect_cases_cover_the_complete_manifest():
    """The redirect manifest must have an independent case for every route."""
    tested_view_names = {
        resolve(legacy_path).view_name
        for legacy_path, _ in LEGACY_PAGE_REDIRECT_CASES
    }

    assert tested_view_names == set(LEGACY_VIEW_TO_REACT_ROUTE)


@override_settings(REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED=True)
def test_cutover_preserves_query_parameters(client):
    """Search, filter and repeated query values should survive redirects."""
    response = client.get(
        reverse('property:list'),
        {'search': 'Москва центр', 'page': 2, 'region': ['1', '2']},
    )
    destination = urlsplit(response['Location'])

    assert response.status_code == 302
    assert destination.path == '/app/properties/'
    assert parse_qs(destination.query) == {
        'search': ['Москва центр'],
        'page': ['2'],
        'region': ['1', '2'],
    }


@pytest.mark.parametrize(
    ('legacy_path', 'expected_location'),
    (
        (
            '/property/dictionaries/?model=window_view&edit=7&page=2',
            '/app/dictionaries/window-views/7/edit/?page=2',
        ),
        (
            '/locations/?model=city&edit=8&page=3',
            '/app/locations/cities/8/edit/?page=3',
        ),
        (
            '/locations/?model=metro_line&edit=9',
            '/app/locations/metro/',
        ),
        (
            '/bank/?model=mortgage_program&edit=10',
            '/app/mortgage-programs/10/edit/',
        ),
        (
            '/bank/?model=mortgage_program_alias&edit=11&page=4',
            '/app/mortgage-programs/?page=4',
        ),
    ),
)
@override_settings(REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED=True)
def test_cutover_translates_catalog_tabs_and_inline_editing(
    client,
    legacy_path,
    expected_location,
):
    """Combined legacy catalogs should open the equivalent React section."""
    response = client.get(legacy_path)

    assert response.status_code == 302
    assert response['Location'] == expected_location


@pytest.mark.parametrize(
    'method',
    ('POST', 'PUT', 'PATCH', 'DELETE', 'OPTIONS'),
)
@override_settings(REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED=True)
def test_cutover_does_not_redirect_write_or_options_requests(method):
    """Non-page methods must retain their existing Django semantics."""
    request = RequestFactory().generic(method, '/')
    request.resolver_match = resolve('/')
    middleware = LegacyFrontendRedirectMiddleware(empty_response)

    assert middleware.process_view(request, empty_response, [], {}) is None


@override_settings(REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED=True)
def test_cutover_supports_head_requests(client):
    """HEAD should return the same temporary redirect as GET."""
    response = client.head('/')

    assert response.status_code == 302
    assert response['Location'] == '/app/'


@pytest.mark.parametrize(
    ('view_name', 'route_keyword_arguments'),
    (
        ('api_v1:session', {}),
        ('health_check', {}),
        ('react_frontend:index', {}),
        ('customer:calculations_export_word', {'pk': 11}),
        ('customer:calculation_delete', {'pk': 11}),
        ('customer:trench_calculation_delete', {'pk': 11}),
        ('mortgage:property_cost_api', {'pk': 11}),
        ('mortgage:developer_mortgage_programs_api', {}),
        ('mortgage:calculation_delete', {'pk': 11}),
        ('mortgage:trench_calculation_delete', {'pk': 11}),
        ('bank:developer_mortgage_program_complex_options', {}),
        ('users:logout', {}),
    ),
)
@override_settings(REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED=True)
def test_cutover_excludes_api_download_and_action_routes(
    view_name,
    route_keyword_arguments,
):
    """Only migrated HTML pages, not APIs or actions, may be redirected."""
    legacy_path = reverse(view_name, kwargs=route_keyword_arguments)
    request = RequestFactory().get(legacy_path)
    request.resolver_match = resolve(legacy_path)
    middleware = LegacyFrontendRedirectMiddleware(empty_response)

    assert middleware.process_view(
        request,
        empty_response,
        [],
        route_keyword_arguments,
    ) is None


@override_settings(REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED=False)
def test_disabled_cutover_keeps_legacy_view_execution():
    """Turning off the flag should restore legacy pages without redirects."""
    request = RequestFactory().get('/')
    request.resolver_match = resolve('/')
    middleware = LegacyFrontendRedirectMiddleware(empty_response)

    assert middleware.process_view(request, empty_response, [], {}) is None
    assert middleware(request).status_code == 200


def test_redirect_builder_encodes_dynamic_path_segments():
    """Path arguments and query values must not change the local origin."""
    destination = build_react_frontend_url(
        'users:password_reset_confirm',
        {'uidb64': '//external.example', 'token': 'token?next=bad'},
        QueryDict('next=https%3A%2F%2Fexternal.example'),
    )

    assert destination == (
        '/app/password/reset/%2F%2Fexternal.example/token%3Fnext%3Dbad/'
        '?next=https%3A%2F%2Fexternal.example'
    )


def test_redirect_builder_fails_closed_for_missing_arguments():
    """An incomplete route must fall through rather than crash a request."""
    assert build_react_frontend_url('property:detail', {}) is None
    assert build_react_frontend_url('unknown:view', {}) is None
