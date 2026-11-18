"""Repair the audited geographic roles and retain all location identities."""

from django.db import migrations

from location.catalog_service import lock_location_catalog
from location.district_verification import verify_legacy_districts


# Verified subject OBJECTIDs and their direct level-two cities in GAR 20261113.
CITIES_BY_SUBJECT = {
    '807356': (
        '807721', '810813', '810889', '815937', '818450', '818579', '819013',
        '821605', '821694', '856608', '861880', '862378', '864776', '878973', '880124',
    ),
    '889307': ('889336',),
}


def reconcile_gar_geography(apps, schema_editor):
    """Reclassify exact GAR identities and confirm the independently audited districts."""
    database = schema_editor.connection.alias
    lock_location_catalog(database)
    locations = apps.get_model('location', 'Location').objects.using(database)
    types = apps.get_model('location', 'LocationType').objects.using(database)
    identifiers = apps.get_model('location', 'LocationIdentifier').objects.using(database)
    official = identifiers.filter(provider='gar')
    subjects = dict(official.filter(
        value__in=CITIES_BY_SUBJECT, location__location_type__category='region',
    ).values_list('value', 'location_id'))
    for subject_identifier, city_identifiers in CITIES_BY_SUBJECT.items():
        subject_id = subjects.get(subject_identifier)
        if not subject_id:
            continue
        cities = locations.filter(
            pk__in=official.filter(value__in=city_identifiers).values('location_id'),
            parent_id=subject_id, region_id=subject_id, location_type__code='gar:2:г.',
            identifiers__provider='fias',
        )
        if cities.exists():
            city_type, _ = types.get_or_create(
                code='gar:2:locality:г.',
                defaults={'category': 'locality', 'name': 'Город', 'abbreviation': 'г.'},
            )
            cities.update(location_type_id=city_type.pk)
    verify_legacy_districts(apps, database)


class Migration(migrations.Migration):
    """Apply the audited, network-independent data correction."""

    dependencies = [('location', '0011_metro_network_identity')]
    operations = [migrations.RunPython(reconcile_gar_geography, migrations.RunPython.noop)]
