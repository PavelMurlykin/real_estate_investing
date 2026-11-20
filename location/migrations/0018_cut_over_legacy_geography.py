"""Keep public identities and finish the old national queue before runtime cutover."""

from django.db import migrations
from django.db.models import Max

from location.catalog_service import lock_location_catalog
from location.migration_support import backfill_locations


NAMESPACES = ('region', 'city', 'district')
RETIRED_MESSAGE = 'Прежний общероссийский импорт закрыт. Контрольная точка сохранена. Запустите импорт ГАР.'


def prepare_registry(apps, schema_editor):
    """Capture committed partial imports and reserve all issued public IDs."""
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [77391042])
    database = schema_editor.connection.alias
    lock_location_catalog(database)
    backfill_locations(apps, database, geography_only=True, prefer_registry=True)
    mapping = apps.get_model('location', 'LegacyLocationMapping')
    with schema_editor.connection.cursor() as cursor:
        for namespace in NAMESPACES:
            sequence = f'location_legacy_{namespace}_id_seq'
            cursor.execute(
                'SELECT pg_sequence_last_value(pg_get_serial_sequence(%s, %s)::regclass)',
                [namespace, 'id'],
            )
            old_highest, = cursor.fetchone()
            registry_highest = mapping.objects.using(database).filter(model_name=namespace).aggregate(
                highest=Max('legacy_id'),
            )['highest']
            next_identifier = max(old_highest or 0, registry_highest or 0) + 1
            cursor.execute('SELECT setval(%s::regclass, %s, false)', [sequence, next_identifier])
    jobs = apps.get_model('location', 'LocationImportJob').objects.using(database)
    jobs.exclude(kind='gar').filter(status__in=['queued', 'running']).update(
        status='failed', error_message=RETIRED_MESSAGE,
    )


class Migration(migrations.Migration):
    """Stop depending on identity sequences attached to the old tables."""

    dependencies = [
        ('bank', '0019_detach_mortgage_limit_region'),
        ('customer', '0009_detach_legacy_geography'),
        ('location', '0017_detach_metro_line_city'),
        ('property', '0024_detach_complex_district'),
    ]
    operations = [
        migrations.RunSQL(
            sql=[f'CREATE SEQUENCE location_legacy_{namespace}_id_seq AS bigint' for namespace in NAMESPACES],
            reverse_sql=[f'DROP SEQUENCE location_legacy_{namespace}_id_seq' for namespace in NAMESPACES],
        ),
        migrations.RunPython(prepare_registry, migrations.RunPython.noop),
    ]
