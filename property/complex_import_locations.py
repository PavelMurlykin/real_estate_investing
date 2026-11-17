"""Resolve portable and legacy territory references without legacy writes."""

import re
from dataclasses import dataclass

from django.db.models import Q

from core.json_import import JsonImportError
from location.models import City, Location, LocationClosure, Region
from location.open_data import location_key

from .location_context import locality_filter


def geographic_key(value, category):
    """Normalize explicit geographic type labels without merging homonyms."""
    value = value.casefold().replace('ё', 'е').strip()
    if category == 'region':
        value = re.sub(r'\b(область|обл|край|республика|респ|город|г)\b\.?', ' ', value)
    elif category == 'district':
        value = re.sub(r'\b(район|р-н)\b', ' ', value)
    else:
        value = re.sub(r'^(город|г\.|посёлок|поселок|п\.|село|с\.|деревня|д\.)\s+', '', value)
    return location_key(value)


@dataclass(frozen=True)
class ImportTerritory:
    """Retain the named locality separately from a legacy coarse district."""

    locality: Location
    primary: Location


class ImportLocationResolver:
    """Use canonical IDs and bounded regional lookups for an entire file."""

    def __init__(self):
        """Cache references and small administrative catalogs per import."""
        self.references = {}
        self.legacy = {}
        self.regions = None
        self.districts = {}

    @staticmethod
    def queryset():
        """Preload geography needed to validate hierarchy and produce labels."""
        return Location.objects.select_related('location_type', 'parent', 'region')

    def reference(self, reference):
        """Require one existing, active locality or federal-city role."""
        key = tuple(sorted((name, str(value)) for name, value in reference.items()))
        if key not in self.references:
            queryset = self.queryset().filter(is_active=True).filter(locality_filter())
            if 'id' in reference:
                queryset = queryset.filter(pk=reference['id'])
            else:
                queryset = queryset.filter(
                    identifiers__provider='fias',
                    identifiers__value=str(reference['fias_id']),
                )
            matches = list(queryset.distinct()[:2])
            if len(matches) != 1:
                raise JsonImportError('Населённый пункт не найден. Проверьте ID или ФИАС и загрузку ГАР.')
            self.references[key] = matches[0]
        return self.references[key]

    @staticmethod
    def contains(ancestor, descendant):
        """Check real administrative ancestry, including an identical territory."""
        return ancestor.pk == descendant.pk or LocationClosure.objects.filter(
            ancestor=ancestor, descendant=descendant,
        ).exists()

    def _region(self, row):
        """Prefer explicit old-code mappings and validate the supplied name."""
        old_regions = list(Region.objects.filter(
            code=row['region_code'],
        ).values('pk', 'name'))
        mapped = self.queryset().filter(
            legacy_mappings__model_name='region',
            legacy_mappings__legacy_id__in=[region['pk'] for region in old_regions],
        )
        matches = list(mapped.distinct()[:2])
        key = geographic_key(row['region'], 'region')
        if not matches:
            if self.regions is None:
                self.regions = list(self.queryset().prefetch_related('aliases').filter(
                    location_type__category='region', is_active=True,
                ))
            matches = [region for region in self.regions
                       if any(geographic_key(name, 'region') == key for name in (
                           region.name, *(alias.name for alias in region.aliases.all()),
                       ))]
        labels = [region['name'] for region in old_regions]
        if len(matches) == 1:
            labels.extend([matches[0].name, *(alias.name for alias in matches[0].aliases.all())])
        if len(matches) != 1 or not any(geographic_key(name, 'region') == key for name in labels):
            raise JsonImportError('Регион старого файла не найден однозначно. Укажите локацию в версии 2.')
        return matches[0]

    def legacy_territory(self, row):
        """Adapt old city/district strings through existing canonical geography."""
        key = (row['region_code'], row['region'], row['city'], row['district'])
        if key in self.legacy:
            return self.legacy[key]
        region = self._region(row)
        locality_name = geographic_key(row['city'], 'locality')
        query_name = r'[\W_]+'.join(
            re.escape(word).replace('е', '[её]') for word in locality_name.split()
        )
        localities = list(self.queryset().filter(
            region=region, is_active=True,
        ).filter(locality_filter()).filter(
            Q(name__iregex=f'^{query_name}$') | Q(aliases__name__iexact=row['city']),
        ).distinct()[:3])
        mapped = list(self.queryset().filter(
            region=region, is_active=True, legacy_mappings__model_name='city',
            legacy_mappings__legacy_id__in=City.objects.filter(
                name__iexact=row['city'], region__code=row['region_code'],
            ).values('pk'),
        ).distinct()[:2])
        if len(mapped) == 1:
            localities = mapped
        if len(localities) != 1:
            raise JsonImportError(f'Населённый пункт «{row["city"]}» не найден однозначно. Используйте ФИАС в версии 2.')
        locality = localities[0]
        if region.pk not in self.districts:
            self.districts[region.pk] = list(self.queryset().prefetch_related('aliases').filter(
                region=region, location_type__category='district', is_active=True,
            ))
        district_key = geographic_key(row['district'], 'district')
        districts = [district for district in self.districts[region.pk] if any(
            geographic_key(name, 'district') == district_key
            for name in (district.name, *(alias.name for alias in district.aliases.all()))
        )]
        related = [district for district in districts
                   if self.contains(district, locality) or self.contains(locality, district)]
        if len(related) != 1:
            raise JsonImportError(f'Административный район «{row["district"]}» не найден однозначно в выбранной территории.')
        district = related[0]
        # Old files name a central city plus one of its districts, not a precise suburb.
        primary = district if self.contains(locality, district) else locality
        result = ImportTerritory(locality, primary)
        self.legacy[key] = result
        return result

    def territory(self, row):
        """Resolve an explicit reference or adapt the unchanged legacy fields."""
        if row.get('location'):
            locality = self.reference(row['location'])
            return ImportTerritory(locality, locality)
        return self.legacy_territory(row)

    def primary_for(self, row, territory, existing):
        """Keep precise existing geography when a compatible old file is coarse."""
        current = existing.primary_location if existing else None
        if row.get('location') or current is None or territory.primary.pk == territory.locality.pk:
            return territory.primary
        if self.contains(territory.primary, current):
            return current
        if current.location_type.category != 'district':
            raise JsonImportError('Старый файл противоречит уточнённой территории ЖК. Укажите location в версии 2.')
        return territory.primary
