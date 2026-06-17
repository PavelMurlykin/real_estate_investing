from django.conf import settings
from django.http import JsonResponse
from django.urls import path
from django.views.decorators.http import require_GET

from location.models import City, District

from .models import RealEstateComplex, RealEstateComplexBuilding

CITY_API_FIELDS = ('id', 'name')
DISTRICT_API_FIELDS = ('id', 'name')
COMPLEX_API_FIELDS = (
    'id',
    'name',
    'developer_id',
    'district_id',
    'district__city_id',
    'district__city__region_id',
)
BUILDING_API_FIELDS = ('id', 'number', 'real_estate_complex_id')


def get_public_catalog_api_limit():
    """Return the maximum number of rows exposed by public catalog APIs."""
    return getattr(settings, 'PUBLIC_CATALOG_API_MAX_RESULTS', 200)


def parse_positive_integer_param(request, name):
    """Return a positive integer query parameter or an error response."""
    value = request.GET.get(name)
    if value in (None, ''):
        return None, None

    try:
        parsed_value = int(value)
    except (TypeError, ValueError):
        return None, JsonResponse(
            {'error': f'Invalid {name}.'},
            status=400,
        )

    if parsed_value <= 0:
        return None, JsonResponse(
            {'error': f'Invalid {name}.'},
            status=400,
        )

    return parsed_value, None


def limited_json_response(queryset):
    """Return a bounded JSON response for public selector endpoints."""
    return JsonResponse(
        list(queryset[:get_public_catalog_api_limit()]),
        safe=False,
    )


@require_GET
def cities_api(request):
    """Return cities for a selected region."""
    region_id, error_response = parse_positive_integer_param(
        request,
        'region_id',
    )
    if error_response:
        return error_response

    cities = City.objects.none()
    if region_id is not None:
        cities = City.objects.filter(region_id=region_id)

    return limited_json_response(
        cities.order_by('name').values(*CITY_API_FIELDS)
    )


@require_GET
def districts_api(request):
    """Return districts for a selected city."""
    city_id, error_response = parse_positive_integer_param(
        request,
        'city_id',
    )
    if error_response:
        return error_response

    districts = District.objects.none()
    if city_id is not None:
        districts = District.objects.filter(city_id=city_id)

    return limited_json_response(
        districts.order_by('name').values(*DISTRICT_API_FIELDS)
    )


@require_GET
def complexes_api(request):
    """Return complexes for selected public catalog filters."""
    region_id, error_response = parse_positive_integer_param(
        request,
        'region_id',
    )
    if error_response:
        return error_response

    city_id, error_response = parse_positive_integer_param(
        request,
        'city_id',
    )
    if error_response:
        return error_response

    district_id, error_response = parse_positive_integer_param(
        request,
        'district_id',
    )
    if error_response:
        return error_response

    developer_id, error_response = parse_positive_integer_param(
        request,
        'developer_id',
    )
    if error_response:
        return error_response

    complexes = RealEstateComplex.objects.select_related(
        'developer',
        'district__city__region',
    )
    if not any((region_id, city_id, district_id, developer_id)):
        complexes = complexes.none()
    if developer_id:
        complexes = complexes.filter(developer_id=developer_id)
    if district_id:
        complexes = complexes.filter(district_id=district_id)
    elif city_id:
        complexes = complexes.filter(district__city_id=city_id)
    elif region_id:
        complexes = complexes.filter(district__city__region_id=region_id)

    return limited_json_response(
        complexes.order_by('name').values(*COMPLEX_API_FIELDS)
    )


@require_GET
def buildings_api(request):
    """Return buildings for a selected complex."""
    complex_id, error_response = parse_positive_integer_param(
        request,
        'complex_id',
    )
    if error_response:
        return error_response

    buildings = RealEstateComplexBuilding.objects.none()
    if complex_id is not None:
        buildings = RealEstateComplexBuilding.objects.filter(
            real_estate_complex_id=complex_id
        )

    return limited_json_response(
        buildings.order_by('number').values(*BUILDING_API_FIELDS)
    )


urlpatterns = [
    path('cities/', cities_api, name='cities_api'),
    path('districts/', districts_api, name='districts_api'),
    path('complexes/', complexes_api, name='complexes_api'),
    path('buildings/', buildings_api, name='buildings_api'),
]
