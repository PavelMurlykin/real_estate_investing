"""Keep additive geographic migration logic compatible with historical models."""


def legacy_import_reference(row):
    """Preserve inputs accepted by the existing file and registry formats."""
    return {
        'legacy_name': row.name,
        'legacy_code': getattr(row, 'code', ''),
        'legacy_source_identifier': row.source_identifier or '',
    }


def backfill_locations(registry, database='default', *, geography_only=False):
    """Map legacy records and complexes without changing any legacy field."""
    Location = registry.get_model('location', 'Location')
    LocationType = registry.get_model('location', 'LocationType')
    Identifier = registry.get_model('location', 'LocationIdentifier')
    Mapping = registry.get_model('location', 'LegacyLocationMapping')
    Alias = registry.get_model('location', 'LocationAlias')
    Closure = registry.get_model('location', 'LocationClosure')
    Region = registry.get_model('location', 'Region')
    City = registry.get_model('location', 'City')
    District = registry.get_model('location', 'District')
    types = {}
    for category, name, abbreviation in [
        ('region', 'Регион', ''), ('locality', 'Город', 'г.'),
        ('district', 'Административный район', 'р-н'),
    ]:
        types[category], _ = LocationType.objects.using(database).get_or_create(
            code=f'legacy:{category}', defaults={
                'category': category, 'name': name, 'abbreviation': abbreviation,
            },
        )
    existing_mappings = {
        (row.model_name, row.legacy_id): row for row in Mapping.objects.using(database).all()
    }
    mappings = {key: row.location_id for key, row in existing_mappings.items()}
    capture_references = any(field.name == 'legacy_name' for field in Mapping._meta.fields)
    capture_region_parent = any(field.name == 'legacy_region_id' for field in Mapping._meta.fields)
    references_to_update = []
    aliases_to_preserve = []
    identifiers = {
        (row.provider, row.value): row.location_id
        for row in Identifier.objects.using(database).filter(
            provider__in=['fias', 'legacy', 'ru-region-code'],
        )
    }

    def preserve(model_name, row, category, parent=None, region=None, reuse=None):
        """Retain one identity, with explicit aliases for shared federal-city roles."""
        key = (model_name, row.pk)
        reference = legacy_import_reference(row) if capture_references else {}
        if model_name == 'city' and capture_region_parent:
            reference['legacy_region_id'] = row.region_id
        if key in mappings:
            mapping = existing_mappings[key]
            if any(getattr(mapping, field) != value for field, value in reference.items()):
                for field, value in reference.items():
                    setattr(mapping, field, value)
                references_to_update.append(mapping)
                aliases_to_preserve.append(Alias(location_id=mapping.location_id, name=row.name))
            return mappings[key]
        source = row.source_identifier or ''
        fias = source.removeprefix('fias/') if source.startswith('fias/') else None
        identifier = reuse or identifiers.get(('fias', fias))
        if identifier is None and capture_references and category == 'region':
            identifier = identifiers.get(('ru-region-code', row.code))
        if identifier is None:
            location = Location.objects.using(database).create(
                name=row.name, location_type=types[category],
                parent_id=parent, region_id=region, is_active=row.is_active,
                source_status='unverified', needs_review=True,
            )
            identifier = location.pk
            if category == 'region':
                Location.objects.using(database).filter(pk=identifier).update(region_id=identifier)
        Mapping.objects.using(database).create(
            model_name=model_name, legacy_id=row.pk, location_id=identifier,
            method='federal_role' if reuse else 'preserved',
            **reference,
        )
        mappings[key] = identifier
        Identifier.objects.using(database).get_or_create(
            provider='legacy', value=f'{model_name}/{row.pk}',
            defaults={'location_id': identifier},
        )
        if fias:
            Identifier.objects.using(database).get_or_create(
                provider='fias', value=fias, defaults={'location_id': identifier},
            )
            identifiers[('fias', fias)] = identifier
        Alias.objects.using(database).get_or_create(location_id=identifier, name=row.name)
        return identifier

    regions = {}
    region_rows = list(Region.objects.using(database).all())
    for row in region_rows:
        regions[row.pk] = preserve('region', row, 'region')
    names = {row.pk: row.name.casefold().strip() for row in region_rows}
    cities = {}
    for row in City.objects.using(database).all():
        root = regions[row.region_id]
        federal = names[row.region_id] == row.name.casefold().strip() and names[row.region_id] in {
            'москва', 'санкт-петербург', 'севастополь',
        }
        cities[row.pk] = preserve(
            'city', row, 'locality', parent=root, region=root,
            reuse=root if federal else None,
        )
    city_regions = dict(City.objects.using(database).values_list('pk', 'region_id'))
    for row in District.objects.using(database).all():
        preserve(
            'district', row, 'district', parent=cities[row.city_id],
            region=regions[city_regions[row.city_id]],
        )
    if references_to_update:
        fields = ['legacy_name', 'legacy_code', 'legacy_source_identifier']
        if capture_region_parent:
            fields.append('legacy_region_id')
        Mapping.objects.using(database).bulk_update(
            references_to_update, fields,
            batch_size=1000,
        )
        Alias.objects.using(database).bulk_create(
            aliases_to_preserve, batch_size=1000, ignore_conflicts=True,
        )
    parents = dict(Location.objects.using(database).values_list('pk', 'parent_id'))
    mapped_locations = set(mappings.values())
    existing_closure = set(Closure.objects.using(database).filter(
        descendant_id__in=mapped_locations,
    ).values_list('ancestor_id', 'descendant_id'))
    paths = []
    for descendant in mapped_locations:
        ancestor, depth, seen = descendant, 0, set()
        while ancestor is not None:
            if ancestor in seen:
                raise ValueError('Geographic hierarchy contains a cycle.')
            seen.add(ancestor)
            if (ancestor, descendant) not in existing_closure:
                paths.append(Closure(ancestor_id=ancestor, descendant_id=descendant, depth=depth))
            ancestor, depth = parents.get(ancestor), depth + 1
    Closure.objects.using(database).bulk_create(paths, batch_size=1000, ignore_conflicts=True)
    if geography_only:
        return
    Complex = registry.get_model('property', 'RealEstateComplex')
    Link = registry.get_model('property', 'RealEstateComplexLocation')
    linked = set(Link.objects.using(database).filter(is_primary=True).values_list('real_estate_complex_id', flat=True))
    Link.objects.using(database).bulk_create([
        Link(real_estate_complex_id=row.pk, location_id=mappings[('district', row.district_id)], is_primary=True)
        for row in Complex.objects.using(database).exclude(district_id=None)
        if row.pk not in linked
    ], batch_size=1000, ignore_conflicts=True)
    MetroLine = registry.get_model('location', 'MetroLine')
    Metro = registry.get_model('location', 'Metro')
    System = registry.get_model('location', 'MetroSystem')
    for city_id in MetroLine.objects.using(database).exclude(city_id=None).order_by().values_list('city_id', flat=True).distinct():
        city = City.objects.using(database).get(pk=city_id)
        system, _ = System.objects.using(database).get_or_create(
            name=f'Метрополитен: {city.name}', defaults={'location_id': cities[city_id]},
        )
        MetroLine.objects.using(database).filter(city_id=city_id, system_id=None).update(system_id=system.pk)
    memberships = []
    Membership = Metro.lines.through
    for station in Metro.objects.using(database).select_related('metro_line'):
        if (
            station.location_id is None and station.metro_line.city_id in cities
            and getattr(station, 'location_is_inferred', True)
        ):
            Metro.objects.using(database).filter(pk=station.pk).update(location_id=cities[station.metro_line.city_id])
        memberships.append(Membership(metro_id=station.pk, metroline_id=station.metro_line_id))
    Membership.objects.using(database).bulk_create(memberships, ignore_conflicts=True, batch_size=1000)
