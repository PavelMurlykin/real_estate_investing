"""Keep historical limit IDs and labels without joining the old region catalog."""

import django.db.models.deletion
from django.db import migrations, models
from django.db.models import OuterRef, Subquery


def retain_region_names(apps, schema_editor):
    """Copy exact labels before removing the foreign key in place."""
    database = schema_editor.connection.alias
    regions = apps.get_model('location', 'Region').objects.using(database).filter(pk=OuterRef('region_id'))
    limits = apps.get_model('bank', 'MortgageProgramRegionalCreditLimit').objects.using(database)
    limits.exclude(region_id=None).update(legacy_region_name=Subquery(regions.values('name')[:1]))


class Migration(migrations.Migration):
    """Retain the scalar column and both uniqueness rules."""

    dependencies = [('bank', '0018_complete_limit_locations'), ('location', '0017_detach_metro_line_city')]
    operations = [
        migrations.AddField(model_name='mortgageprogramregionalcreditlimit', name='legacy_region_name',
                            field=models.CharField(blank=True, editable=False, max_length=100)),
        migrations.RunPython(retain_region_names, migrations.RunPython.noop),
        migrations.RemoveConstraint(model_name='mortgageprogramregionalcreditlimit', name='mortgage_limit_has_region'),
        migrations.RemoveConstraint(model_name='mortgageprogramregionalcreditlimit', name='unique_mortgage_program_region_credit_limit'),
        migrations.AlterField(
            model_name='mortgageprogramregionalcreditlimit', name='region',
            field=models.PositiveBigIntegerField(
                blank=True, db_column='region_id', db_index=True, editable=False, null=True,
                verbose_name='Прежний ID региона',
            ),
        ),
        migrations.RenameField(model_name='mortgageprogramregionalcreditlimit', old_name='region', new_name='region_id'),
        migrations.AlterField(
            model_name='mortgageprogramregionalcreditlimit', name='region_id',
            field=models.PositiveBigIntegerField(
                blank=True, db_index=True, editable=False, null=True, verbose_name='Прежний ID региона',
            ),
        ),
        migrations.AlterField(
            model_name='mortgageprogramregionalcreditlimit', name='region_location',
            field=models.ForeignKey(
                blank=True, limit_choices_to={'location_type__category': 'region'}, null=True,
                on_delete=django.db.models.deletion.PROTECT, related_name='mortgage_credit_limits',
                to='location.location', verbose_name='Регион',
            ),
        ),
        migrations.AlterModelOptions(name='mortgageprogramregionalcreditlimit', options={
            'ordering': ['mortgage_program__name', 'region_location__name', 'region_id', 'pk'],
            'verbose_name': 'Региональный лимит ипотечной программы',
            'verbose_name_plural': 'Региональные лимиты ипотечных программ',
        }),
        migrations.AddConstraint(model_name='mortgageprogramregionalcreditlimit', constraint=models.CheckConstraint(
            condition=models.Q(region_id__isnull=False) | models.Q(region_location__isnull=False),
            name='mortgage_limit_has_region',
        )),
        migrations.AddConstraint(model_name='mortgageprogramregionalcreditlimit', constraint=models.UniqueConstraint(
            fields=('mortgage_program', 'region_id'), name='unique_mortgage_program_region_credit_limit',
        )),
    ]
