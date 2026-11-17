"""Resolve effective apartment geography in SQL for sorting and pagination."""

from django.db.models import (
    BigIntegerField, Case, CharField, Exists, F, OuterRef, Q, Subquery, Value, When,
)
from django.db.models.functions import Coalesce

from location.models import LegacyLocationMapping, Location, LocationClosure

from .location_filters import selected_scopes
from .models import RealEstateComplexLocation


def annotate_property_geography(queryset, building_prefix='property__building__'):
    """Prefer building, primary complex, then explicitly mapped legacy territory."""
    if 'geographic_location_id' in queryset.query.annotations:
        return queryset
    primary = RealEstateComplexLocation.objects.filter(
        real_estate_complex_id=OuterRef(f'{building_prefix}real_estate_complex_id'),
        is_primary=True,
    ).order_by().values('location_id')[:1]
    previous = LegacyLocationMapping.objects.filter(
        model_name='district',
        legacy_id=OuterRef(f'{building_prefix}real_estate_complex__district_id'),
    ).order_by().values('location_id')[:1]
    queryset = queryset.annotate(geographic_location_id=Coalesce(
        F(f'{building_prefix}complex_location__location_id'),
        Subquery(primary), Subquery(previous),
        output_field=BigIntegerField(),
    ))
    ancestry = LocationClosure.objects.filter(
        descendant_id=OuterRef('geographic_location_id'),
    ).order_by('depth', 'ancestor_id')
    localities = ancestry.filter(ancestor__location_type__category='locality')
    federal = ancestry.filter(
        ancestor__location_type__category='region',
        ancestor__location_type__abbreviation__in=('г', 'г.', 'г.ф.з.'),
    )
    district = ancestry.filter(ancestor__location_type__category='district')
    region = ancestry.filter(ancestor__location_type__category='region')
    old_district = f'{building_prefix}real_estate_complex__district'
    annotations = {}
    for category, records, previous_name in (
        ('region', region, f'{old_district}__city__region__name'),
        ('district', district, f'{old_district}__name'),
        ('locality', localities, f'{old_district}__city__name'),
    ):
        identifier = Subquery(
            records.values('ancestor_id')[:1], output_field=BigIntegerField(),
        )
        name = Subquery(records.values('ancestor__name')[:1])
        if category == 'locality':
            identifier = Coalesce(
                identifier, Subquery(federal.values('ancestor_id')[:1]),
                output_field=BigIntegerField(),
            )
            name = Coalesce(name, Subquery(federal.values('ancestor__name')[:1]))
        annotations[f'geographic_{category}_id'] = identifier
        annotations[f'geographic_{category}_name'] = Case(
            When(
                geographic_location_id__isnull=True,
                then=Coalesce(F(previous_name), Value('')),
            ),
            default=Coalesce(name, Value('')), output_field=CharField(),
        )
    return queryset.annotate(**annotations)


def filter_property_geography(
    queryset, parameters, building_prefix='property__building__',
):
    """Intersect all canonical scopes and translate old city IDs explicitly."""
    queryset = annotate_property_geography(queryset, building_prefix)
    for identifier in selected_scopes(parameters):
        queryset = queryset.filter(Exists(LocationClosure.objects.filter(
            descendant_id=OuterRef('geographic_location_id'), ancestor_id=identifier,
        )))
    if parameters.get('city'):
        mapped = LegacyLocationMapping.objects.filter(
            model_name='city', legacy_id=parameters['city'],
        ).order_by().values('location_id')
        matching = LocationClosure.objects.filter(
            descendant_id=OuterRef('geographic_location_id'), ancestor_id__in=mapped,
        )
        queryset = queryset.filter(
            Exists(matching) | Q(**{
                'geographic_location_id__isnull': True,
                f'{building_prefix}real_estate_complex__district__city_id': parameters['city'],
            }),
        )
    return queryset


def property_geography_search(
    queryset, search, building_prefix='property__building__',
):
    """Match names and aliases only on the effective territory's ancestry."""
    queryset = annotate_property_geography(queryset, building_prefix)
    locations = Location.objects.filter(
        Q(name__icontains=search) | Q(aliases__name__icontains=search),
    ).order_by().values('pk')
    ancestry = LocationClosure.objects.filter(
        descendant_id=OuterRef('geographic_location_id'), ancestor_id__in=locations,
    )
    return queryset.filter(Exists(ancestry) | Q(
        geographic_region_name__icontains=search,
    ) | Q(
        geographic_district_name__icontains=search,
    ) | Q(geographic_locality_name__icontains=search))


def geography_payload(calculation):
    """Expose canonical IDs separately from financial legacy region identifiers."""
    return {
        'region': calculation.geographic_region_name,
        'district': calculation.geographic_district_name,
        'city': calculation.geographic_locality_name,
        'regionLocationId': calculation.geographic_region_id,
        'districtLocationId': calculation.geographic_district_id,
        'localityId': calculation.geographic_locality_id,
        'locationId': calculation.geographic_location_id,
    }
