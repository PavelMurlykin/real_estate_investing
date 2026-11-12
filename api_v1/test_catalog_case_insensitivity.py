"""Exercise Cyrillic search and duplicate checks against real PostgreSQL."""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse

from bank.models import Bank, DeveloperMortgageProgram, MortgageProgram
from location.models import City, Region
from property.models import ApartmentLayout, CompanyGroup
from users.roles import MODERATOR_GROUP_NAME


CATALOG_KEYS = ['banks', 'mortgage-programs', 'apartment-layouts', 'cities']
CASE_VARIANTS = ['lower', 'upper', 'mixed-with-whitespace']


def case_variant(value, variant):
    """Change display case and whitespace while preserving the logical name."""
    if variant == 'lower':
        return value.lower()
    if variant == 'upper':
        return value.upper()
    mixed_value = ''.join(
        character.upper() if index % 2 else character.lower()
        for index, character in enumerate(value)
    )
    return '  ' + mixed_value.replace(' ', '   ') + '  '


@pytest.fixture
def catalog_case_records():
    """Create Cyrillic names, including Ё, in every affected catalog family."""
    name = 'Каталог Ёлка'
    first_region = Region.objects.create(name='Первый регион', code='CASE1')
    second_region = Region.objects.create(name='Второй регион', code='CASE2')
    bank = Bank.objects.create(name=name)
    program = MortgageProgram.objects.create(name=name, condition='Условия')
    layout = ApartmentLayout.objects.create(name=name)
    city = City.objects.create(name=name, region=first_region)
    developer_program = DeveloperMortgageProgram.objects.create(
        company_group=CompanyGroup.objects.create(name=name),
        bank=bank,
        mortgage_program=program,
    )
    records = {}
    for key, instance, list_name, detail_name, route_values, fields in [
        ('banks', bank, 'bank_list', 'bank_detail', {}, {}),
        ('mortgage-programs', program, 'mortgage_program_list',
         'mortgage_program_detail', {}, {'condition': 'Условия'}),
        ('apartment-layouts', layout, 'property_dictionary_list',
         'property_dictionary_detail', {'dictionary_key': 'apartment-layouts'},
         {}),
        ('cities', city, 'location_dictionary_list',
         'location_dictionary_detail', {'dictionary_key': 'cities'},
         {'region': first_region}),
        ('developer-programs', developer_program,
         'developer_mortgage_program_list',
         'developer_mortgage_program_detail', {}, {}),
    ]:
        records[key] = {
            'instance': instance,
            'list_url': reverse(
                'api_v1:' + list_name, kwargs=route_values,
            ),
            'detail_name': 'api_v1:' + detail_name,
            'route_values': route_values,
            'model_fields': fields,
            'name': name,
        }
    records['cities']['other_region'] = second_region
    return records


@pytest.fixture
def catalog_manager():
    """Grant only catalog permission to the test account."""
    manager = get_user_model().objects.create_user(
        email='case-moderator@example.com', phone_number='+79990000301',
        password='safe-test-password',
    )
    moderator_group, _ = Group.objects.get_or_create(name=MODERATOR_GROUP_NAME)
    manager.groups.add(moderator_group)
    return manager


@pytest.mark.django_db
@pytest.mark.parametrize('catalog_key', CATALOG_KEYS)
@pytest.mark.parametrize('variant', CASE_VARIANTS)
def test_catalog_rejects_case_duplicates_without_rejecting_own_name(
    client, catalog_case_records, catalog_manager, catalog_key, variant,
):
    """Reject duplicate POST/PATCH and allow the entry's own spelling."""
    client.force_login(catalog_manager)
    record = catalog_case_records[catalog_key]
    instance = record['instance']
    model = type(instance)
    other_entry = model.objects.create(
        name='Другое название', **record['model_fields'],
    )
    requested_name = case_variant(record['name'], variant)
    creation_payload = {'name': requested_name}
    if catalog_key == 'mortgage-programs':
        creation_payload['condition'] = 'Условия'
    if catalog_key == 'cities':
        creation_payload['regionId'] = instance.region_id
    initial_count = model.objects.count()
    response = client.post(
        record['list_url'], creation_payload, content_type='application/json',
    )
    assert response.status_code == 400, response.content
    assert 'name' in response.json()
    assert model.objects.count() == initial_count

    other_url = reverse(
        record['detail_name'],
        kwargs=record['route_values'] | {'pk': other_entry.pk},
    )
    response = client.patch(
        other_url, {'name': requested_name}, content_type='application/json',
    )
    assert response.status_code == 400, response.content
    assert 'name' in response.json()
    other_entry.refresh_from_db()
    assert other_entry.name == 'Другое название'
    assert model.objects.count() == initial_count

    own_url = reverse(
        record['detail_name'],
        kwargs=record['route_values'] | {'pk': instance.pk},
    )
    response = client.patch(
        own_url, {'name': requested_name}, content_type='application/json',
    )
    assert response.status_code == 200, response.content
    instance.refresh_from_db()
    assert instance.name == ' '.join(requested_name.split())
    assert model.objects.count() == initial_count


@pytest.mark.django_db
@pytest.mark.parametrize('catalog_key', CATALOG_KEYS + ['developer-programs'])
@pytest.mark.parametrize('variant', CASE_VARIANTS)
def test_catalog_search_finds_cyrillic_names_in_every_case(
    client, catalog_case_records, catalog_key, variant,
):
    """Find Cyrillic names in lower, upper and mixed case."""
    record = catalog_case_records[catalog_key]
    search = ' '.join(case_variant(record['name'], variant).split())
    response = client.get(record['list_url'], {'q': search})
    assert response.status_code == 200, response.content
    assert response.json()['totalCount'] == 1
    assert response.json()['results'][0]['id'] == record['instance'].pk


@pytest.mark.django_db
@pytest.mark.parametrize('variant', CASE_VARIANTS)
def test_city_name_uniqueness_follows_the_selected_region(
    client, catalog_case_records, catalog_manager, variant,
):
    """Allow names in another region and reject a conflicting parent change."""
    client.force_login(catalog_manager)
    record = catalog_case_records['cities']
    original = record['instance']
    other_region = record['other_region']
    response = client.post(
        record['list_url'],
        {'name': case_variant(record['name'], variant),
         'regionId': other_region.pk},
        content_type='application/json',
    )
    assert response.status_code == 201, response.content
    created = City.objects.get(pk=response.json()['id'])
    assert created.region == other_region
    original_name = created.name
    response = client.patch(
        reverse(record['detail_name'], kwargs={
            'dictionary_key': 'cities', 'pk': created.pk,
        }),
        {'regionId': original.region_id}, content_type='application/json',
    )
    assert response.status_code == 400, response.content
    assert 'name' in response.json()
    created.refresh_from_db()
    assert created.region == other_region
    assert created.name == original_name
    assert City.objects.count() == 2
