"""Add canonical customer references without modifying original profile fields."""


def backfill_customer_locations(registry, database='default'):
    """Backfill exact mappings in batches and preserve each original finance region."""
    customer_model = registry.get_model('customer', 'Customer')
    mapping_model = registry.get_model('location', 'LegacyLocationMapping')
    location_model = registry.get_model('location', 'Location')
    city_model = registry.get_model('location', 'City')
    mappings = {(name, identifier): territory for name, identifier, territory in mapping_model.objects.using(database).filter(
        model_name__in=['city', 'district'],
    ).values_list('model_name', 'legacy_id', 'location_id')}
    regions = {identifier: (identifier if category == 'region' else region) for identifier, region, category in location_model.objects.using(database).filter(
        pk__in=set(mappings.values()),
    ).values_list('pk', 'region_id', 'location_type__category')}
    locality_ids = set(location_model.objects.using(database).filter(
        pk__in=set(mappings.values()), location_type__category='locality',
    ).values_list('pk', flat=True)) | set(location_model.objects.using(database).filter(
        pk__in=set(mappings.values()), location_type__category='region',
        location_type__abbreviation__in=['г', 'г.', 'г.ф.з.'],
    ).values_list('pk', flat=True))
    mappings = {key: value for key, value in mappings.items()
                if key[0] != 'city' or (value in locality_ids and regions.get(value))}
    financial_regions = dict(city_model.objects.using(database).values_list('pk', 'region_id'))
    fields = ['residence_locality', 'residence_uses_canonical_location', 'desired_region_location',
              'desired_district_location', 'desired_locality', 'purchase_uses_canonical_locations', 'desired_financial_region']
    pending = []
    for customer in customer_model.objects.using(database).order_by('pk').iterator(chunk_size=1000):
        if not customer.residence_uses_canonical_location:
            customer.residence_locality_id = mappings.get(('city', customer.residence_city_id))
            customer.residence_uses_canonical_location = customer.residence_city_id is None or customer.residence_locality_id is not None
        if not customer.purchase_uses_canonical_locations:
            customer.desired_locality_id = mappings.get(('city', customer.desired_city_id))
            customer.desired_district_location_id = mappings.get(('district', customer.desired_district_id))
            customer.desired_region_location_id = regions.get(customer.desired_locality_id or customer.desired_district_location_id)
            customer.desired_financial_region_id = financial_regions.get(customer.desired_city_id)
            customer.purchase_uses_canonical_locations = (
                (customer.desired_city_id is None or customer.desired_locality_id is not None)
                and (customer.desired_district_id is None or customer.desired_district_location_id is not None)
                and (not (customer.desired_city_id or customer.desired_district_id) or customer.desired_region_location_id is not None)
                and (not (customer.desired_locality_id and customer.desired_district_location_id)
                     or regions.get(customer.desired_locality_id) == regions.get(customer.desired_district_location_id))
            )
        pending.append(customer)
        if len(pending) == 1000:
            customer_model.objects.using(database).bulk_update(pending, fields, batch_size=1000)
            pending = []
    if pending:
        customer_model.objects.using(database).bulk_update(pending, fields, batch_size=1000)
