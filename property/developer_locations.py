"""Canonical working regions with explicit legacy API adapters."""

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import BigIntegerField, Exists, OuterRef, Prefetch, Q, Subquery, Value, prefetch_related_objects
from django.db.models.functions import Coalesce, NullIf

from location.legacy_catalog import legacy_catalog
from location.catalog_service import lock_location_catalog
from location.models import LegacyLocationMapping
from .models import Developer, DeveloperRegion


def region_references():
    """Translate old IDs only when the mapped Location is a federal subject."""
    return LegacyLocationMapping.objects.filter(model_name='region', location__location_type__category='region')


def legacy_region_names(identifiers=None):
    """Read the old public region identities from their retained namespace."""
    references = legacy_catalog('region')
    if identifiers is not None:
        references = references.filter(legacy_id__in=identifiers)
    return dict(references.values_list('legacy_id', 'legacy_name'))


def developer_region_projections():
    """Project display names and effective regions from links and their mappings."""
    mapped = region_references().filter(legacy_id=OuterRef('region_id'))
    return DeveloperRegion.objects.annotate(
        effective_location_id=Coalesce(
            'location_id', Subquery(mapped.values('location_id')[:1]), output_field=BigIntegerField(),
        ),
        effective_location_name=Coalesce('location__name', Subquery(mapped.values('location__name')[:1])),
        legacy_name=Coalesce(
            Subquery(mapped.exclude(legacy_name='').values('legacy_name')[:1]), NullIf('legacy_region_name', Value('')),
        ),
    )


def filter_developer_regions(queryset, *, legacy_id=None, location_id=None):
    """Match canonical and legacy filters per association without multiplying rows."""
    links = developer_region_projections().filter(developer_id=OuterRef('pk'))
    if legacy_id is not None:
        mapped = region_references().filter(legacy_id=legacy_id).values('location_id')
        queryset = queryset.filter(Exists(links.filter(Q(region_id=legacy_id) | Q(effective_location_id__in=mapped))))
    if location_id is not None:
        queryset = queryset.filter(Exists(links.filter(effective_location_id=location_id)))
    return queryset


def orderable_developer_regions(queryset):
    """Supply the first canonical label before pagination, with a legacy fallback."""
    links = developer_region_projections().filter(developer_id=OuterRef('pk'))
    locations = links.filter(effective_location_name__isnull=False).order_by('effective_location_name', 'pk')
    legacy = links.filter(legacy_name__isnull=False).order_by('legacy_name', 'pk')
    return queryset.annotate(first_region_name=Coalesce(
        Subquery(locations.values('effective_location_name')[:1]), Subquery(legacy.values('legacy_name')[:1]),
    ))


def developer_region_prefetch():
    """Load region projections for an already bounded page."""
    return Prefetch('region_links', queryset=developer_region_projections().order_by('pk'), to_attr='working_region_links')


def prepare_developer_regions(developers):
    """Build both projections in bulk for a bounded page or a detail response."""
    pending = [developer for developer in developers if not hasattr(developer, 'working_region_data')]
    if not pending:
        return
    prefetch_related_objects(pending, developer_region_prefetch())
    missing_names = legacy_region_names({
        link.region_id for developer in pending for link in developer.working_region_links
        if link.region_id and not link.legacy_name
    })
    for developer in pending:
        locations, legacy, unresolved = {}, {}, {}
        for link in developer.working_region_links:
            if link.effective_location_id:
                locations[link.effective_location_id] = link.effective_location_name
            if link.region_id:
                name = link.legacy_name or missing_names.get(link.region_id)
                if name is not None:
                    legacy[link.region_id] = name
                    if not link.effective_location_id:
                        unresolved[link.region_id] = name
        developer.working_region_data = {
            key: [{'id': identifier, 'name': name}
                  for identifier, name in sorted(values.items(), key=lambda item: (item[1], item[0]))]
            for key, values in [('regions', legacy), ('regionLocations', locations), ('unmappedRegions', unresolved)]
        }


@transaction.atomic
def set_developer_regions(
    developer, *, locations=None, legacy_regions=None, additive=False, mappings=None, legacy_names=None,
):
    """Synchronize one ID domain while preserving unrepresentable legacy links."""
    lock_location_catalog()
    Developer.objects.select_for_update().get(pk=developer.pk)
    links = list(DeveloperRegion.objects.filter(developer=developer).order_by('pk'))
    created = []
    changed = []
    if locations is not None:
        if mappings is None:
            mappings = dict(region_references().exclude(legacy_name='').values_list('legacy_id', 'location_id'))
        desired = {item.pk for item in locations}
        if not additive:
            removed = {link.pk for link in links if (location_id := link.location_id or mappings.get(link.region_id))
                       and location_id not in desired}
            DeveloperRegion.objects.filter(pk__in=removed).delete()
            links = [link for link in links if link.pk not in removed]
        for identifier in sorted(desired):
            if any(link.location_id == identifier for link in links):
                continue
            legacy_ids = [old for old, current in mappings.items() if current == identifier]
            existing = next((link for link in links if link.region_id in legacy_ids), None)
            if existing:
                existing.location_id = identifier
                changed.append(existing)
            else:
                created.append(DeveloperRegion(
                    developer=developer, location_id=identifier,
                    region_id=legacy_ids[0] if len(legacy_ids) == 1 else None,
                ))
    else:
        desired = set(legacy_regions or [])
        legacy_names = legacy_region_names(desired) if legacy_names is None else legacy_names
        if desired - legacy_names.keys():
            raise ValidationError('Один из регионов больше не доступен.')
        mappings = dict(region_references().filter(legacy_id__in=desired).values_list('legacy_id', 'location_id'))
        if not additive:
            DeveloperRegion.objects.filter(developer=developer, region_id__isnull=False).exclude(
                region_id__in=desired,
            ).delete()
        for identifier in sorted(desired):
            location_id = mappings.get(identifier)
            existing = next((link for link in links if link.region_id == identifier), None)
            if existing:
                effective_location = location_id or existing.location_id
                name = existing.legacy_region_name if effective_location else legacy_names[identifier]
                if (effective_location, name) != (existing.location_id, existing.legacy_region_name):
                    existing.location_id, existing.legacy_region_name = effective_location, name
                    changed.append(existing)
            else:
                canonical = next((link for link in links if location_id
                                  and link.location_id == location_id and link.region_id is None), None)
                if canonical:
                    canonical.region_id = identifier
                    changed.append(canonical)
                else:
                    created.append(DeveloperRegion(
                        developer=developer, region_id=identifier, location_id=location_id,
                        legacy_region_name='' if location_id else legacy_names[identifier],
                    ))
    if changed:
        DeveloperRegion.objects.bulk_update(changed, ['region_id', 'location', 'legacy_region_name'])
    if created:
        DeveloperRegion.objects.bulk_create(created)
    getattr(developer, '_prefetched_objects_cache', {}).clear()
    for attribute in ('working_region_links', 'working_region_data'):
        developer.__dict__.pop(attribute, None)
    return len(created)
