"""Resolve precise geography and retain legacy identifiers for existing clients."""

from dataclasses import dataclass

from django.db import transaction
from django.db.models import Prefetch, Q, prefetch_related_objects

from location.catalog_service import lock_location_catalog
from location.compatibility import canonical_legacy_location
from location.models import LegacyLocationMapping, LocationClosure


def locality_filter():
    """Include federal cities in their locality role without duplicate records."""
    return Q(location_type__category='locality') | Q(
        location_type__category='region',
        location_type__abbreviation__in=['г', 'г.', 'г.ф.з.'],
    )


def ancestor_prefetch(prefix=''):
    """Load the current hierarchy and the associated compatibility identifiers."""
    ancestors = LocationClosure.objects.select_related(
        'ancestor__location_type',
    ).prefetch_related('ancestor__legacy_mappings').order_by('depth', 'ancestor_id')
    return Prefetch(f'{prefix}ancestor_links', queryset=ancestors)


def location_link_queryset():
    """Load geographic context for both primary links and building overrides."""
    from .models import RealEstateComplexLocation

    return RealEstateComplexLocation.objects.select_related(
        'location__location_type', 'location__parent', 'location__region',
    ).prefetch_related(ancestor_prefetch('location__'))


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
    region_location_id: int | None = None
    district_location_id: int | None = None
    locality_id: int | None = None


def primary_location(complex_object):
    """Use prefetched primary links on list/detail queries."""
    links = getattr(complex_object, 'primary_location_links', None)
    if links is None:
        prefetch_related_objects([complex_object], geography_prefetch())
        links = complex_object.primary_location_links
    return links[0].location if links else None


def prefetch_complex_geography(complexes):
    """Batch compatibility fallbacks only for old complexes without a territory."""
    from .models import RealEstateComplexLocation

    prefetch_related_objects(complexes, geography_prefetch())
    missing = [complex_object for complex_object in complexes
               if not complex_object.primary_location_links and complex_object.district_id
               and 'mapped_legacy_location' not in complex_object.__dict__]
    if not missing:
        return
    linked = set(RealEstateComplexLocation.objects.filter(
        real_estate_complex_id__in=[complex_object.pk for complex_object in missing],
    ).values_list('real_estate_complex_id', flat=True))
    mappings = {
        mapping.legacy_id: mapping.location
        for mapping in LegacyLocationMapping.objects.filter(
            model_name='district', legacy_id__in={
                complex_object.district_id for complex_object in missing if complex_object.pk not in linked
            },
        ).select_related('location').prefetch_related(ancestor_prefetch('location__'))
    }
    for complex_object in missing:
        complex_object.mapped_legacy_location = (
            mappings.get(complex_object.district_id) if complex_object.pk not in linked else None
        )


def location_context(complex_object, explicit_location=None):
    """Use a building override, the primary complex location or an old mapping."""
    location = explicit_location or complex_object.primary_location
    if location is None and complex_object.district_id:
        if 'mapped_legacy_location' not in complex_object.__dict__:
            prefetch_complex_geography([complex_object])
        location = complex_object.mapped_legacy_location
    if location is None:
        return LocationContext()
    prefetch_related_objects([location], ancestor_prefetch())
    by_category = {}
    for path in location.ancestor_links.all():
        ancestor = path.ancestor
        by_category.setdefault(ancestor.location_type.category, ancestor)
    region = by_category.get('region')
    locality = by_category.get('locality') or (
        region if region and region.location_type.abbreviation in {'г', 'г.', 'г.ф.з.'} else None
    )
    district = by_category.get('district')

    def legacy_identifier(territory, model_name):
        """Resolve original region/city IDs without inventing legacy records."""
        return next((mapping.legacy_id for mapping in territory.legacy_mappings.all()
                     if mapping.model_name == model_name), None) if territory else None

    legacy_district = None
    if explicit_location is None and district and district.pk == location.pk and complex_object.district_id:
        legacy_district = next((
            mapping for mapping in district.legacy_mappings.all()
            if mapping.model_name == 'district' and mapping.legacy_id == complex_object.district_id
        ), None)
    region_id = legacy_district.legacy_region_id if legacy_district else None
    city_id = legacy_district.legacy_city_id if legacy_district else None

    return LocationContext(
        region_id=region_id or legacy_identifier(region, 'region'),
        city_id=city_id or legacy_identifier(locality, 'city'),
        region=region.name if region else '', city=locality.name if locality else '',
        district=district.name if district else '',
        region_location_id=region.pk if region else None,
        district_location_id=district.pk if district else None,
        locality_id=locality.pk if locality else None,
    )


def clear_geography_cache(complex_object):
    """Discard cached presentation after changing the primary binding."""
    for name in ('primary_location', 'geography', 'primary_location_links', 'mapped_legacy_location'):
        complex_object.__dict__.pop(name, None)
    getattr(complex_object, '_prefetched_objects_cache', {}).pop('location_links', None)


def resolve_legacy_district_edit(complex_id, district):
    """Resolve a district edit while holding locks through the surrounding save."""
    from .models import RealEstateComplex

    lock_location_catalog()
    previous = RealEstateComplex.objects.select_for_update().get(pk=complex_id)
    if previous.district_id == district.pk:
        return None
    primary = previous.primary_location
    if primary is None or (
        primary.location_type.category == 'district' and primary.legacy_mappings.filter(
            model_name='district', legacy_id=previous.district_id,
        ).exists()
    ):
        return canonical_legacy_location(district)
    return None


@transaction.atomic
def set_primary_location(complex_object, location):
    """Change the primary territory while retaining secondary/building bindings."""
    from .models import RealEstateComplex, RealEstateComplexLocation

    RealEstateComplex.objects.select_for_update().get(pk=complex_object.pk)
    complex_object.location_links.filter(is_primary=True).exclude(location=location).update(
        is_primary=False, is_historical=True,
    )
    RealEstateComplexLocation.objects.update_or_create(
        real_estate_complex=complex_object, location=location,
        defaults={'is_primary': True, 'is_historical': False},
    )
    clear_geography_cache(complex_object)
