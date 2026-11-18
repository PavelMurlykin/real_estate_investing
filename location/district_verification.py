"""Confirm administrative districts where the GAR address extract skips that level."""

from django.apps import apps


ADMINISTRATIVE_REVIEW_VERSION = 'administrative:20261118'

# Parent FIAS UUIDs and original identifiers of the independently verified
# administrative districts. See stage 17 of the location migration audit.
VERIFIED_DISTRICTS = (
    ('39', 'df679694-d505-4dd3-b514-4ba48c8a97d8', (
        'Q1949329',  # Московский район Калининграда
    )),
    ('77', '0c5b2444-70a0-4932-980c-b4dc0d3f02b5', (
        'Q2367564', 'Q1963381', 'Q2367394', 'Q2367649',
    )),
    ('78', 'c2deb16a-0330-4f05-821f-1d09c93331e6', (
        'Q219746', 'Q220622', 'Q270112', 'Q1193156',
        'Q220316', 'Q1142777', 'Q270114',
    )),
)


def verify_legacy_districts(registry=apps, database='default', *, region_id=None, region_code=None):
    """Verify known district identities in place under the exact GAR parent."""
    locations = registry.get_model('location', 'Location').objects.using(database)
    districts = registry.get_model('location', 'District').objects.using(database)
    mappings = registry.get_model('location', 'LegacyLocationMapping').objects.using(database)
    updated = 0
    for subject_code, parent_fias, source_items in VERIFIED_DISTRICTS:
        if region_code is not None and region_code != subject_code:
            continue
        parents = locations.filter(
            identifiers__provider='fias', identifiers__value=parent_fias,
            source_status='verified', location_type__category__in=('region', 'locality'),
        )
        if region_id is not None:
            parents = parents.filter(region_id=region_id)
        parent = parents.only('pk', 'region_id').first()
        if parent is None:
            continue
        old_cities = mappings.filter(model_name='city', location_id=parent.pk).values('legacy_id')
        old_districts = districts.filter(
            city_id__in=old_cities, city__region__code=subject_code,
            source_identifier__in=[f'wikidata/{item}' for item in source_items],
        ).values('pk')
        updated += locations.filter(
            parent_id=parent.pk, region_id=parent.region_id, location_type__category='district',
            legacy_mappings__model_name='district', legacy_mappings__legacy_id__in=old_districts,
            needs_review=True, source_status='unverified',
        ).update(source_status='verified', source_version=ADMINISTRATIVE_REVIEW_VERSION, needs_review=False)
    return updated
