"""Verify customer geography migration, ownership and financial compatibility."""

from decimal import Decimal

import pytest
from django.apps import apps
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import Client
from django.urls import reverse

from api_v1.test_location_filters import filtered_catalog, locality_catalog, complex_catalog, import_user
from api_v1.test_customers import customer_users
from api_v1.test_customer_calculations import create_customer_calculations
from bank.models import MortgageProgram, MortgageProgramRegionalCreditLimit
from customer.forms import CustomerForm
from customer.location_migration import backfill_customer_locations
from customer.models import Customer, CustomerCalculation, CustomerTrenchCalculation
from location.models import City, Location, LocationClosure, Region


@pytest.fixture
def geographic_customer(client, filtered_catalog, customer_users):
    """Keep a legacy profile and its original regional limit for migration tests."""
    owner, _ = customer_users
    district = filtered_catalog['legacy'].district
    customer = Customer.objects.create(
        user=owner, first_name='Проверка', residence_city=district.city,
        desired_city=district.city, desired_district=district,
        initial_payment_amount=2000000, max_monthly_payment=150000, age=35,
    )
    program = MortgageProgram.objects.create(name='Льготная', is_preferential=True, credit_limit=6000000)
    MortgageProgramRegionalCreditLimit.objects.create(mortgage_program=program, region=district.city.region, credit_limit=12000000)
    customer.preferential_programs.add(program)
    client.force_login(owner)
    return customer


@pytest.mark.django_db(transaction=True)
def test_schema_migration_retains_original_profiles_calculation_links_and_limits(client, geographic_customer, filtered_catalog):
    """Apply the actual migration, reverse it safely, reapply and test idempotency."""
    customer = geographic_customer
    market, trench = create_customer_calculations(client, customer, filtered_catalog['strelna'][3])
    executor = MigrationExecutor(connection)
    previous = [('customer', '0005_customertrenchcalculation_and_more')]
    target = [('customer', '0006_customer_desired_district_location_and_more')]
    old_model = executor.loader.project_state(previous).apps.get_model('customer', 'Customer')
    original_fields = [field.attname for field in old_model._meta.concrete_fields]
    snapshot = Customer.objects.filter(pk=customer.pk).values(*original_fields).get()
    old_region = customer.get_desired_region().pk
    old_limit = customer.get_preferential_credit_limit()
    try:
        executor.migrate(previous)
        assert old_model.objects.filter(pk=customer.pk).values(*original_fields).get() == snapshot
        MigrationExecutor(connection).migrate(target)
        customer.refresh_from_db()
        assert customer.purchase_uses_canonical_locations and customer.residence_uses_canonical_location
        assert customer.desired_financial_region_id == old_region
        assert customer.get_preferential_credit_limit() == old_limit == Decimal('12000000')
        assert Customer.objects.filter(pk=customer.pk).values(*original_fields).get() == snapshot
        assert CustomerCalculation.objects.filter(customer=customer, calculation_id=market).exists()
        assert CustomerTrenchCalculation.objects.filter(customer=customer, calculation_id=trench).exists()
        MigrationExecutor(connection).migrate(previous)
        assert old_model.objects.filter(pk=customer.pk).values(*original_fields).get() == snapshot
        MigrationExecutor(connection).migrate(target)
        strelna = filtered_catalog['strelna'][0]
        assert client.patch(f'/api/v1/customers/{customer.pk}/', {
            'desiredRegionLocationId': strelna.region_id, 'desiredLocalityId': strelna.pk,
            'desiredDistrictLocationId': strelna.parent_id,
        }, content_type='application/json').status_code == 200
        backfill_customer_locations(apps)
        backfill_customer_locations(apps)
        customer.refresh_from_db()
        assert customer.desired_locality_id == strelna.pk
        assert customer.get_preferential_credit_limit() == old_limit
    finally:
        MigrationExecutor(connection).migrate(target)


@pytest.mark.django_db
def test_new_localities_and_clearing_preserve_snapshots_and_financial_identity(client, geographic_customer, filtered_catalog):
    """Separate geography from finance and never revive a cleared historical value."""
    customer = geographic_customer
    strelna = filtered_catalog['strelna'][0]
    pushkin = filtered_catalog['pushkin'][0]
    old_ids = (customer.residence_city_id, customer.desired_city_id, customer.desired_district_id)
    url = f'/api/v1/customers/{customer.pk}/'
    response = client.patch(url, {'residenceLocalityId': pushkin.pk, 'desiredLocalityId': strelna.pk}, content_type='application/json')
    assert response.status_code == 200, response.content
    customer.refresh_from_db()
    assert customer.desired_region_location_id == strelna.region_id
    assert customer.get_desired_region().pk == customer.desired_city.region_id
    assert customer.get_preferential_credit_limit() == Decimal('12000000')
    data = client.get(url).json()
    assert data['residenceLocality'] == 'Пушкин' and data['desiredLocality'] == 'Стрельна'
    assert data['calculated']['preferentialCreditLimit'] == '12000000.00'
    response = client.patch(url, {
        'residenceLocalityId': None, 'desiredLocalityId': None,
        'desiredDistrictLocationId': None, 'desiredRegionLocationId': None,
    }, content_type='application/json')
    assert response.status_code == 200
    customer.refresh_from_db()
    assert old_ids == (customer.residence_city_id, customer.desired_city_id, customer.desired_district_id)
    assert customer.residence_display_name is None and customer.purchase_locality_display_name is None
    assert customer.get_desired_region() is None and customer.get_preferential_credit_limit() == Decimal('6000000')


@pytest.mark.django_db
def test_unmapped_legacy_values_survive_other_profile_changes(client, geographic_customer):
    """Do not guess a locality or lose financial context when mappings are absent."""
    customer = geographic_customer
    unknown = City.objects.create(name='Несопоставленный город', region=customer.desired_city.region)
    customer.residence_city = unknown
    customer.desired_city = unknown
    customer.desired_district = None
    customer.save()
    backfill_customer_locations(apps)
    customer.refresh_from_db()
    assert not customer.purchase_uses_canonical_locations and not customer.residence_uses_canonical_location
    assert client.patch(f'/api/v1/customers/{customer.pk}/', {'comment': 'Изменение заметки'}, content_type='application/json').status_code == 200
    customer.refresh_from_db()
    assert customer.desired_city_id == unknown.pk and customer.get_preferential_credit_limit() == Decimal('12000000')
    form = CustomerForm(data={'first_name': customer.first_name, 'comment': 'Другая заметка'}, instance=customer)
    assert form.is_valid(), form.errors
    form.save()
    customer.refresh_from_db()
    assert customer.desired_city_id == unknown.pk and not customer.purchase_uses_canonical_locations


@pytest.mark.django_db
def test_role_hierarchy_inactive_and_ownership_validation(client, geographic_customer, filtered_catalog, customer_users):
    """Reject wrong roles, incompatible parents, new inactive choices and foreign owners."""
    customer = geographic_customer
    strelna = filtered_catalog['strelna'][0]
    pushkin = filtered_catalog['pushkin'][0]
    url = f'/api/v1/customers/{customer.pk}/'
    for payload in [
        {'residenceLocalityId': strelna.parent_id},
        {'desiredLocalityId': strelna.pk, 'desiredDistrictLocationId': pushkin.parent_id},
        {'desiredCityId': customer.desired_city_id, 'desiredLocalityId': strelna.pk},
    ]:
        assert client.patch(url, payload, content_type='application/json').status_code == 400
    strelna.is_active = False
    strelna.save(update_fields=['is_active'])
    assert client.patch(url, {'residenceLocalityId': strelna.pk}, content_type='application/json').status_code == 400
    client.force_login(customer_users[1])
    assert client.get(url).status_code == 404
    assert client.patch(url, {'residenceLocalityId': pushkin.pk}, content_type='application/json').status_code == 404
    protected = Client(enforce_csrf_checks=True)
    protected.force_login(customer_users[0])
    assert protected.patch(url, {'residenceLocalityId': pushkin.pk}, content_type='application/json').status_code == 403


@pytest.mark.django_db
def test_native_form_bounded_choices_and_geo_only_region_budget(client, geographic_customer, filtered_catalog):
    """Validate native controls and region-wide purchase preferences."""
    customer = geographic_customer
    strelna = filtered_catalog['strelna'][0]
    form = CustomerForm(data={
        'first_name': customer.first_name, 'residence_locality': strelna.pk,
        'desired_region_location': strelna.region_id,
        'preferential_programs': list(customer.preferential_programs.values_list('pk', flat=True)),
    }, instance=customer)
    assert form.is_valid(), form.errors
    form.save()
    customer.refresh_from_db()
    assert customer.desired_locality_id is None and customer.desired_region_location_id == strelna.region_id
    assert customer.get_preferential_credit_limit() == Decimal('12000000')
    page = client.get(reverse('customer:update', args=[customer.pk]))
    assert page.status_code == 200
    assert all(len(form.fields[name].widget.choices) <= 52 for name in ['residence_locality', 'desired_locality', 'desired_region_location', 'desired_district_location'])


@pytest.mark.django_db
def test_region_without_financial_mapping_uses_global_limit(client, geographic_customer, filtered_catalog):
    """Do not fabricate financial regions when a new geographic region has no mapping."""
    customer = geographic_customer
    count = Region.objects.count()
    root = Location.objects.create(name='Новый субъект', location_type=filtered_catalog['strelna'][0].region.location_type)
    root.region = root
    root.save(update_fields=['region'])
    response = client.patch(f'/api/v1/customers/{customer.pk}/', {
        'desiredRegionLocationId': root.pk, 'desiredDistrictLocationId': None, 'desiredLocalityId': None,
    }, content_type='application/json')
    assert response.status_code == 200
    customer.refresh_from_db()
    assert customer.get_desired_region() is None
    assert customer.get_preferential_credit_limit() == Decimal('6000000')
    assert Region.objects.count() == count


@pytest.mark.django_db
def test_homonymous_settlements_keep_distinct_ids_and_labels(client, geographic_customer, filtered_catalog):
    """Use parent context to distinguish same-name settlements in customer profiles."""
    customer = geographic_customer
    localities = []
    for key in ['strelna', 'pushkin']:
        parent = filtered_catalog[key][0].parent
        locality = Location.objects.create(name='Сосновка', location_type=filtered_catalog[key][0].location_type,
                                           parent=parent, region=parent.region)
        LocationClosure.objects.bulk_create([
            LocationClosure(ancestor=locality, descendant=locality, depth=0),
            *[LocationClosure(ancestor_id=path.ancestor_id, descendant=locality, depth=path.depth + 1)
              for path in parent.ancestor_links.all()],
        ])
        localities.append(locality)
    url = f'/api/v1/customers/{customer.pk}/'
    assert client.patch(url, {'residenceLocalityId': localities[0].pk, 'desiredLocalityId': localities[1].pk},
                        content_type='application/json').status_code == 200
    data = client.get(url).json()
    assert data['residenceLocalityId'] != data['desiredLocalityId']
    assert 'Петродворцовый' in data['residenceLocalityLabel']
    assert 'Пушкинский' in data['desiredLocalityLabel']


@pytest.mark.django_db
def test_legacy_district_without_city_keeps_original_global_limit(client, geographic_customer):
    """Do not change an original global limit merely by backfilling a district's region."""
    customer = geographic_customer
    customer.desired_city = None
    customer.save(update_fields=['desired_city'])
    assert customer.get_preferential_credit_limit() == Decimal('6000000')
    backfill_customer_locations(apps)
    customer.refresh_from_db()
    assert customer.purchase_uses_canonical_locations
    assert customer.desired_region_location_id and customer.desired_financial_region_id is None
    response = client.patch(f'/api/v1/customers/{customer.pk}/', {
        'desiredRegionLocationId': customer.desired_region_location_id,
        'desiredDistrictLocationId': customer.desired_district_location_id, 'desiredLocalityId': None,
    }, content_type='application/json')
    assert response.status_code == 200
    customer.refresh_from_db()
    assert customer.get_preferential_credit_limit() == Decimal('6000000')
