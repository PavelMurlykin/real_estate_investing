"""Attach the audited GAR locality to the existing Mys complex."""

from django.db import migrations

from location.catalog_service import lock_location_catalog


def refine_mys_location(apps, schema_editor):
    """Move the known legacy binding from the municipal district to Likino."""
    database = schema_editor.connection.alias
    lock_location_catalog(database)
    complexes = apps.get_model('property', 'RealEstateComplex').objects.using(database)
    links = apps.get_model('property', 'RealEstateComplexLocation').objects.using(database)
    mappings = apps.get_model('location', 'LegacyLocationMapping').objects.using(database)
    locations = apps.get_model('location', 'Location').objects.using(database)
    identifiers = apps.get_model('location', 'LocationIdentifier').objects.using(database)
    complex_object = complexes.select_for_update(of=('self',)).filter(
        source_key='ru:complex:mys',
        district__name='Одинцовский городской округ',
        district__city__region__code='50',
    ).first()
    if complex_object is None:
        return

    # The EISZhS card for building 65525 places the project in Likino. Its
    # GAR path is Moscow Oblast (807356), Odintsovo (862378), Likino (868510).
    official = dict(identifiers.filter(
        provider='gar', value__in=('807356', '862378', '868510'),
    ).values_list('value', 'location_id'))
    if len(official) != 3:
        return
    locality = locations.filter(
        pk=official['868510'], parent_id=official['862378'], region_id=official['807356'],
        location_type__category='locality', is_active=True, source_status='verified', needs_review=False,
        identifiers__provider='fias', identifiers__value='f45a3692-93c0-42d2-807a-80112e346a13',
    ).first()
    if locality is None:
        return

    legacy_territory = mappings.filter(
        model_name='district', legacy_id=complex_object.district_id,
        location__parent_id=locality.parent_id, location__region_id=locality.region_id,
    ).values('location_id')
    complex_links = links.filter(real_estate_complex_id=complex_object.pk)
    previous = complex_links.filter(
        is_primary=True, is_active=True, location_id__in=legacy_territory,
    )
    destination = complex_links.filter(location_id=locality.pk)
    if not previous.exists() or destination.filter(is_active=False).exists():
        return

    previous.update(is_primary=False, is_historical=True)
    links.update_or_create(
        real_estate_complex_id=complex_object.pk, location_id=locality.pk,
        defaults={'is_primary': True, 'is_historical': False},
    )


class Migration(migrations.Migration):
    """Refine existing catalog data using stable identifiers."""

    dependencies = [
        ('location', '0012_reconcile_gar_city_and_district_roles'),
        ('property', '0020_developer_region_locations'),
    ]
    operations = [migrations.RunPython(refine_mys_location, migrations.RunPython.noop)]
