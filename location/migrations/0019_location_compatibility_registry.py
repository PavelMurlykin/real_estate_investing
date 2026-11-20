"""Give the persistent compatibility registry a permanent model name."""

from django.db import migrations


class Migration(migrations.Migration):
    """Keep the existing PostgreSQL relation and all its rows."""

    dependencies = [('location', '0018_cut_over_legacy_geography')]
    operations = [
        migrations.AlterModelTable(name='legacylocationmapping', table='location_legacylocationmapping'),
        migrations.RenameModel(old_name='LegacyLocationMapping', new_name='LocationCompatibilityEntry'),
    ]
