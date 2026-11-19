"""Project the public legacy dictionaries from their retained Location identities."""

from dataclasses import dataclass

from django.db.models import Count, IntegerField, OuterRef, Subquery, Value
from django.db.models.functions import Coalesce

from .models import City, District, LegacyLocationMapping, Region


LEGACY_GEOGRAPHY_MODELS = {'regions': Region, 'cities': City, 'districts': District}


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
    return LegacyLocationMapping.objects.filter(model_name=model_name).exclude(legacy_name='')


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
            + _usage_count(MetroLine.objects.all(), 'city_id')
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
