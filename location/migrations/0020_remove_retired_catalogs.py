"""Drop the detached geography tables after checking data and incoming keys."""

from django.core.management.color import no_style
from django.db import migrations
from django.utils import timezone

from location.catalog_service import lock_location_catalog


RETIRED_MODELS = ('Region', 'City', 'District')


def verify_retired_catalogs(apps, schema_editor):
    """Require preserved identities, no external FKs and empty municipal tables."""
    database = schema_editor.connection.alias
    lock_location_catalog(database)
    municipality = apps.get_model('location', 'Municipality')
    memberships = municipality._meta.get_field('locations').remote_field.through
    geography = [apps.get_model('location', name) for name in RETIRED_MODELS]
    tables = [model._meta.db_table for model in (*geography, municipality, memberships)]
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            'LOCK TABLE ' + ', '.join(schema_editor.quote_name(table) for table in tables)
            + ' IN ACCESS EXCLUSIVE MODE',
        )
        cursor.execute(
            """
            SELECT conrelid::regclass::text, conname
            FROM pg_constraint
            WHERE contype = 'f'
              AND confrelid IN (SELECT to_regclass(table_name) FROM unnest(%s::text[]) AS table_name)
              AND conrelid NOT IN (SELECT to_regclass(table_name) FROM unnest(%s::text[]) AS table_name)
            """,
            [tables, tables],
        )
        if cursor.fetchone():
            raise RuntimeError('Старые справочники ещё имеют внешние ссылки. Удаление остановлено.')
    if municipality.objects.using(database).exists() or memberships.objects.using(database).exists():
        raise RuntimeError('Есть данные муниципальных образований. Перед удалением согласуйте их перенос.')
    registry = apps.get_model('location', 'LocationCompatibilityEntry').objects.using(database)
    for model in geography:
        aliases = registry.filter(model_name=model._meta.model_name).values('legacy_id')
        if model.objects.using(database).exclude(pk__in=aliases).exists():
            raise RuntimeError(f'Для старого справочника {model._meta.db_table} есть ID без соответствия.')


def rebuild_legacy_mirrors(apps, schema_editor):
    """Rebuild a prior schema from current aliases. Exact restore uses a backup."""
    connection = schema_editor.connection
    database = connection.alias
    lock_location_catalog(database)
    registry = apps.get_model('location', 'LocationCompatibilityEntry').objects.using(database)
    restored = {}
    models = [apps.get_model('location', name) for name in RETIRED_MODELS]
    timestamp = timezone.now()
    for model in models:
        namespace = model._meta.model_name
        references = registry.filter(model_name=namespace).exclude(legacy_name='').order_by('legacy_id')
        rows, dates = [], {}
        for alias in references.iterator(chunk_size=500):
            values = {
                'pk': alias.legacy_id, 'name': alias.legacy_name, 'is_active': alias.legacy_is_active,
                'source_identifier': alias.legacy_source_identifier or None,
            }
            if namespace == 'region':
                values['code'] = alias.legacy_code
            elif namespace == 'city':
                if alias.legacy_region_id not in restored['region']:
                    continue
                values['region_id'] = alias.legacy_region_id
            else:
                if alias.legacy_city_id not in restored['city']:
                    continue
                values['city_id'] = alias.legacy_city_id
            rows.append(model(**values))
            dates[alias.legacy_id] = (alias.legacy_created_at or timestamp, alias.legacy_updated_at or timestamp)
        records = model.objects.using(database)
        records.bulk_create(rows, batch_size=500)
        for row in rows:
            row.created_at, row.updated_at = dates[row.pk]
        records.bulk_update(rows, ['created_at', 'updated_at'], batch_size=500)
        restored[namespace] = dates.keys()
    with connection.cursor() as cursor:
        for statement in connection.ops.sequence_reset_sql(no_style(), models):
            cursor.execute(statement)


class Migration(migrations.Migration):
    """Remove obsolete dictionaries and the unused municipal scaffold."""

    dependencies = [('location', '0019_location_compatibility_registry')]
    operations = [
        migrations.RunPython(verify_retired_catalogs, rebuild_legacy_mirrors),
        migrations.DeleteModel(name='District'),
        migrations.DeleteModel(name='City'),
        migrations.DeleteModel(name='Region'),
        migrations.DeleteModel(name='Municipality'),
    ]
