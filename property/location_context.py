"""Resolve precise geography and retain legacy identifiers for existing clients."""

from dataclasses import dataclass

from django.db import transaction
from django.db.models import Prefetch, Q

from location.models import LocationClosure


def locality_filter():
    """Include federal cities in their locality role without duplicate records."""
    return Q(location_type__category='locality') | Q(
        location_type__category='region',
        location_type__abbreviation__in=['г', 'г.', 'г.ф.з.'],
    )


def location_link_queryset():
    """Load geographic context for both primary links and building overrides."""
    from .models import RealEstateComplexLocation

    ancestors = LocationClosure.objects.select_related(
        'ancestor__location_type',
    ).prefetch_related('ancestor__legacy_mappings').order_by('depth')
    return RealEstateComplexLocation.objects.select_related(
        'location__location_type', 'location__parent', 'location__region',
    ).prefetch_related(Prefetch('location__ancestor_links', queryset=ancestors))


def geography_prefetch(prefix=''):
    """Load primary territories and ancestors in a bounded number of queries."""
    links = location_link_queryset().filter(is_primary=True)
    return Prefetch(f'{prefix}location_links', queryset=links, to_attr='primary_location_links')


def building_geography_prefetch(prefix=''):
    """Batch optional overrides while doing no query for inherited locations."""
    return Prefetch(f'{prefix}complex_location', queryset=location_link_queryset())


@dataclass(frozen=True)
class LocationContext:
    """Keep canonical labels separate from nullable legacy catalog identifiers."""

    region_id: int | None = None
    city_id: int | None = None
    region: str = ''
    city: str = ''
    district: str = ''


def primary_location(complex_object):
    """Use prefetched primary links on list/detail queries."""
    links = getattr(complex_object, 'primary_location_links', None)
    if links is None:
        links = list(complex_object.location_links.filter(is_primary=True).select_related(
            'location__location_type', 'location__parent', 'location__region',
        ))
    return links[0].location if links else None


def location_context(complex_object, explicit_location=None):
    """Use precise locality ancestry, falling back to a preserved coarse district."""
    location = explicit_location or complex_object.primary_location
    if explicit_location is None and complex_object.district_id and (
        location is None or location.location_type.category == 'district'
    ):
        district = complex_object.district
        return LocationContext(
            region_id=district.city.region_id, city_id=district.city_id,
            region=district.city.region.name, city=district.city.name,
            district=district.name,
        )
    if location is None:
        return LocationContext()
    paths = location.ancestor_links.all()
    if 'ancestor_links' not in getattr(location, '_prefetched_objects_cache', {}):
        paths = paths.select_related('ancestor__location_type').prefetch_related(
            'ancestor__legacy_mappings',
        ).order_by('depth')
    ancestors = [path.ancestor for path in paths]
    by_category = {}
    for ancestor in sorted(ancestors, key=lambda row: row.pk != location.pk):
        by_category.setdefault(ancestor.location_type.category, ancestor)
    region = by_category.get('region')
    locality = by_category.get('locality') or (
        region if region and region.location_type.abbreviation in {'г', 'г.', 'г.ф.з.'} else None
    )
    district = by_category.get('district')

    def legacy_identifier(territory, model_name):
        """Resolve original region/city IDs without inventing legacy records."""
        if territory:
            return next((mapping.legacy_id for mapping in territory.legacy_mappings.all()
                         if mapping.model_name == model_name), None)
        return None

    return LocationContext(
        region_id=legacy_identifier(region, 'region'),
        city_id=legacy_identifier(locality, 'city'),
        region=region.name if region else '', city=locality.name if locality else '',
        district=district.name if district else '',
    )


def clear_geography_cache(complex_object):
    """Discard cached presentation after changing the primary binding."""
    for name in ('primary_location', 'geography', 'primary_location_links'):
        complex_object.__dict__.pop(name, None)
    getattr(complex_object, '_prefetched_objects_cache', {}).pop('location_links', None)


@transaction.atomic
def set_primary_location(complex_object, location):
    """Change the primary territory while retaining secondary/building bindings."""
    from .models import RealEstateComplex, RealEstateComplexLocation

    RealEstateComplex.objects.select_for_update().get(pk=complex_object.pk)
    complex_object.location_links.filter(is_primary=True).update(is_primary=False)
    RealEstateComplexLocation.objects.update_or_create(
        real_estate_complex=complex_object, location=location,
        defaults={'is_primary': True},
    )
    clear_geography_cache(complex_object)
