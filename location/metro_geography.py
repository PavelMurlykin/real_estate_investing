"""Translate metro geography between network centers and legacy identities."""

from dataclasses import dataclass

from django.db.models import BigIntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce, NullIf

from .legacy_catalog import LegacyImportScope, legacy_catalog
from .models import LegacyLocationMapping


@dataclass(frozen=True)
class LegacyMetroCity:
    """Keep the original import scope independently of the network center."""

    city: LegacyImportScope
    region: LegacyImportScope
    location_id: int
    center_name: str


def legacy_metro_city(region_id, city_id):
    """Validate the legacy hierarchy and resolve the canonical center only through mappings."""
    city = legacy_catalog('city').select_related('location').filter(
        legacy_id=city_id, legacy_region_id=region_id,
    ).first()
    if city is None:
        return None
    region = legacy_catalog('region').filter(legacy_id=region_id).first()
    if region is None:
        return None
    return LegacyMetroCity(
        LegacyImportScope.from_mapping(city), LegacyImportScope.from_mapping(region),
        city.location_id, city.location.name,
    )


def annotate_legacy_metro_geography(queryset, line_prefix='metro_line__'):
    """Keep old line labels and IDs available without joining Region or City."""
    references = LegacyLocationMapping.objects.all()
    city = references.filter(model_name='city', legacy_id=OuterRef(f'{line_prefix}legacy_city_id'))
    queryset = queryset.annotate(
        legacy_metro_city_name=Coalesce(
            Subquery(city.exclude(legacy_name='').values('legacy_name')[:1]),
            NullIf(f'{line_prefix}legacy_city_name', Value('')),
        ),
        legacy_metro_region_id=Coalesce(
            Subquery(city.values('legacy_region_id')[:1]), f'{line_prefix}legacy_region_id',
            output_field=BigIntegerField(),
        ),
    )
    region = references.filter(model_name='region', legacy_id=OuterRef('legacy_metro_region_id'))
    return queryset.annotate(legacy_metro_region_name=Coalesce(
        Subquery(region.exclude(legacy_name='').values('legacy_name')[:1]),
        NullIf(f'{line_prefix}legacy_region_name', Value('')),
    ))


def filter_metro_geography(queryset, parameters, *, canonical=False, line_prefix='metro_line__'):
    """Apply legacy filters either to their original IDs or to the mapped network."""
    city_id, region_id = parameters.get('cityId'), parameters.get('regionId')
    if canonical:
        mappings = LegacyLocationMapping.objects.all()
        center = f'{line_prefix}system__location'
        if city_id:
            mapped = mappings.filter(model_name='city', legacy_id=city_id).values('location_id')
            queryset = queryset.filter(**{f'{center}_id__in': mapped})
        if region_id:
            mapped = mappings.filter(model_name='region', legacy_id=region_id).values('location_id')
            queryset = queryset.filter(Q(**{f'{center}__region_id__in': mapped}) | Q(**{f'{center}_id__in': mapped}))
    else:
        if city_id:
            queryset = queryset.filter(**{f'{line_prefix}legacy_city_id': city_id})
        if region_id:
            if 'legacy_metro_region_id' not in queryset.query.annotations:
                queryset = annotate_legacy_metro_geography(queryset, line_prefix)
            queryset = queryset.filter(legacy_metro_region_id=region_id)
    return queryset
