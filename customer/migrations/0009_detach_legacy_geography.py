"""Retain former geography IDs in the existing columns without foreign keys."""

from django.db import migrations, models

from location.migration_support import ensure_referenced_geography


def repair_legacy_aliases(apps, schema_editor):
    """Retain metadata for all four kinds of historical profile references."""
    database = schema_editor.connection.alias
    records = apps.get_model('customer', 'Customer').objects.using(database)
    ensure_referenced_geography(apps, database, records, (
        ('residence_city_id', 'city'),
        ('desired_city_id', 'city'),
        ('desired_district_id', 'district'),
        ('desired_financial_region_id', 'region'),
    ))


class Migration(migrations.Migration):
    """Detach the geographic snapshots without modifying their values."""

    dependencies = [('customer', '0008_complete_financial_regions'), ('location', '0017_detach_metro_line_city')]
    operations = [
        migrations.RunPython(repair_legacy_aliases, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='customer', name='residence_city',
            field=models.PositiveBigIntegerField(
                blank=True, db_column='residence_city_id', db_index=True, editable=False, null=True,
                verbose_name='Прежний ID города проживания',
            ),
        ),
        migrations.RenameField(model_name='customer', old_name='residence_city', new_name='residence_city_id'),
        migrations.AlterField(
            model_name='customer', name='residence_city_id',
            field=models.PositiveBigIntegerField(
                blank=True, db_index=True, editable=False, null=True, verbose_name='Прежний ID города проживания',
            ),
        ),
        migrations.AlterField(
            model_name='customer', name='desired_city',
            field=models.PositiveBigIntegerField(
                blank=True, db_column='desired_city_id', db_index=True, editable=False, null=True,
                verbose_name='Прежний ID города покупки',
            ),
        ),
        migrations.RenameField(model_name='customer', old_name='desired_city', new_name='desired_city_id'),
        migrations.AlterField(
            model_name='customer', name='desired_city_id',
            field=models.PositiveBigIntegerField(
                blank=True, db_index=True, editable=False, null=True, verbose_name='Прежний ID города покупки',
            ),
        ),
        migrations.AlterField(
            model_name='customer', name='desired_district',
            field=models.PositiveBigIntegerField(
                blank=True, db_column='desired_district_id', db_index=True, editable=False, null=True,
                verbose_name='Прежний ID района покупки',
            ),
        ),
        migrations.RenameField(model_name='customer', old_name='desired_district', new_name='desired_district_id'),
        migrations.AlterField(
            model_name='customer', name='desired_district_id',
            field=models.PositiveBigIntegerField(
                blank=True, db_index=True, editable=False, null=True, verbose_name='Прежний ID района покупки',
            ),
        ),
        migrations.AlterField(
            model_name='customer', name='desired_financial_region',
            field=models.PositiveBigIntegerField(
                blank=True, db_column='desired_financial_region_id', db_index=True, editable=False, null=True,
                verbose_name='Прежний ID региона ипотечных лимитов',
            ),
        ),
        migrations.RenameField(model_name='customer', old_name='desired_financial_region', new_name='desired_financial_region_id'),
        migrations.AlterField(
            model_name='customer', name='desired_financial_region_id',
            field=models.PositiveBigIntegerField(
                blank=True, db_index=True, editable=False, null=True, verbose_name='Прежний ID региона ипотечных лимитов',
            ),
        ),
    ]
