"""Preserve legacy labels and fill missing canonical developer regions."""

from django.db import migrations, models
from django.db.models import OuterRef, Subquery
from django.db.models.functions import Coalesce


def complete_developer_regions(apps, schema_editor):
    """Backfill associations in place, retaining identity, status and timestamps."""
    database = schema_editor.connection.alias
    links = apps.get_model('property', 'DeveloperRegion').objects.using(database)
    regions = apps.get_model('location', 'Region').objects.using(database).filter(pk=OuterRef('region_id'))
    mappings = apps.get_model('location', 'LegacyLocationMapping').objects.using(database).filter(
        model_name='region', legacy_id=OuterRef('region_id'), location__location_type__category='region',
    )
    links.filter(region_id__isnull=False, legacy_region_name='').update(
        legacy_region_name=Subquery(regions.values('name')[:1]),
        location_id=Coalesce('location_id', Subquery(mappings.values('location_id')[:1]), output_field=models.BigIntegerField()),
    )


class Migration(migrations.Migration):
    """Complete developer-region metadata without changing the legacy tables."""

    dependencies = [('property', '0021_refine_mys_location'), ('location', '0014_legacy_district_ancestry')]
    operations = [
        migrations.AddField(
            model_name='developerregion', name='legacy_region_name',
            field=models.CharField(blank=True, max_length=100),
        ),
        migrations.RunPython(complete_developer_regions, migrations.RunPython.noop),
    ]
