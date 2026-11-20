"""Filter current geographic scopes without mixing canonical and legacy IDs."""

from django.db.models import Exists, OuterRef, Q, QuerySet

from location.models import LocationCompatibilityEntry, Location


SCOPE_PARAMETERS = ('regionLocationId', 'districtLocationId', 'localityId', 'locationId')


def selected_scopes(parameters):
    """Apply every specified scope as an intersection rather than replacing one."""
    return list(dict.fromkeys(parameters[name] for name in SCOPE_PARAMETERS if parameters.get(name)))


def _in_scopes(queryset, lookup, location_id):
    """Require all scopes to contain the same territory, including multi-area ЖК."""
    for identifier in location_id if isinstance(location_id, (list, tuple)) else [location_id]:
        queryset = queryset.filter(**{
            f'{lookup}__in' if isinstance(identifier, QuerySet) else lookup: identifier,
        })
    return queryset


def _legacy_match(district_reference, location_id):
    """Resolve only known legacy correspondences; never match by display name."""
    return _in_scopes(LocationCompatibilityEntry.objects.filter(
        model_name='district', legacy_id=OuterRef(district_reference),
    ), 'location__ancestor_links__ancestor_id', location_id)


def filter_complex_locations(queryset, location_id, prefix=''):
    """Match active territories and explicit building territories, excluding history."""
    from .models import RealEstateComplexBuilding, RealEstateComplexLocation

    current = RealEstateComplexLocation.objects.filter(
        real_estate_complex_id=OuterRef(f'{prefix}pk'), is_historical=False, is_active=True,
    )
    matching = _in_scopes(current, 'location__ancestor_links__ancestor_id', location_id)
    buildings = _in_scopes(RealEstateComplexBuilding.objects.filter(
        real_estate_complex_id=OuterRef(f'{prefix}pk'),
    ), 'complex_location__location__ancestor_links__ancestor_id', location_id)
    all_links = RealEstateComplexLocation.objects.filter(real_estate_complex_id=OuterRef(f'{prefix}pk'))
    return queryset.filter(
        Exists(matching) | Exists(buildings)
        | (~Exists(all_links) & Exists(_legacy_match(f'{prefix}district_id', location_id))),
    )


def filter_property_locations(queryset, location_id, building_prefix='building__'):
    """Use a building override, otherwise inherit only the complex primary."""
    from .models import RealEstateComplexLocation

    primary = RealEstateComplexLocation.objects.filter(
        real_estate_complex_id=OuterRef(f'{building_prefix}real_estate_complex_id'),
        is_primary=True, is_active=True, is_historical=False,
    )
    explicit = _in_scopes(RealEstateComplexLocation.objects.filter(
        pk=OuterRef(f'{building_prefix}complex_location_id'),
    ), 'location__ancestor_links__ancestor_id', location_id)
    inherited = _in_scopes(primary, 'location__ancestor_links__ancestor_id', location_id)
    all_links = RealEstateComplexLocation.objects.filter(
        real_estate_complex_id=OuterRef(f'{building_prefix}real_estate_complex_id'),
    )
    return queryset.filter(
        Exists(explicit)
        | (Q(**{f'{building_prefix}complex_location_id__isnull': True}) & (
            Exists(inherited) | (~Exists(all_links) & Exists(_legacy_match(
                f'{building_prefix}real_estate_complex__district_id', location_id,
            )))
        )),
    )


def apply_location_scopes(queryset, parameters, *, buildings=False, prefix=None):
    """Reuse the same scope rules in catalogs, calculators and customer selection."""
    scopes = selected_scopes(parameters)
    if not scopes:
        return queryset
    return (filter_property_locations(queryset, scopes, 'building__' if prefix is None else prefix)
            if buildings else filter_complex_locations(queryset, scopes, prefix or ''))


def apply_catalog_location_filters(queryset, parameters, *, properties=False):
    """Intersect old city links and canonical scopes on the same actual territory."""
    scopes = selected_scopes(parameters)
    city = parameters.get('cityId') or parameters.get('city')
    if not scopes and not city:
        return queryset
    combined = list(scopes)
    if city:
        combined.append(LocationCompatibilityEntry.objects.filter(
            model_name='city', legacy_id=city,
        ).order_by().values('location_id'))
    return (
        filter_property_locations(queryset, combined)
        if properties else filter_complex_locations(queryset, combined)
    )


def geographic_search_ids(search, *, properties=False):
    """Search names and aliases through effective ancestry, excluding obsolete links."""
    from .models import Property, RealEstateComplex

    locations = Location.objects.filter(
        Q(name__icontains=search) | Q(aliases__name__icontains=search),
    ).order_by().values('pk')
    queryset = (filter_property_locations(Property.objects.all(), locations)
                if properties else filter_complex_locations(RealEstateComplex.objects.all(), locations))
    return queryset.order_by().values('pk')
