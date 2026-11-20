"""Retain the original region ID without a foreign key for developer links."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    """Reuse the original column and keep the association constraints."""

    dependencies = [('property', '0022_complete_developer_regions'), ('location', '0017_detach_metro_line_city')]
    operations = [
        migrations.RemoveField(model_name='developer', name='regions'),
        migrations.RemoveConstraint(model_name='developerregion', name='developer_region_has_territory'),
        migrations.RemoveConstraint(model_name='developerregion', name='unique_canonical_only_developer_region'),
        migrations.RemoveConstraint(model_name='developerregion', name='unique_developer_region'),
        migrations.AlterField(
            model_name='developerregion', name='region',
            field=models.PositiveBigIntegerField(
                blank=True, db_column='region_id', db_index=True, editable=False, null=True,
                verbose_name='Прежний ID региона',
            ),
        ),
        migrations.RenameField(model_name='developerregion', old_name='region', new_name='region_id'),
        migrations.AlterField(
            model_name='developerregion', name='region_id',
            field=models.PositiveBigIntegerField(
                blank=True, db_index=True, editable=False, null=True, verbose_name='Прежний ID региона',
            ),
        ),
        migrations.AlterField(
            model_name='developerregion', name='location',
            field=models.ForeignKey(
                blank=True, limit_choices_to={'location_type__category': 'region'}, null=True,
                on_delete=django.db.models.deletion.PROTECT, related_name='developer_region_links',
                to='location.location', verbose_name='Регион Location',
            ),
        ),
        migrations.AlterModelOptions(name='developerregion', options={
            'ordering': ['developer__name', 'location__name', 'region_id', 'pk'],
            'verbose_name': 'Регион застройщика', 'verbose_name_plural': 'Регионы застройщиков',
        }),
        migrations.AddConstraint(model_name='developerregion', constraint=models.CheckConstraint(
            condition=models.Q(region_id__isnull=False) | models.Q(location__isnull=False),
            name='developer_region_has_territory',
        )),
        migrations.AddConstraint(model_name='developerregion', constraint=models.UniqueConstraint(
            fields=('developer', 'location'), condition=models.Q(region_id__isnull=True),
            name='unique_canonical_only_developer_region',
        )),
        migrations.AddConstraint(model_name='developerregion', constraint=models.UniqueConstraint(
            fields=('developer', 'region_id'), name='unique_developer_region',
        )),
    ]
