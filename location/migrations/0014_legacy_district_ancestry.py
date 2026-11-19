"""Preserve the old district hierarchy used by API compatibility fields."""

from django.db import migrations, models

from location.catalog_service import lock_location_catalog


def capture_legacy_district_ancestry(apps, schema_editor):
    """Copy old IDs into the mapping without rewriting any property links."""
    database = schema_editor.connection.alias
    lock_location_catalog(database)
    district = apps.get_model('location', 'District')
    mapping = apps.get_model('location', 'LegacyLocationMapping')
    ancestry = {
        identifier: (city_id, region_id)
        for identifier, city_id, region_id in district.objects.using(database).values_list(
            'pk', 'city_id', 'city__region_id',
        )
    }
    references = mapping.objects.using(database).filter(model_name='district', legacy_id__in=ancestry)
    for reference in references:
        reference.legacy_city_id, reference.legacy_region_id = ancestry[reference.legacy_id]
    references.bulk_update(references, ['legacy_city_id', 'legacy_region_id'], batch_size=1000)


class Migration(migrations.Migration):
    """Keep the legacy API independent of the current geographic hierarchy."""

    dependencies = [('location', '0013_legacy_import_references')]
    operations = [
        migrations.AddField(
            model_name='legacylocationmapping', name='legacy_city_id',
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='legacylocationmapping', name='legacy_region_id',
            field=models.PositiveBigIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(capture_legacy_district_ancestry, migrations.RunPython.noop),
    ]
