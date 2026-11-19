"""Complete financial Location links for profiles saved in the previous format."""

from django.db import migrations
from django.db.models import OuterRef, Subquery


def complete_financial_regions(apps, schema_editor):
    """Copy the prior financial region without inferring one from a purchase district."""
    database = schema_editor.connection.alias
    customers = apps.get_model('customer', 'Customer').objects.using(database)
    cities = apps.get_model('location', 'City').objects.using(database).filter(pk=OuterRef('desired_city_id'))
    customers.filter(
        purchase_uses_canonical_locations=False, desired_financial_region_id__isnull=True,
        desired_city_id__isnull=False,
    ).update(desired_financial_region_id=Subquery(cities.values('region_id')[:1]))
    mappings = apps.get_model('location', 'LegacyLocationMapping').objects.using(database).filter(
        model_name='region', legacy_id=OuterRef('desired_financial_region_id'),
        location__location_type__category='region',
    )
    customers.filter(desired_financial_region_location_id__isnull=True, desired_financial_region_id__isnull=False).update(
        desired_financial_region_location_id=Subquery(mappings.values('location_id')[:1]),
    )


class Migration(migrations.Migration):
    """Fill only missing financial associations; retain the original preferences."""

    dependencies = [
        ('customer', '0007_financial_locations'),
        ('location', '0014_legacy_district_ancestry'),
    ]
    operations = [migrations.RunPython(complete_financial_regions, migrations.RunPython.noop)]
