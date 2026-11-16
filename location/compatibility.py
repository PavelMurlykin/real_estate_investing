"""Map newly created legacy catalog records without changing their IDs."""

from django.db import transaction

from .models import (
    City, District, LegacyLocationMapping, Location, LocationAlias,
    LocationClosure, LocationIdentifier, LocationType,
)


@transaction.atomic
def canonical_legacy_location(row):
    """Resolve one legacy chain, preserving federal-city dual roles."""
    model_name = row._meta.model_name
    mapping = LegacyLocationMapping.objects.filter(model_name=model_name, legacy_id=row.pk).first()
    if mapping:
        return mapping.location
    row = type(row).objects.select_for_update().get(pk=row.pk)
    mapping = LegacyLocationMapping.objects.filter(model_name=model_name, legacy_id=row.pk).first()
    if mapping:
        return mapping.location
    parent = None
    if isinstance(row, District):
        parent = canonical_legacy_location(row.city)
    elif isinstance(row, City):
        parent = canonical_legacy_location(row.region)
    category = 'locality' if model_name == 'city' else model_name
    federal = model_name == 'city' and row.name == row.region.name and row.region.code in {'77', '78', '92'}
    location = parent if federal else None
    source = row.source_identifier or ''
    source_guid = source.removeprefix('fias/') if source.startswith('fias/') else None
    identifier = LocationIdentifier.objects.filter(provider='fias', value=source_guid).first() if source_guid else None
    if identifier:
        location = identifier.location
    if location is None:
        location_type, _ = LocationType.objects.get_or_create(
            code=f'legacy:{category}', defaults={
                'category': category, 'name': {'region': 'Регион', 'locality': 'Город', 'district': 'Административный район'}[category],
            },
        )
        location = Location.objects.create(
            name=row.name, location_type=location_type, parent=parent,
            region_id=parent.region_id if parent else None,
            is_active=row.is_active, needs_review=True,
        )
        if parent is None:
            location.region_id = location.pk
            location.save(update_fields=['region'])
        paths = [LocationClosure(ancestor=location, descendant=location, depth=0)]
        if parent:
            paths.extend(LocationClosure(ancestor_id=path.ancestor_id, descendant=location, depth=path.depth + 1)
                         for path in parent.ancestor_links.all())
        LocationClosure.objects.bulk_create(paths)
    LegacyLocationMapping.objects.create(model_name=model_name, legacy_id=row.pk, location=location)
    LocationIdentifier.objects.get_or_create(provider='legacy', value=f'{model_name}/{row.pk}', defaults={'location': location})
    if source_guid:
        LocationIdentifier.objects.get_or_create(provider='fias', value=source_guid, defaults={'location': location})
    LocationAlias.objects.get_or_create(location=location, name=row.name)
    return location


def bind_new_complex(sender, instance, created, raw=False, **kwargs):
    """Initialize new complexes with the same district binding as the migration."""
    if not created or raw:
        return
    from property.models import RealEstateComplexLocation

    RealEstateComplexLocation.objects.get_or_create(
        real_estate_complex=instance, is_primary=True,
        defaults={'location': canonical_legacy_location(instance.district)},
    )
