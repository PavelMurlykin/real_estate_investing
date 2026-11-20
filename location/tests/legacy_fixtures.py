"""Build public geography fixtures without restoring removed Django models."""

from contextlib import contextmanager
from dataclasses import dataclass

from django.db import connection, transaction
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

from location.catalog_service import lock_location_catalog
from location.compatibility import refresh_legacy_mapping, register_legacy_mapping
from location.legacy_catalog import legacy_catalog, reserve_legacy_ids
from location.models import LocationCompatibilityEntry


@dataclass
class LegacyGeography:
    """Use the original ID and labels from a stored compatibility entry."""

    entry: LocationCompatibilityEntry

    @property
    def pk(self):
        """Identify the public entry within its namespace."""
        return self.entry.legacy_id

    id = pk

    @property
    def name(self):
        """Expose the existing public name."""
        return self.entry.legacy_name

    @property
    def code(self):
        """Expose the retained subject code."""
        return self.entry.legacy_code

    @property
    def source_identifier(self):
        """Serialize the original source identity to fixture adapters."""
        return self.entry.legacy_source_identifier

    @property
    def is_active(self):
        """Expose the status from the public catalog."""
        return self.entry.legacy_is_active

    @property
    def created_at(self):
        """Expose the original creation time used by the old API."""
        return self.entry.legacy_created_at

    @property
    def region_id(self):
        """Return the original regional parent."""
        return self.entry.legacy_region_id

    @property
    def region(self):
        """Load the original regional parent when a fixture needs it."""
        return legacy_fixture('region', self.region_id)

    @property
    def city_id(self):
        """Return the original city parent."""
        return self.entry.legacy_city_id

    @property
    def city(self):
        """Load the original city parent when a fixture needs it."""
        return legacy_city_for(self.city_id)

    def refresh_from_db(self):
        """Refresh a fixture after a real public request."""
        self.entry.refresh_from_db()


def legacy_fixture(model_name, identifier):
    """Read a public identity without using the removed mirror tables."""
    return LegacyGeography(LocationCompatibilityEntry.objects.get(model_name=model_name, legacy_id=identifier))


@transaction.atomic
def create_legacy_fixture(model_name, *, name, code='', region=None, city=None, is_active=True,
                          source_identifier=None, pk=None, location=None):
    """Seed a registry entry and its canonical binding with stable public ancestry."""
    lock_location_catalog()
    identifier = pk if pk is not None else next(iter(reserve_legacy_ids(model_name, 1)))
    timestamp = timezone.now()
    reference = {
        'legacy_name': name, 'legacy_code': code, 'legacy_is_active': is_active,
        'legacy_source_identifier': source_identifier or '',
        'legacy_created_at': timestamp, 'legacy_updated_at': timestamp,
    }
    parent = city or region
    if city:
        reference.update(legacy_city_id=city.pk, legacy_region_id=city.region_id)
    elif region:
        reference['legacy_region_id'] = region.pk
    if location is None:
        entry = register_legacy_mapping(model_name, identifier, reference, parent=parent.entry if parent else None)
    else:
        entry = LocationCompatibilityEntry.objects.create(
            model_name=model_name, legacy_id=identifier, location=location, **reference,
        )
    return LegacyGeography(entry)


def get_or_create_legacy_fixture(model_name, defaults=None, **values):
    """Seed repeated fixture catalogs without altering their public IDs."""
    scope = {}
    for field, value in values.items():
        if field in ('region', 'city'):
            scope[f'legacy_{field}_id'] = value.pk
        else:
            scope[f'legacy_{field}'] = value
    entry = legacy_catalog(model_name).filter(**scope).first()
    if entry:
        return LegacyGeography(entry), False
    return create_legacy_fixture(model_name, **((defaults or {}) | values)), True


def update_legacy_fixture(fixture, **values):
    """Change public labels independently of the canonical territory."""
    refresh_legacy_mapping(fixture.entry, {f'legacy_{field}': value for field, value in values.items()})


def canonical_legacy_location(fixture):
    """Return the stored canonical territory of a historical identity fixture."""
    return fixture.entry.location


def registered_legacy_id(fixture):
    """Return the ID used by compatibility fields on current models."""
    return fixture.pk


def legacy_district_for(complex_object):
    """Read a complex's preserved district independently of its territory."""
    return legacy_fixture('district', complex_object.district_id)


def legacy_city_for(identifier):
    """Read a retained city without restoring the removed relationship."""
    return legacy_fixture('city', identifier)


@contextmanager
def historical_geography_schema():
    """Recreate mirrors temporarily for tests of historical migration code."""
    executor = MigrationExecutor(connection)
    latest = executor.loader.graph.leaf_nodes()
    previous = [('location', '0018_cut_over_legacy_geography')]
    executor.migrate(previous)
    try:
        yield executor.loader.project_state(previous).apps
    finally:
        MigrationExecutor(connection).migrate(latest)
