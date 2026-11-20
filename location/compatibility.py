"""Map newly created legacy catalog records without changing their IDs."""

from django.db import transaction

from .catalog_service import lock_location_catalog
from .migration_support import legacy_catalog_metadata, legacy_import_reference
from .models import (
    City, District, LegacyLocationMapping, Location, LocationAlias,
    LocationClosure, LocationIdentifier, LocationType,
)


@transaction.atomic
def canonical_legacy_location(row):
    """Resolve one legacy chain and retain the input accepted by older imports."""
    lock_location_catalog()
    return _mapping_for_legacy_row(row).location


def _mapping_for_legacy_row(row):
    """Keep Django and backfills able to register a pre-existing legacy row."""
    model_name = row._meta.model_name
    mapping = LegacyLocationMapping.objects.filter(model_name=model_name, legacy_id=row.pk).first()
    reference = legacy_import_reference(row) | legacy_catalog_metadata(row)
    if isinstance(row, District):
        reference.update(legacy_city_id=row.city_id, legacy_region_id=row.city.region_id)
    elif isinstance(row, City):
        reference['legacy_region_id'] = row.region_id
    if mapping:
        refresh_legacy_mapping(mapping, reference)
        return mapping
    parent = None
    if isinstance(row, District):
        parent = _mapping_for_legacy_row(row.city)
    elif isinstance(row, City):
        parent = _mapping_for_legacy_row(row.region)
    return register_legacy_mapping(model_name, row.pk, reference, parent=parent)


def refresh_legacy_mapping(mapping, reference):
    """Update historical metadata and labels without moving a canonical territory."""
    if mapping.model_name == 'city' and 'legacy_region_id' in reference:
        LegacyLocationMapping.objects.filter(
            model_name='district', legacy_city_id=mapping.legacy_id,
        ).exclude(legacy_region_id=reference['legacy_region_id']).update(
            legacy_region_id=reference['legacy_region_id'],
        )
    changes = {field: value for field, value in reference.items() if getattr(mapping, field) != value}
    if changes:
        for field, value in changes.items():
            setattr(mapping, field, value)
        mapping.save(update_fields=changes)
        if 'legacy_name' in changes and changes['legacy_name']:
            LocationAlias.objects.get_or_create(location_id=mapping.location_id, name=changes['legacy_name'])


def register_legacy_mapping(model_name, legacy_id, reference, *, parent=None):
    """Match or create a canonical territory from the compatibility registry inputs."""
    name = reference['legacy_name']
    parent_location = parent.location if parent else None
    category = 'locality' if model_name == 'city' else model_name
    federal = model_name == 'city' and name == parent.legacy_name and parent.legacy_code in {'77', '78', '92'}
    location = parent_location if federal else None
    source = reference.get('legacy_source_identifier', '')
    source_guid = source.removeprefix('fias/') if source.startswith('fias/') else None
    identifier = LocationIdentifier.objects.filter(provider='fias', value=source_guid).first() if source_guid else None
    if identifier:
        location = identifier.location
    if location is None and model_name == 'region':
        code = reference['legacy_code']
        region_code = code.lstrip('0').zfill(2) if code.isdecimal() else code
        location = Location.objects.filter(
            location_type__category='region',
            identifiers__provider='ru-region-code', identifiers__value=region_code,
        ).first()
    if location is None:
        matching_locations = list(Location.objects.filter(
            name__iexact=name, location_type__category=category, parent=parent_location,
        ).exclude(legacy_mappings__model_name=model_name)[:2])
        if len(matching_locations) == 1:
            location = matching_locations[0]
    if location is None:
        location_type, _ = LocationType.objects.get_or_create(
            code=f'legacy:{category}', defaults={
                'category': category, 'name': {'region': 'Регион', 'locality': 'Город', 'district': 'Административный район'}[category],
            },
        )
        location = Location.objects.create(
            name=name, location_type=location_type, parent=parent_location,
            region_id=parent_location.region_id if parent_location else None,
            is_active=reference.get('legacy_is_active', True), needs_review=True,
        )
        if parent_location is None:
            location.region_id = location.pk
            location.save(update_fields=['region'])
        paths = [LocationClosure(ancestor=location, descendant=location, depth=0)]
        if parent_location:
            paths.extend(LocationClosure(ancestor_id=path.ancestor_id, descendant=location, depth=path.depth + 1)
                         for path in parent_location.ancestor_links.all())
        LocationClosure.objects.bulk_create(paths)
    mapping = LegacyLocationMapping.objects.create(
        model_name=model_name, legacy_id=legacy_id, location=location, **reference,
    )
    LocationIdentifier.objects.get_or_create(provider='legacy', value=f'{model_name}/{legacy_id}', defaults={'location': location})
    if source_guid:
        LocationIdentifier.objects.get_or_create(provider='fias', value=source_guid, defaults={'location': location})
    LocationAlias.objects.get_or_create(location=location, name=name)
    return mapping


def bind_new_complex(sender, instance, created, raw=False, using='default', **kwargs):
    """Initialize new complexes with the same district binding as the migration."""
    if not created or raw or not instance.district_id:
        return
    from property.models import RealEstateComplexLocation

    location_id = LegacyLocationMapping.objects.using(using).filter(
        model_name='district', legacy_id=instance.district_id,
    ).values_list('location_id', flat=True).first()
    if location_id is not None:
        RealEstateComplexLocation.objects.using(using).get_or_create(
            real_estate_complex=instance, is_primary=True, defaults={'location_id': location_id},
        )
