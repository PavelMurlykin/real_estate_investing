from collections.abc import Callable, Mapping
from urllib.parse import quote

from django.conf import settings
from django.http import HttpRequest, HttpResponseRedirect, QueryDict
from django.http.response import HttpResponseBase
from django.urls import reverse


LEGACY_VIEW_TO_REACT_ROUTE = {
    'homepage:index': '',
    'users:register': 'register/',
    'users:login': 'login/',
    'users:profile_edit': 'profile/',
    'users:password_change': 'password/change/',
    'users:password_change_done': 'profile/',
    'users:password_reset': 'password/reset/',
    'users:password_reset_done': 'password/reset/',
    'users:password_reset_confirm': 'password/reset/{uidb64}/{token}/',
    'users:password_reset_complete': 'login/',
    'property:dictionary_catalog': 'dictionaries/real-estate-types/',
    'property:company_group_list': 'company-groups/',
    'property:company_group_create': 'company-groups/new/',
    'property:company_group_update': 'company-groups/{pk}/edit/',
    'property:company_group_delete': 'company-groups/',
    'property:developer_list': 'developers/',
    'property:developer_create': 'developers/new/',
    'property:developer_registry_import': 'developers/',
    'property:developer_update': 'developers/{pk}/edit/',
    'property:developer_delete': 'developers/',
    'property:complex_list': 'complexes/',
    'property:complex_create': 'complexes/new/',
    'property:complex_update': 'complexes/{pk}/edit/',
    'property:complex_detail': 'complexes/{pk}/',
    'property:complex_delete': 'complexes/{pk}/',
    'property:list': 'properties/',
    'property:create': 'properties/new/',
    'property:detail': 'properties/{pk}/',
    'property:update': 'properties/{pk}/edit/',
    'property:delete': 'properties/{pk}/',
    'location:location_catalog': 'locations/regions/',
    'bank:catalog': 'banks/',
    'bank:bank_create': 'banks/new/',
    'bank:bank_detail': 'banks/{pk}/',
    'bank:bank_update': 'banks/{pk}/edit/',
    'bank:developer_mortgage_program_list': 'developer-programs/',
    'bank:developer_mortgage_program_create': 'developer-programs/new/',
    'bank:developer_mortgage_program_import': 'developer-programs/',
    'bank:developer_mortgage_program_update': 'developer-programs/{pk}/edit/',
    'bank:developer_mortgage_program_delete': 'developer-programs/{pk}/',
    'bank:key_rate_list': 'key-rate/',
    'mortgage:mortgage_calculator': 'mortgage/',
    'mortgage:calculation_list': 'mortgage/calculations/',
    'mortgage:calculation_detail': 'mortgage/calculations/{pk}/',
    'mortgage:trench_calculation_list': 'mortgage/trench/calculations/',
    'mortgage:trench_calculation_detail': 'mortgage/trench/calculations/{pk}/',
    'customer:list': 'customers/',
    'customer:create': 'customers/new/',
    'customer:detail': 'customers/{pk}/',
    'customer:update': 'customers/{pk}/edit/',
    'customer:delete': 'customers/{pk}/',
}

CATALOG_REACT_ROUTES = {
    'property:dictionary_catalog': {
        'real_estate_type': 'dictionaries/real-estate-types/',
        'real_estate_class': 'dictionaries/real-estate-classes/',
        'apartment_layout': 'dictionaries/apartment-layouts/',
        'apartment_decoration': 'dictionaries/apartment-decorations/',
        'window_view': 'dictionaries/window-views/',
        'transport_accessibility_type': (
            'dictionaries/transport-accessibility-types/'
        ),
    },
    'location:location_catalog': {
        'region': 'locations/regions/',
        'city': 'locations/cities/',
        'district': 'locations/districts/',
        'metro': 'locations/metro/',
        'metro_line': 'locations/metro/',
    },
    'bank:catalog': {
        'bank': 'banks/',
        'mortgage_program': 'mortgage-programs/',
        'mortgage_program_regional_credit_limit': 'mortgage-programs/',
        'mortgage_program_alias': 'mortgage-programs/',
        'bank_program': 'banks/',
    },
}

EDITABLE_CATALOG_MODELS = {
    'property:dictionary_catalog': frozenset(
        CATALOG_REACT_ROUTES['property:dictionary_catalog'],
    ),
    'location:location_catalog': frozenset(
        {
            'region',
            'city',
            'district',
            'metro',
        },
    ),
    'bank:catalog': frozenset({'bank', 'mortgage_program'}),
}


def specialize_catalog_route(
    view_name: str,
    default_route: str,
    query_parameters: QueryDict,
) -> str:
    """Translate a legacy catalog tab and inline edit into a React route."""
    routes_by_model = CATALOG_REACT_ROUTES.get(view_name)
    if routes_by_model is None:
        return default_route

    requested_model = query_parameters.get('model', '')
    route = routes_by_model.get(requested_model, default_route)
    edit_identifier = query_parameters.get('edit', '')
    query_parameters.pop('model', None)
    query_parameters.pop('edit', None)

    if (
        requested_model in EDITABLE_CATALOG_MODELS[view_name]
        and edit_identifier.isdecimal()
    ):
        safe_identifier = quote(edit_identifier, safe='')
        return f'{route}{safe_identifier}/edit/'
    return route


def build_react_frontend_url(
    view_name: str,
    route_keyword_arguments: Mapping[str, object],
    query_parameters: QueryDict | None = None,
) -> str | None:
    """Build a local React URL for a migrated legacy Django page."""
    route_pattern = LEGACY_VIEW_TO_REACT_ROUTE.get(view_name)
    if route_pattern is None:
        return None

    remaining_query_parameters = (
        query_parameters.copy()
        if query_parameters is not None
        else QueryDict()
    )
    route_pattern = specialize_catalog_route(
        view_name,
        route_pattern,
        remaining_query_parameters,
    )

    safe_route_arguments = {
        name: quote(str(value), safe='')
        for name, value in route_keyword_arguments.items()
    }
    try:
        route = route_pattern.format_map(safe_route_arguments)
    except KeyError:
        return None

    frontend_root = reverse('react_frontend:index')
    destination = f'{frontend_root}{route}'
    if remaining_query_parameters:
        query_string = remaining_query_parameters.urlencode()
        if query_string:
            destination = f'{destination}?{query_string}'
    return destination


class LegacyFrontendRedirectMiddleware:
    """Redirect migrated legacy pages to React when cutover is enabled."""

    allowed_methods = frozenset({'GET', 'HEAD'})

    def __init__(
        self,
        get_response: Callable[[HttpRequest], HttpResponseBase],
    ) -> None:
        """Store the next middleware callable."""
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponseBase:
        """Continue the middleware chain for non-redirected requests."""
        return self.get_response(request)

    def process_view(
        self,
        request: HttpRequest,
        view_function: Callable[..., HttpResponseBase],
        view_arguments: tuple[object, ...],
        view_keyword_arguments: dict[str, object],
    ) -> HttpResponseBase | None:
        """Redirect a resolved legacy page without affecting write methods."""
        del view_function, view_arguments
        if not getattr(
            settings,
            'REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED',
            False,
        ):
            return None
        if request.method not in self.allowed_methods:
            return None
        if request.resolver_match is None:
            return None

        destination = build_react_frontend_url(
            request.resolver_match.view_name,
            view_keyword_arguments,
            request.GET,
        )
        if destination is None:
            return None
        return HttpResponseRedirect(destination)
