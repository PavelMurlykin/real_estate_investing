"""Project the public legacy dictionaries from their retained Location identities."""

from dataclasses import dataclass

from django.core.cache import cache
from django.db import connection, transaction
from django.db.models import Count, IntegerField, Max, OuterRef, Subquery, Value
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Coalesce
from django.utils import timezone

from .compatibility import refresh_legacy_mapping, register_legacy_mapping
from .catalog_service import lock_location_catalog
from .models import LocationCompatibilityEntry


LEGACY_GEOGRAPHY_KEYS = {'regions': 'region', 'cities': 'city', 'districts': 'district'}
LEGACY_IDENTIFIER_SEQUENCES = {
    namespace: f'location_legacy_{namespace}_id_seq' for namespace in LEGACY_GEOGRAPHY_KEYS.values()
}


@dataclass(frozen=True)
class LegacyImportScope:
    """Pass a retained identity to the existing import without loading its old row."""

    pk: int
    name: str
    code: str
    source_identifier: str

    @classmethod
    def from_mapping(cls, mapping):
        """Expose the old identity and its source selectors."""
        return cls(mapping.legacy_id, mapping.legacy_name, mapping.legacy_code, mapping.legacy_source_identifier)


def legacy_catalog(model_name):
    """Exclude deleted aliases that still resolve old links to Location."""
    return LocationCompatibilityEntry.objects.filter(model_name=model_name).exclude(legacy_name='')


def legacy_choices(model_name, *, region_id=None, city_id=None, active_only=False):
    """Keep the exact old cascade even when GAR places have a different parent."""
    choices = legacy_catalog(model_name)
    if region_id is not None:
        choices = choices.filter(legacy_region_id=region_id)
    if city_id is not None:
        choices = choices.filter(legacy_city_id=city_id)
    if active_only:
        choices = choices.filter(legacy_is_active=True)
    return choices.order_by('legacy_name', 'legacy_id')


def unique_legacy_region(location_id):
    """Return an old region ID and label only when a subject has one visible alias."""
    aliases = list(legacy_catalog('region').filter(location_id=location_id)
                   .values_list('legacy_id', 'legacy_name')[:2])
    return aliases[0] if len(aliases) == 1 else (None, '')


def invalidate_legacy_options():
    """Refresh cached native selectors after the registry change commits."""
    from mortgage.apps import FORM_DATA_CACHE_KEYS as mortgage_keys
    from property.apps import FORM_DATA_CACHE_KEYS as property_keys

    transaction.on_commit(lambda: cache.delete_many((*mortgage_keys, *property_keys)))


def reserve_legacy_ids(model_name, count):
    """Allocate a batch above all retained IDs while holding the catalog lock."""
    if count == 0:
        return []
    sequence = LEGACY_IDENTIFIER_SEQUENCES[model_name]
    highest_alias = LocationCompatibilityEntry.objects.filter(model_name=model_name).aggregate(
        highest=Max('legacy_id'),
    )['highest'] or 0
    with connection.cursor() as cursor:
        cursor.execute('SELECT nextval(%s::regclass)', [sequence])
        identifier, = cursor.fetchone()
        first = max(identifier, highest_alias + 1)
        last = first + count - 1
        if last != identifier:
            cursor.execute('SELECT setval(%s::regclass, %s)', [sequence, last])
    return range(first, last + 1)


@transaction.atomic
def save_legacy_catalog_entry(model_name, values, *, mapping=None):
    """Write a compatibility ID and bind it to Location without mirroring a row."""
    lock_location_catalog()
    reference = {f'legacy_{field}': value for field, value in values.items()}
    parent = None
    if 'region_id' in values:
        parent = legacy_catalog('region').select_related('location').get(legacy_id=values['region_id'])
    elif 'city_id' in values:
        parent = legacy_catalog('city').select_related('location').get(legacy_id=values['city_id'])
        reference['legacy_region_id'] = parent.legacy_region_id

    timestamp = timezone.now()
    reference['legacy_updated_at'] = timestamp
    if mapping is None:
        identifier, = reserve_legacy_ids(model_name, 1)
        reference['legacy_created_at'] = timestamp
        mapping = register_legacy_mapping(model_name, identifier, reference, parent=parent)
    else:
        refresh_legacy_mapping(mapping, reference)
    invalidate_legacy_options()
    return mapping


def retire_legacy_catalog_entry(mapping):
    """Hide the old entry while retaining its identity and canonical links."""
    from customer.models import Customer

    if mapping.usage_count or (
        mapping.model_name == 'region'
        and Customer.objects.filter(desired_financial_region_id=mapping.legacy_id).exists()
    ):
        raise ProtectedError('Историческая локация используется.', [mapping])
    LocationCompatibilityEntry.objects.filter(pk=mapping.pk).update(
        legacy_name='', legacy_code='', legacy_source_identifier='', legacy_updated_at=timezone.now(),
    )
    invalidate_legacy_options()


def _usage_count(queryset, field, *, distinct_field=None):
    """Count one legacy reference group without joining the retired geography."""
    grouped = queryset.filter(**{field: OuterRef('legacy_id')}).order_by().values(field)
    total = grouped.annotate(total=Count(distinct_field or 'pk', distinct=distinct_field is not None))
    return Coalesce(Subquery(total.values('total')[:1], output_field=IntegerField()), Value(0))


def legacy_dictionary_entries(model_name):
    """Load the original dates, parents and usage counts for the legacy CRUD API."""
    from bank.models import MortgageProgramRegionalCreditLimit
    from customer.models import Customer
    from property.models import DeveloperRegion, RealEstateComplex

    from .models import MetroLine

    queryset = legacy_catalog(model_name).annotate(
        created_at=Coalesce('legacy_created_at', 'location__created_at'),
        updated_at=Coalesce('legacy_updated_at', 'location__updated_at'),
    )
    if model_name == 'region':
        return queryset.annotate(usage_count=(
            _usage_count(legacy_catalog('city'), 'legacy_region_id')
            + _usage_count(DeveloperRegion.objects.all(), 'region_id', distinct_field='developer_id')
            + _usage_count(DeveloperRegion.objects.all(), 'region_id')
            + _usage_count(MortgageProgramRegionalCreditLimit.objects.all(), 'region_id')
        ))
    regions = legacy_catalog('region').filter(legacy_id=OuterRef('legacy_region_id'))
    queryset = queryset.annotate(region_name=Subquery(regions.values('legacy_name')[:1]))
    if model_name == 'city':
        return queryset.annotate(usage_count=(
            _usage_count(legacy_catalog('district'), 'legacy_city_id')
            + _usage_count(MetroLine.objects.all(), 'legacy_city_id')
            + _usage_count(Customer.objects.all(), 'residence_city_id')
            + _usage_count(Customer.objects.all(), 'desired_city_id')
        ))
    cities = legacy_catalog('city').filter(legacy_id=OuterRef('legacy_city_id'))
    return queryset.annotate(
        city_name=Subquery(cities.values('legacy_name')[:1]),
        usage_count=(
            _usage_count(RealEstateComplex.objects.all(), 'district_id')
            + _usage_count(Customer.objects.all(), 'desired_district_id')
        ),
    )
