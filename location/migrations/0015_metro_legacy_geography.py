"""Preserve the original metro geography outside the old parent tables."""

from django.db import migrations, models
from django.db.models import OuterRef, Subquery

from location.catalog_service import lock_location_catalog


def capture_metro_geography(apps, schema_editor):
    """Copy exact labels and IDs without modifying lines, stations or their links."""
    database = schema_editor.connection.alias
    lock_location_catalog(database)
    cities = apps.get_model('location', 'City').objects.using(database)
    mappings = apps.get_model('location', 'LegacyLocationMapping').objects.using(database)
    lines = apps.get_model('location', 'MetroLine').objects.using(database)
    mapped_city = cities.filter(pk=OuterRef('legacy_id'))
    mappings.filter(model_name='city', legacy_id__in=cities.values('pk')).update(
        legacy_region_id=Subquery(mapped_city.values('region_id')[:1]),
    )
    line_city = cities.filter(pk=OuterRef('city_id'))
    lines.filter(city_id__isnull=False, legacy_city_name='').update(
        legacy_city_name=Subquery(line_city.values('name')[:1]),
        legacy_region_id=Subquery(line_city.values('region_id')[:1]),
        legacy_region_name=Subquery(line_city.values('region__name')[:1]),
    )


class Migration(migrations.Migration):
    """Add compatibility metadata to existing metro lines."""

    dependencies = [('location', '0014_legacy_district_ancestry')]
    operations = [
        migrations.AddField(model_name='metroline', name='legacy_city_name',
                            field=models.CharField(blank=True, editable=False, max_length=100)),
        migrations.AddField(model_name='metroline', name='legacy_region_id',
                            field=models.PositiveBigIntegerField(blank=True, editable=False, null=True)),
        migrations.AddField(model_name='metroline', name='legacy_region_name',
                            field=models.CharField(blank=True, editable=False, max_length=100)),
        migrations.RunPython(capture_metro_geography, migrations.RunPython.noop),
    ]
