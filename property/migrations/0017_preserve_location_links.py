"""Backfill canonical locations while retaining every legacy primary key."""

from django.db import migrations

from location.migration_support import backfill_locations


def forwards(apps, schema_editor):
    """Use historical models to retain complexes, apartments and metro access."""
    backfill_locations(apps, schema_editor.connection.alias)


class Migration(migrations.Migration):
    """Populate the compatibility layer without destructive data operations."""

    dependencies = [
        ('property', '0016_realestatecomplexlocation_and_more'),
        ('location', '0009_locationtype_locationimportjob_kind_and_more'),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
