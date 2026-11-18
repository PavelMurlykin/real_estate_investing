"""Validate customer territories and preserve legacy financial region identities."""

from django.core.exceptions import ValidationError

from location.models import LegacyLocationMapping, Location, LocationClosure
from property.location_context import locality_filter

RESIDENCE_FIELDS = ('residence_locality',)
PURCHASE_FIELDS = ('desired_region_location', 'desired_district_location', 'desired_locality')
CUSTOMER_LOCATION_FIELDS = RESIDENCE_FIELDS + PURCHASE_FIELDS + (
    'residence_uses_canonical_location', 'purchase_uses_canonical_locations', 'desired_financial_region',
    'desired_financial_region_location',
)
CUSTOMER_LOCATION_RELATED = (
    'residence_locality', 'desired_region_location', 'desired_district_location',
    'desired_locality', 'desired_financial_region', 'desired_financial_region_location',
    'residence_locality__location_type', 'residence_locality__parent', 'residence_locality__region',
    'desired_locality__location_type', 'desired_locality__parent', 'desired_locality__region',
)


def _mapped_territory(model_name, identifier):
    """Resolve exact compatibility identities without matching names."""
    if identifier is None:
        return None
    return Location.objects.filter(
        legacy_mappings__model_name=model_name, legacy_mappings__legacy_id=identifier,
    ).select_related('location_type', 'region').first()


def _region_of(territory):
    """Resolve a federal city's regional role without duplicating its identity."""
    return territory if territory.location_type.category == 'region' else territory.region


def _validate_territory(customer, name, category, previous):
    """Check roles and reject newly selected inactive territories."""
    territory = getattr(customer, name)
    if not territory:
        return
    valid_role = (Location.objects.filter(locality_filter(), pk=territory.pk).exists()
                  if category == 'locality' else territory.location_type.category == category)
    if not valid_role:
        raise ValidationError({name: 'Выберите территорию соответствующего уровня.'})
    if not territory.is_active and (previous is None or getattr(previous, f'{name}_id') != territory.pk):
        raise ValidationError({name: 'Выберите действующую территорию.'})


def _validate_purchase(customer, previous):
    """Require scopes to intersect despite either district/locality hierarchy order."""
    for name, category in zip(PURCHASE_FIELDS, ['region', 'district', 'locality']):
        _validate_territory(customer, name, category, previous)
    region = customer.desired_region_location
    for name in ['desired_district_location', 'desired_locality']:
        territory = getattr(customer, name)
        if territory and _region_of(territory) is None:
            raise ValidationError({name: 'Регион территории требует уточнения.'})
        if territory and region and _region_of(territory).pk != region.pk:
            raise ValidationError({name: 'Территория относится к другому региону.'})
    district, locality = customer.desired_district_location, customer.desired_locality
    if district and locality and not LocationClosure.objects.filter(
        ancestor_id=district.pk, descendant_id=locality.pk,
    ).exists() and not LocationClosure.objects.filter(ancestor_id=locality.pk, descendant_id=district.pk).exists():
        raise ValidationError({'desired_locality': 'Населённый пункт и район не связаны административной иерархией.'})


def validate_customer_locations(customer):
    """Enforce canonical roles and hierarchy during model validation."""
    if customer.residence_uses_canonical_location:
        _validate_territory(customer, 'residence_locality', 'locality', customer)
    if customer.purchase_uses_canonical_locations:
        _validate_purchase(customer, customer)


def prepare_customer_locations(customer, changed_fields, previous=None):
    """Apply only explicitly submitted location changes, retaining legacy snapshots."""
    changed = set(changed_fields)
    if changed.intersection(RESIDENCE_FIELDS):
        if 'residence_city' in changed:
            raise ValidationError({'residence_locality': 'Передайте новый населённый пункт отдельно от старого города.'})
        _validate_territory(customer, 'residence_locality', 'locality', previous)
        customer.residence_uses_canonical_location = True
    elif 'residence_city' in changed:
        customer.residence_locality = _mapped_territory('city', customer.residence_city_id)
        customer.residence_uses_canonical_location = customer.residence_city_id is None or customer.residence_locality is not None

    if changed.intersection(PURCHASE_FIELDS):
        if changed.intersection({'desired_city', 'desired_district'}):
            raise ValidationError({'desired_locality': 'Передайте новые территории отдельно от старых города и района.'})
        target = customer.desired_locality or customer.desired_district_location
        if target and not customer.desired_region_location:
            customer.desired_region_location = _region_of(target)
        _validate_purchase(customer, previous)
        unchanged = previous is not None and previous.purchase_uses_canonical_locations and all(
            getattr(previous, f'{name}_id') == getattr(customer, f'{name}_id') for name in PURCHASE_FIELDS
        )
        if not unchanged:
            region = customer.desired_region_location
            customer.desired_financial_region_location = region
            candidates = list(LegacyLocationMapping.objects.filter(
                model_name='region', location=region,
            ).values_list('legacy_id', flat=True)) if region else []
            previous_region = previous.get_desired_region() if previous else None
            if previous_region and previous_region.pk in candidates:
                customer.desired_financial_region = previous_region
            elif len(candidates) == 1:
                customer.desired_financial_region_id = candidates[0]
            else:
                customer.desired_financial_region = None
        customer.purchase_uses_canonical_locations = True
    elif changed.intersection({'desired_city', 'desired_district'}):
        if customer.desired_city_id and customer.desired_district_id and customer.desired_district.city_id != customer.desired_city_id:
            raise ValidationError({'desired_district': 'Район должен относиться к выбранному городу.'})
        customer.desired_locality = _mapped_territory('city', customer.desired_city_id)
        customer.desired_district_location = _mapped_territory('district', customer.desired_district_id)
        target = customer.desired_locality or customer.desired_district_location
        customer.desired_region_location = _region_of(target) if target else None
        customer.desired_financial_region = customer.desired_city.region if customer.desired_city_id else None
        customer.desired_financial_region_location = _mapped_territory('region', customer.desired_financial_region_id)
        customer.purchase_uses_canonical_locations = (
            (customer.desired_city_id is None or customer.desired_locality is not None)
            and (customer.desired_district_id is None or customer.desired_district_location is not None)
        )
