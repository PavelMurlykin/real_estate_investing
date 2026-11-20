"""Keep metro city IDs in place while removing the foreign key to City."""

from django.db import migrations, models


class Migration(migrations.Migration):
    """Keep the original city_id column and its historical uniqueness rule."""

    dependencies = [('location', '0016_legacy_catalog_metadata')]
    operations = [
        migrations.RemoveConstraint(model_name='metroline', name='unique_metro_line_line_city'),
        migrations.AlterField(
            model_name='metroline', name='city',
            field=models.PositiveBigIntegerField(
                blank=True, db_column='city_id', db_index=True, editable=False, null=True,
                verbose_name='Прежний ID города',
            ),
        ),
        migrations.RenameField(model_name='metroline', old_name='city', new_name='legacy_city_id'),
        migrations.AddConstraint(
            model_name='metroline',
            constraint=models.UniqueConstraint(fields=('line', 'legacy_city_id'), name='unique_metro_line_line_city'),
        ),
    ]
