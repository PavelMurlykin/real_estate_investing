"""Build snapshots from the old catalog while exercising its compatibility API."""

from location.compatibility import canonical_legacy_location
from location.models import City, District


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
