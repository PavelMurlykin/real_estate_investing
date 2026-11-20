"""Retain former geography IDs in the existing columns without foreign keys."""

from django.db import migrations, models

from location.migration_support import ensure_referenced_geography


def repair_legacy_aliases(apps, schema_editor):
    """Retain aliases used by complexes that still carry an old district ID."""
    database = schema_editor.connection.alias
    records = apps.get_model('property', 'RealEstateComplex').objects.using(database)
    ensure_referenced_geography(apps, database, records, (('district_id', 'district'),))


class Migration(migrations.Migration):
    """Detach the geographic snapshots without modifying their values."""

    dependencies = [('property', '0023_detach_developer_region')]
    operations = [
        migrations.RunPython(repair_legacy_aliases, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='realestatecomplex', name='district',
            field=models.PositiveBigIntegerField(
                blank=True, db_column='district_id', db_index=True, editable=False, null=True,
                verbose_name='Прежний ID района',
            ),
        ),
        migrations.RenameField(model_name='realestatecomplex', old_name='district', new_name='district_id'),
        migrations.AlterField(
            model_name='realestatecomplex', name='district_id',
            field=models.PositiveBigIntegerField(
                blank=True, db_index=True, editable=False, null=True, verbose_name='Прежний ID района',
            ),
        ),
    ]
