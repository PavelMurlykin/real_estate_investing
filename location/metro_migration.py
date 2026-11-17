"""Complete additive metro references without replacing legacy identities."""


def backfill_metro(apps, schema_editor):
    """Use only explicit city mappings and retain every existing association."""
    database = schema_editor.connection.alias
    lines = apps.get_model('location', 'MetroLine')
    stations = apps.get_model('location', 'Metro')
    systems = apps.get_model('location', 'MetroSystem')
    mappings = dict(apps.get_model('location', 'LegacyLocationMapping').objects.using(
        database,
    ).filter(model_name='city').values_list('legacy_id', 'location_id'))
    pending = []
    for line in lines.objects.using(database).filter(system__isnull=True).select_related('city'):
        if line.city_id is None:
            continue
        system, _ = systems.objects.using(database).get_or_create(
            name=f'Метрополитен: {line.city.name}',
            defaults={'location_id': mappings.get(line.city_id)},
        )
        line.system_id = system.pk
        pending.append(line)
    lines.objects.using(database).bulk_update(pending, ['system'])
    memberships = stations.lines.through
    memberships.objects.using(database).bulk_create([
        memberships(metro_id=identifier, metroline_id=line_identifier)
        for identifier, line_identifier in stations.objects.using(database).values_list(
            'pk', 'metro_line_id',
        )
    ], ignore_conflicts=True)
