"""Resolve regional limits through Location and explicit compatibility identities."""

from django.db.models import Exists, OuterRef, Prefetch, Subquery, Value
from django.db.models.functions import Coalesce, NullIf

from location.legacy_catalog import legacy_catalog
from location.models import LocationCompatibilityEntry


def limit_region_labels(queryset):
    """Expose legacy names and canonical display names without the old Region join."""
    aliases = legacy_catalog('region').filter(legacy_id=OuterRef('region_id'))
    return queryset.annotate(retained_region_name=Coalesce(
        Subquery(aliases.values('legacy_name')[:1]), NullIf('legacy_region_name', Value('')),
    )).annotate(display_region_name=Coalesce('region_location__name', 'retained_region_name'))


def limit_prefetch(prefix=''):
    """Load limits without the legacy region-name ordering used by the old admin."""
    from .models import MortgageProgramRegionalCreditLimit

    return Prefetch(f'{prefix}regional_credit_limits', queryset=MortgageProgramRegionalCreditLimit.objects.order_by('pk'))


def legacy_limit_locations(limits):
    """Resolve legacy-only limits whose regional identity has a unique mapping."""
    legacy_ids = {limit.region_id for limit in limits if limit.region_id and not limit.region_location_id}
    if not legacy_ids:
        return {}
    mappings = LocationCompatibilityEntry.objects.filter(model_name='region')
    aliases = mappings.filter(location_id=OuterRef('location_id')).exclude(pk=OuterRef('pk'))
    return dict(mappings.filter(
        ~Exists(aliases), legacy_id__in=legacy_ids, location__location_type__category='region',
    ).values_list('legacy_id', 'location_id'))


def active_limit_locations(limits, mappings):
    """Give each effective Location to one active limit, preferring its explicit link."""
    locations = {limit.region_location_id for limit in limits if limit.is_active and limit.region_location_id}
    return {
        limit.pk: limit.region_location_id or (
            mappings.get(limit.region_id) if mappings.get(limit.region_id) not in locations else None
        )
        for limit in limits if limit.is_active
    }
