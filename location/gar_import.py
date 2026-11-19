"""Load complete administrative extracts while retaining legacy identities."""

import re

from django.db import transaction
from django.utils import timezone

from .models import (
    Location, LocationAlias, LocationClosure, LocationIdentifier, LocationType,
)
from .administrative_overrides import SPB_DISTRICTS
from .catalog_service import lock_location_catalog
from .district_verification import verify_catalog_districts


def normalized_name(value):
    """Compare only within a known parent and category, never across Russia."""
    value = value.casefold().replace('ё', 'е')
    return re.sub(r'\s+(?:район|р-н)$', '', value).strip()


def gar_location_type(record, region_code, root_id):
    """Classify verified city types directly under either audited GAR subject."""
    level, abbreviation = record['level'], record['type']
    if (region_code in {'50', '52'} and level == '2' and record['parent'] == root_id
            and abbreviation == 'г.'):
        return 'gar:2:locality:г.', 'locality'
    category = {'1': 'region', '2': 'district'}.get(level, 'locality')
    return f'gar:{level}:{abbreviation}', category


@transaction.atomic
def load_region(records, code, version):
    """Commit one verified region and its closure graph as one restartable unit."""
    lock_location_catalog()
    counts = {key: {'created': 0, 'updated': 0, 'unchanged': 0}
              for key in ('regions', 'cities', 'districts')}
    if not records:
        return counts
    roots = [row for row in records if row['level'] == '1']
    if len(roots) != 1:
        raise ValueError('A regional extract must contain exactly one root.')
    root_record = roots[0]
    root_identifier = LocationIdentifier.objects.filter(
        provider='fias', value=root_record['guid'],
    ).first()
    root = root_identifier.location if root_identifier else None
    bootstrap_root = False
    if root is None:
        code_identifier = LocationIdentifier.objects.filter(
            provider='ru-region-code', value=code, location__location_type__category='region',
        ).select_related('location').first()
        if code_identifier:
            root = code_identifier.location
        else:
            matching_regions = list(Location.objects.filter(
                location_type__category='region', legacy_mappings__model_name='region',
                legacy_mappings__legacy_code=code,
            ).distinct()[:2])
            if len(matching_regions) > 1:
                raise ValueError('Ambiguous region code mapping.')
            root = matching_regions[0] if matching_regions else None
    if code == '78' and root is None:
        root_type, _ = LocationType.objects.get_or_create(
            code=f'gar:1:{root_record["type"]}', defaults={
                'name': root_record['typeName'], 'category': 'region',
                'abbreviation': root_record['type'],
            },
        )
        root = Location.objects.create(name=root_record['name'], location_type=root_type)
        Location.objects.filter(pk=root.pk).update(region_id=root.pk)
        root.region_id = root.pk
        bootstrap_root = True
    existing = list(Location.objects.filter(region_id=root.pk).select_related('location_type')) if root else []
    if root and root.pk not in {row.pk for row in existing}:
        existing.append(root)
    overrides = {}
    if code == '78' and root:
        district_type, _ = LocationType.objects.get_or_create(
            code='administrative:district', defaults={
                'category': 'district', 'name': 'Административный район', 'abbreviation': 'р-н',
            },
        )
        for name, localities in SPB_DISTRICTS.items():
            candidates = [row for row in existing
                          if row.parent_id == root.pk
                          and row.location_type.category == 'district'
                          and normalized_name(row.name) == normalized_name(name)]
            if len(candidates) > 1:
                raise ValueError('Ambiguous administrative district mapping.')
            if candidates:
                district = candidates[0]
            else:
                district = Location.objects.create(
                    name=f'{name} район', location_type=district_type,
                    parent=root, region=root, source_status='verified',
                )
                existing.append(district)
                counts['districts']['created'] += 1
            for identifier in localities:
                overrides[identifier] = district
    by_id = {row.pk: row for row in existing}
    source_ids = dict(LocationIdentifier.objects.filter(
        provider='fias', value__in=[row['guid'] for row in records],
    ).values_list('value', 'location_id'))
    claimed_locations = set(source_ids.values())
    if root:
        claimed_locations.update(LocationIdentifier.objects.filter(
            provider__in=('fias', 'gar'), location__region_id=root.pk,
        ).values_list('location_id', flat=True))
    for row in Location.objects.filter(pk__in=set(source_ids.values()) - by_id.keys()):
        existing.append(row)
        by_id[row.pk] = row
    types = {}
    for row in records:
        type_code, category = gar_location_type(row, code, root_record['id'])
        if type_code not in types:
            types[type_code], _ = LocationType.objects.update_or_create(
                code=type_code, defaults={
                    'category': category, 'name': row['typeName'],
                    'abbreviation': row['type'],
                },
            )
    categories = dict(LocationType.objects.values_list('pk', 'category'))
    natural = {}
    for row in existing:
        key = (row.parent_id, categories[row.location_type_id], normalized_name(row.name))
        natural.setdefault(key, []).append(row)
    resolved, remaining = {}, {row['id']: row for row in records}
    identifiers, aliases = [], []
    changed, created = [], []
    timestamp = timezone.now()
    # Resolve a level at a time, so bulk inserts still get authoritative parents.
    while remaining:
        ready = [row for row in remaining.values()
                 if row['parent'] is None or row['parent'] in resolved]
        if not ready:
            raise ValueError('An extract contains a cycle or missing parent.')
        new_rows, assignments = [], []
        for record in ready:
            type_code, _ = gar_location_type(record, code, root_record['id'])
            location_type = types[type_code]
            parent = (overrides.get(record['guid'])
                      if record['level'] in {'5', '6'} else None) or resolved.get(record['parent'])
            row = by_id.get(source_ids.get(record['guid']))
            if record['level'] == '1':
                row = row or root
            if row is None:
                key = (parent.pk if parent else None, location_type.category, normalized_name(record['name']))
                candidates = [candidate for candidate in natural.get(key, [])
                              if candidate.pk not in claimed_locations]
                row = candidates[0] if len(candidates) == 1 else None
                if row:
                    claimed_locations.add(row.pk)
            values = {
                'name': record['name'], 'location_type_id': location_type.pk,
                'parent_id': parent.pk if parent else None,
                'region_id': root.pk if root else None,
                'source_status': 'verified', 'source_version': version,
                'needs_review': False,
            }
            count_key = {'region': 'regions', 'district': 'districts', 'locality': 'cities'}[
                location_type.category
            ]
            if row is None:
                row = Location(**values)
                new_rows.append(row)
                counts[count_key]['created'] += 1
            else:
                aliases.append(LocationAlias(location_id=row.pk, name=row.name))
                if any(getattr(row, key) != value for key, value in values.items()):
                    for key, value in values.items():
                        setattr(row, key, value)
                    row.updated_at = timestamp
                    changed.append(row)
                    counts[count_key]['created' if bootstrap_root and record['level'] == '1' else 'updated'] += 1
                else:
                    counts[count_key]['unchanged'] += 1
            assignments.append((record, row))
        Location.objects.bulk_create(new_rows, batch_size=1000)
        created.extend(new_rows)
        for record, row in assignments:
            if record['level'] == '1':
                root = row
                row.region_id = row.pk
                Location.objects.filter(pk=row.pk).update(region_id=row.pk)
            resolved[record['id']] = row
            identifiers.extend([
                LocationIdentifier(location_id=row.pk, provider='fias', value=record['guid']),
                LocationIdentifier(location_id=row.pk, provider='gar', value=record['id']),
            ])
            aliases.append(LocationAlias(location_id=row.pk, name=record['name']))
            remaining.pop(record['id'])
    Location.objects.bulk_update(changed, [
        'name', 'location_type', 'parent', 'region', 'source_status',
        'source_version', 'needs_review', 'updated_at',
    ], batch_size=1000)
    LocationIdentifier.objects.bulk_create(identifiers, ignore_conflicts=True, batch_size=1000)
    code_identifier, _ = LocationIdentifier.objects.get_or_create(
        provider='ru-region-code', value=code, defaults={'location_id': root.pk},
    )
    if code_identifier.location_id != root.pk:
        raise ValueError('GAR region code and FIAS identify different locations.')
    LocationAlias.objects.bulk_create(aliases, ignore_conflicts=True, batch_size=1000)
    # Removal in a later full source version never deletes a referenced object.
    Location.objects.filter(region_id=root.pk, source_status='verified',
                            identifiers__provider='gar').exclude(
        pk__in=[row.pk for row in resolved.values()],
    ).update(source_status='retired', is_active=False, needs_review=True)
    if created or changed:
        parents = dict(Location.objects.filter(region_id=root.pk).values_list('pk', 'parent_id'))
        closure = []
        for descendant in parents:
            ancestor, depth, seen = descendant, 0, set()
            while ancestor:
                if ancestor in seen:
                    raise ValueError('Geographic hierarchy contains a cycle.')
                seen.add(ancestor)
                closure.append(LocationClosure(
                    ancestor_id=ancestor, descendant_id=descendant, depth=depth,
                ))
                ancestor, depth = parents.get(ancestor), depth + 1
        LocationClosure.objects.filter(descendant_id__in=parents).delete()
        LocationClosure.objects.bulk_create(closure, batch_size=2000)
    counts['districts']['updated'] += verify_catalog_districts(region_id=root.pk, region_code=code)
    return counts
