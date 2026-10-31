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


def translate_legacy_query_parameters(view_name, parameters):
    """Translate legacy business context and table state to React names."""
    aliases = {'customer': 'customerId'}
    ordering_fields = {}
    ordering_parameter = 'ordering'
    if view_name == 'mortgage:mortgage_calculator':
        aliases['property_id'] = 'propertyId'
    elif view_name == 'property:list':
        aliases.update({
            'filter_city': 'city', 'filter_developer': 'developer',
            'filter_complex': 'realEstateComplex',
            'filter_building': 'building',
            'filter_apartment_number': 'apartmentNumber',
            'filter_layout': 'layout', 'filter_area': 'area',
            'filter_property_cost': 'propertyCost',
        })
        ordering_fields = {
            'city': 'city', 'developer': 'developer',
            'complex': 'realEstateComplex', 'building': 'building',
            'apartment_number': 'apartmentNumber', 'layout': 'layout',
            'area': 'area', 'property_cost': 'propertyCost',
        }
    elif view_name in {
        'mortgage:calculation_list', 'mortgage:trench_calculation_list',
        'customer:detail',
    }:
        for prefix in ('cost', 'initial_payment', 'monthly_payment',
                       'term', 'rate'):
            new_prefix = {
                'initial_payment': 'initialPayment',
                'monthly_payment': 'monthlyPayment',
            }.get(prefix, prefix)
            for boundary in ('from', 'to'):
                aliases[f'{prefix}_{boundary}'] = (
                    f'{new_prefix}{boundary.capitalize()}'
                )
        ordering_fields = {
            'city': 'city', 'timestamp': 'createdAt',
            'object': 'realEstateComplex', 'cost': 'finalPropertyCost',
            'initial_payment': 'initialPaymentRubles',
            'monthly_payment': (
                'mainMonthlyPayment'
                if view_name == 'mortgage:calculation_list'
                else 'monthlyPayment'
            ),
            'term': 'mortgageTermMonths', 'rate': 'annualRate',
        }
        if view_name == 'customer:detail':
            aliases.update({'city': 'city', 'q': 'q'})
            aliases = {
                old: f'calculation{new[0].upper()}{new[1:]}'
                for old, new in aliases.items()
                if old != 'customer'
            }
            ordering_parameter = 'calculationOrdering'
    else:
        aliases['filter_name'] = 'q'
        ordering_fields = {'name': 'name'}
        if view_name == 'property:developer_list':
            aliases.update({
                'filter_company_group': 'companyGroupId',
                'filter_region': 'regionId',
            })
            ordering_fields['company_group'] = 'companyGroup'
        elif view_name == 'property:complex_list':
            aliases.update({
                'filter_name': 'search', 'filter_developer': 'developerId',
                'filter_city': 'cityId',
                'filter_real_estate_class': 'realEstateClassId',
                'filter_real_estate_type': 'realEstateTypeId',
                'filter_buildings_count': 'buildingCount',
            })
            ordering_fields.update({
                'developer': 'developer', 'city': 'city',
                'real_estate_class': 'realEstateClass',
                'real_estate_type': 'realEstateType',
                'buildings_count': 'buildingCount',
            })
        elif view_name == 'location:location_catalog':
            aliases.update({
                'filter_city': 'cityId', 'filter_metro_line': 'metroLineId',
            })
            ordering_fields.update({
                'station': 'name', 'metro_line': 'metroLine',
                'metro_line__city': 'city',
            })
        elif view_name == 'bank:catalog':
            aliases['filter_bank_scope'] = 'scope'
    for old_name, new_name in aliases.items():
        if old_name not in parameters or old_name == new_name:
            continue
        if new_name not in parameters:
            parameters.setlist(new_name, parameters.getlist(old_name))
        parameters.pop(old_name)
    if parameters.get('scope') == 'with_programs':
        parameters['scope'] = 'withPrograms'
    sort_field = parameters.get('sort_by') or parameters.get('sort')
    if sort_field in ordering_fields:
        direction = parameters.get('sort_dir') or parameters.get('order')
        prefix = '-' if direction == 'desc' else ''
        parameters.setdefault(
            ordering_parameter, f'{prefix}{ordering_fields[sort_field]}'
        )
        for name in ('sort_by', 'sort_dir', 'sort', 'order'):
            parameters.pop(name, None)


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
    translate_legacy_query_parameters(view_name, remaining_query_parameters)

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
        if request.GET.get('legacy') == '1':
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
