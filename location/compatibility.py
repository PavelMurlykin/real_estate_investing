"""Map newly created legacy catalog records without changing their IDs."""

from django.db.models import Exists, OuterRef, Q
from django.db.models.functions import Lower

from .models import (
    LocationCompatibilityEntry, Location, LocationAlias,
    LocationClosure, LocationIdentifier, LocationType,
)


def refresh_legacy_mapping(mapping, reference):
    """Update historical metadata and labels without moving a canonical territory."""
    if mapping.model_name == 'city' and 'legacy_region_id' in reference:
        LocationCompatibilityEntry.objects.filter(
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
    """Bind one validated public ID using the same rules as a batch import."""
    mapping, = register_legacy_mappings(model_name, [(legacy_id, reference)], parent=parent)
    return mapping


def _source_guid(reference):
    """Read the canonical FIAS key only from a FIAS source reference."""
    source = reference.get('legacy_source_identifier', '')
    return source.removeprefix('fias/') if source.startswith('fias/') else None


def _region_code(reference):
    """Normalize a Russian subject code without changing the original display code."""
    code = reference.get('legacy_code', '')
    return code.lstrip('0').zfill(2) if code.isdecimal() else code


def register_legacy_mappings(model_name, entries, *, parent=None):
    """Resolve and anchor registry entries for one parent in bounded queries."""
    entries = list(entries)
    if not entries:
        return []
    parent_location = parent.location if parent else None
    category = 'locality' if model_name == 'city' else model_name
    fias_guids = {guid for _, reference in entries if (guid := _source_guid(reference))}
    region_codes = {_region_code(reference) for _, reference in entries} if model_name == 'region' else set()
    identifiers = {
        (identifier.provider, identifier.value): identifier.location for identifier in
        LocationIdentifier.objects.filter(
            Q(provider='fias', value__in=fias_guids)
            | Q(provider='ru-region-code', value__in=region_codes, location__location_type__category='region')
        ).select_related('location')
    }
    names = {reference['legacy_name'].lower() for _, reference in entries}
    occupied = LocationCompatibilityEntry.objects.filter(
        model_name=model_name, location_id=OuterRef('pk'),
    ).exclude(legacy_name='')
    candidates = {}
    for location in Location.objects.alias(folded_name=Lower('name')).filter(
        ~Exists(occupied),
        folded_name__in=names, location_type__category=category, parent=parent_location,
    ):
        candidates.setdefault(location.name.lower(), []).append(location)

    result = []
    pending = []
    for legacy_id, reference in entries:
        name = reference['legacy_name']
        federal = model_name == 'city' and name == parent.legacy_name and parent.legacy_code in {'77', '78', '92'}
        location = identifiers.get(('fias', _source_guid(reference)))
        if location is None and federal:
            location = parent_location
        if location is None and model_name == 'region':
            location = identifiers.get(('ru-region-code', _region_code(reference)))
        if location is None:
            potential = candidates.get(name.lower(), ())
            if len(potential) == 1:
                location = potential[0]
        if location is None:
            location = Location(
                name=name, parent=parent_location, region_id=parent_location.region_id if parent_location else None,
                is_active=reference.get('legacy_is_active', True), needs_review=True,
            )
            pending.append(location)
        result.append((legacy_id, reference, location))

    if pending:
        location_type, _ = LocationType.objects.get_or_create(
            code=f'legacy:{category}', defaults={
                'category': category, 'name': {'region': 'Регион', 'locality': 'Город', 'district': 'Административный район'}[category],
            },
        )
        for location in pending:
            location.location_type = location_type
        Location.objects.bulk_create(pending, batch_size=500)
        if parent_location is None:
            for location in pending:
                location.region_id = location.pk
            Location.objects.bulk_update(pending, ['region'], batch_size=500)
        parent_paths = list(parent_location.ancestor_links.values_list('ancestor_id', 'depth')) if parent_location else []
        paths = []
        for location in pending:
            paths.append(LocationClosure(ancestor=location, descendant=location, depth=0))
            paths.extend(LocationClosure(ancestor_id=ancestor, descendant=location, depth=depth + 1)
                         for ancestor, depth in parent_paths)
        LocationClosure.objects.bulk_create(paths, batch_size=500)

    mappings = LocationCompatibilityEntry.objects.bulk_create([
        LocationCompatibilityEntry(model_name=model_name, legacy_id=legacy_id, location=location, **reference)
        for legacy_id, reference, location in result
    ], batch_size=500)
    links = []
    for legacy_id, reference, location in result:
        links.append(LocationIdentifier(provider='legacy', value=f'{model_name}/{legacy_id}', location=location))
        if guid := _source_guid(reference):
            links.append(LocationIdentifier(provider='fias', value=guid, location=location))
    LocationIdentifier.objects.bulk_create(links, batch_size=500, ignore_conflicts=True)
    LocationAlias.objects.bulk_create([
        LocationAlias(location=location, name=reference['legacy_name']) for _, reference, location in result
    ], batch_size=500, ignore_conflicts=True)
    return mappings


def bind_new_complex(sender, instance, created, raw=False, using='default', **kwargs):
    """Initialize new complexes with the same district binding as the migration."""
    if not created or raw or not instance.district_id:
        return
    from property.models import RealEstateComplexLocation

    location_id = LocationCompatibilityEntry.objects.using(using).filter(
        model_name='district', legacy_id=instance.district_id,
    ).values_list('location_id', flat=True).first()
    if location_id is not None:
        RealEstateComplexLocation.objects.using(using).get_or_create(
            real_estate_complex=instance, is_primary=True, defaults={'location_id': location_id},
        )
