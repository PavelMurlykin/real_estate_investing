"""Preserve legacy import inputs in canonical location mappings."""

from django.db import migrations, models

from location.catalog_service import lock_location_catalog
from location.migration_support import backfill_locations


def capture_import_references(apps, schema_editor):
    """Copy import references without changing existing business relationships."""
    database = schema_editor.connection.alias
    lock_location_catalog(database)
    backfill_locations(apps, database, geography_only=True)


class Migration(migrations.Migration):
    """Add the metadata needed by existing import formats."""

    dependencies = [
        ('location', '0012_reconcile_gar_city_and_district_roles'),
        ('property', '0021_refine_mys_location'),
    ]
    operations = [
        migrations.AddField(
            model_name='legacylocationmapping', name='legacy_name',
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name='legacylocationmapping', name='legacy_code',
            field=models.CharField(blank=True, max_length=10),
        ),
        migrations.AddField(
            model_name='legacylocationmapping', name='legacy_source_identifier',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.RunPython(capture_import_references, migrations.RunPython.noop),
    ]
