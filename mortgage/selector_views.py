"""Bounded public catalog lookups for the native calculator."""

from django import forms
from django.core.paginator import Paginator
from django.db.models import Case, IntegerField, Value, When
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from property.location_context import building_geography_prefetch, geography_prefetch
from property.location_filters import apply_location_scopes
from property.models import Property, RealEstateComplexBuilding

from .location_fields import financial_region_identifier


class CalculatorSelectorQueryForm(forms.Form):
    """Bound externally supplied identifiers before using them in ORM scopes."""

    q = forms.CharField(required=False, max_length=50)

    def __init__(self, *args, **kwargs):
        """Use the same positive bigint bounds for all optional identifiers."""
        super().__init__(*args, **kwargs)
        for name in ['buildingId', 'regionLocationId', 'districtLocationId', 'localityId', 'page']:
            self.fields[name] = forms.IntegerField(
                required=False, min_value=1, max_value=9223372036854775807,
            )


def calculator_properties():
    """Load effective geography in a fixed number of queries per page."""
    return Property.objects.select_related(
        'building__real_estate_complex__district__city__region',
    ).prefetch_related(
        geography_prefetch('building__real_estate_complex__'),
        building_geography_prefetch('building__'),
    )


@require_GET
def property_options(request):
    """Search apartments within one building without exposing private records."""
    from .views import _get_property_payload

    form = CalculatorSelectorQueryForm(request.GET)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)
    parameters = form.cleaned_data
    building_id = parameters.get('buildingId')
    properties = calculator_properties().filter(building_id=building_id)
    properties = apply_location_scopes(properties, parameters, buildings=True)
    query = parameters.get('q', '')
    if query:
        properties = properties.filter(apartment_number__icontains=query)
    properties = properties.annotate(exact_number=Case(
        When(apartment_number__iexact=query, then=Value(0)),
        default=Value(1), output_field=IntegerField(),
    ))
    page = Paginator(properties.order_by('exact_number', 'apartment_number', 'pk'), 20).get_page(
        parameters.get('page') or 1,
    )
    return JsonResponse({
        'properties': [_get_property_payload(item) for item in page],
        'nextPage': page.next_page_number() if page.has_next() else None,
    })


@require_GET
def financial_region(request):
    """Return the financial region through the explicit compatibility mapping."""
    form = CalculatorSelectorQueryForm(request.GET)
    if not form.is_valid():
        return JsonResponse({'errors': form.errors}, status=400)
    region_id = form.cleaned_data.get('regionLocationId')
    identifier = financial_region_identifier(region_id)
    if not region_id:
        building_id = form.cleaned_data.get('buildingId')
        building = RealEstateComplexBuilding.objects.select_related(
            'real_estate_complex__district__city__region',
        ).prefetch_related(
            geography_prefetch('real_estate_complex__'), building_geography_prefetch(),
        ).filter(pk=building_id).first() if building_id else None
        if building and not building.geography.region_location_id:
            identifier = building.geography.region_id
    return JsonResponse({'financialRegionId': identifier})
