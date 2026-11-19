"""Canonical working regions with explicit legacy API adapters."""

from django.db import transaction

from location.models import LegacyLocationMapping, Region
from .models import Developer, DeveloperRegion


def region_mapping():
    """Resolve legacy IDs only through declared region correspondences."""
    return dict(LegacyLocationMapping.objects.filter(
        model_name='region', location__location_type__category='region',
        legacy_id__in=Region.objects.values('pk'),
    ).values_list('legacy_id', 'location_id'))


@transaction.atomic
def set_developer_regions(
    developer, *, locations=None, legacy_regions=None, additive=False, mappings=None,
):
    """Synchronize one ID domain while preserving unrepresentable legacy links."""
    Developer.objects.select_for_update().get(pk=developer.pk)
    mappings = region_mapping() if mappings is None else mappings
    links = list(DeveloperRegion.objects.filter(developer=developer).order_by('pk'))
    created = []
    changed = []
    if locations is not None:
        desired = {item.pk for item in locations}
        if not additive:
            DeveloperRegion.objects.filter(developer=developer, location__isnull=False).exclude(
                location_id__in=desired,
            ).delete()
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
        desired = {item.pk for item in legacy_regions or []}
        if not additive:
            DeveloperRegion.objects.filter(developer=developer, region__isnull=False).exclude(
                region_id__in=desired,
            ).delete()
        for identifier in sorted(desired):
            location_id = mappings.get(identifier)
            existing = next((link for link in links if link.region_id == identifier), None)
            if existing:
                if existing.location_id != location_id:
                    existing.location_id = location_id
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
                    ))
    if changed:
        DeveloperRegion.objects.bulk_update(changed, ['region', 'location'])
    if created:
        DeveloperRegion.objects.bulk_create(created)
    getattr(developer, '_prefetched_objects_cache', {}).clear()
    return len(created)


def canonical_regions(developer):
    """Deduplicate retained legacy aliases without deleting association rows."""
    return sorted({row.pk: row for row in developer.region_locations.all()}.values(),
                  key=lambda row: (row.name, row.pk))


def unresolved_regions(developer):
    """Expose unconverted legacy associations so editing cannot silently lose them."""
    missing = {link.region_id for link in developer.region_links.all() if link.location_id is None}
    return [{'id': row.pk, 'name': row.name} for row in developer.regions.all() if row.pk in missing]
