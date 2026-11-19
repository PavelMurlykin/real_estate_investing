"""Attach canonical subjects to regional limits added through older editors."""

from django.db import migrations
from django.db.models import Exists, OuterRef


def complete_limit_locations(apps, schema_editor):
    """Fill unambiguous missing links and retain conflicting limits by legacy ID."""
    database = schema_editor.connection.alias
    mappings = apps.get_model('location', 'LegacyLocationMapping').objects.using(database).filter(model_name='region')
    aliases = mappings.filter(location_id=OuterRef('location_id')).exclude(pk=OuterRef('pk'))
    limits = apps.get_model('bank', 'MortgageProgramRegionalCreditLimit').objects.using(database)
    pending_ids = limits.filter(region_location_id__isnull=True).values('region_id')
    for legacy_id, location_id in mappings.filter(
        ~Exists(aliases), legacy_id__in=pending_ids, location__location_type__category='region',
    ).values_list('legacy_id', 'location_id'):
        existing = limits.filter(mortgage_program_id=OuterRef('mortgage_program_id'), region_location_id=location_id)
        limits.filter(~Exists(existing), region_id=legacy_id, region_location_id__isnull=True).update(
            region_location_id=location_id,
        )


class Migration(migrations.Migration):
    """Reconcile the two region identifiers without replacing the original rows."""

    dependencies = [
        ('bank', '0017_financial_locations'),
        ('location', '0014_legacy_district_ancestry'),
    ]
    operations = [migrations.RunPython(complete_limit_locations, migrations.RunPython.noop)]
