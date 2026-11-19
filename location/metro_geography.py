"""Translate metro geography between network centers and legacy identities."""

from dataclasses import dataclass

from django.db.models import BigIntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce, NullIf

from .models import City, LegacyLocationMapping


@dataclass(frozen=True)
class LegacyMetroCity:
    """Keep the original import scope independently of the network center."""

    identifier: int
    name: str
    region_id: int
    region_name: str
    location_id: int | None
    city: City | None = None


def legacy_metro_city(region_id, city_id):
    """Validate the exact legacy region and city, looking up unreconciled IDs only."""
    mapping = LegacyLocationMapping.objects.filter(model_name='city', legacy_id=city_id).first()
    if mapping and mapping.legacy_region_id and mapping.legacy_name:
        if mapping.legacy_region_id != region_id:
            return None
        name = LegacyLocationMapping.objects.filter(
            model_name='region', legacy_id=region_id,
        ).exclude(legacy_name='').values_list('legacy_name', flat=True).first()
        if name:
            return LegacyMetroCity(city_id, mapping.legacy_name, region_id, name, mapping.location_id)
    city = City.objects.select_related('region').filter(pk=city_id, region_id=region_id).first()
    if city:
        return LegacyMetroCity(city.pk, city.name, city.region_id, city.region.name,
                              mapping.location_id if mapping else None, city)
    return None


def annotate_legacy_metro_geography(queryset, line_prefix='metro_line__'):
    """Keep old line labels and IDs available without joining Region or City."""
    references = LegacyLocationMapping.objects.all()
    city = references.filter(model_name='city', legacy_id=OuterRef(f'{line_prefix}city_id'))
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
            queryset = queryset.filter(**{f'{line_prefix}city_id': city_id})
        if region_id:
            if 'legacy_metro_region_id' not in queryset.query.annotations:
                queryset = annotate_legacy_metro_geography(queryset, line_prefix)
            queryset = queryset.filter(legacy_metro_region_id=region_id)
    return queryset
