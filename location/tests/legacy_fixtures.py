"""Build snapshots from the old catalog while exercising its compatibility API."""


from django.db import transaction

from location.catalog_service import lock_location_catalog
from location.compatibility import refresh_legacy_mapping, register_legacy_mapping
from location.migration_support import legacy_catalog_metadata, legacy_import_reference
from location.models import City, District, LegacyLocationMapping


@transaction.atomic
def canonical_legacy_location(row):
    """Resolve one legacy chain and retain the input accepted by older imports."""
    lock_location_catalog()
    return _mapping_for_legacy_row(row).location


def _mapping_for_legacy_row(row):
    """Register the old mirror rows used by a test hierarchy."""
    model_name = row._meta.model_name
    mapping = LegacyLocationMapping.objects.filter(model_name=model_name, legacy_id=row.pk).first()
    reference = legacy_import_reference(row) | legacy_catalog_metadata(row)
    if model_name == 'district':
        reference.update(legacy_city_id=row.city_id, legacy_region_id=row.city.region_id)
    elif model_name == 'city':
        reference['legacy_region_id'] = row.region_id
    if mapping:
        refresh_legacy_mapping(mapping, reference)
        return mapping
    parent = None
    if model_name == 'district':
        parent = _mapping_for_legacy_row(row.city)
    elif model_name == 'city':
        parent = _mapping_for_legacy_row(row.region)
    return register_legacy_mapping(model_name, row.pk, reference, parent=parent)


def registered_legacy_id(entry):
    """Register a historical fixture and return the original public identifier."""
    canonical_legacy_location(entry)
    return entry.pk


def legacy_district_for(complex_object):
    """Retrieve the legacy fixture row independently of current complex storage."""
    return District.objects.select_related('city__region').get(pk=complex_object.district_id)


def legacy_city_for(identifier):
    """Retrieve a fixture city without restoring the removed model relationship."""
    return City.objects.select_related('region').get(pk=identifier)
