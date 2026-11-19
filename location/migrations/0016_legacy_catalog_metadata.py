"""Preserve the old public catalog's status and dates in the location mapping."""

from django.db import migrations, models

from location.catalog_service import lock_location_catalog
from location.migration_support import backfill_locations


def capture_catalog_metadata(apps, schema_editor):
    """Backfill catalog projections without rewriting object relations."""
    database = schema_editor.connection.alias
    lock_location_catalog(database)
    backfill_locations(apps, database, geography_only=True)


class Migration(migrations.Migration):
    """Keep legacy API metadata separate from authoritative GAR attributes."""

    dependencies = [('location', '0015_metro_legacy_geography')]
    operations = [
        migrations.AddField(model_name='legacylocationmapping', name='legacy_is_active',
                            field=models.BooleanField(default=True)),
        migrations.AddField(model_name='legacylocationmapping', name='legacy_created_at',
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.AddField(model_name='legacylocationmapping', name='legacy_updated_at',
                            field=models.DateTimeField(blank=True, null=True)),
        migrations.RunPython(capture_catalog_metadata, migrations.RunPython.noop),
    ]
