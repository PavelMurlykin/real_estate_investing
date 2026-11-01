import pytest
from django.urls import reverse

from bank.models import BankProgram
from customer.models import Customer
from property.models import ApartmentLayout

from .test_customers import customer_users
from .test_developer_mortgage_programs import developer_program_catalog
from .test_key_rates import key_rate_history
from .test_location_dictionaries import location_dictionary_catalog


@pytest.mark.django_db
@pytest.mark.parametrize(('path', 'fields'), [
    ('company-groups', ['name', 'developerCount']),
    ('developers', ['name', 'companyGroup', 'regions', 'complexCount']),
    ('banks', ['name', 'programCount', 'minimumInterestRate']),
    ('mortgage-programs', ['name', 'isPreferential', 'creditLimit', 'bankCount',
                           'regionalLimitCount', 'aliasCount']),
    ('developer-mortgage-programs', ['companyGroup', 'bank', 'interestRate',
        'gracePeriodMonths', 'minimumInitialPaymentPercent',
        'maximumLoanAmount', 'priceIncreasePercent']),
    ('complexes', ['name', 'developer', 'city', 'realEstateClass',
                   'realEstateType', 'buildingCount']),
    ('property-dictionaries/real-estate-classes',
        ['name', 'description', 'weight', 'usageCount']),
    ('property-dictionaries/apartment-layouts',
        ['name', 'description', 'usageCount']),
    ('location-dictionaries/regions', ['name', 'code', 'usageCount']),
    ('location-dictionaries/cities', ['name', 'region', 'usageCount']),
    ('location-dictionaries/districts', ['name', 'region', 'city', 'usageCount']),
    ('location-dictionaries/metro',
        ['name', 'region', 'city', 'metroLine', 'usageCount']),
    ('customers', ['name', 'phone', 'email', 'city']),
])
def test_visible_columns_support_both_server_sort_directions(
    client, developer_program_catalog, location_dictionary_catalog,
    customer_users, path, fields,
):
    """Compile and execute every public table sort against populated data."""
    owner, _ = customer_users
    client.force_login(owner)
    catalog = developer_program_catalog
    BankProgram.objects.create(
        bank=catalog['bank'], mortgage_program=catalog['mortgage_program'],
        interest_rate='5.90', minimum_initial_payment_percent='20.10',
    )
    catalog['real_estate_complex'].developer.regions.add(
        location_dictionary_catalog['regions']
    )
    ApartmentLayout.objects.create(name='Проверка сортировки')
    Customer.objects.create(
        user=owner, first_name='Клиент', phone='+79990000001',
        residence_city=location_dictionary_catalog['cities'],
    )
    for field in fields:
        for prefix in ('', '-'):
            response = client.get(f'/api/v1/{path}/', {
                'ordering': f'{prefix}{field}', 'pageSize': 1,
            })
            assert response.status_code == 200, (path, field, response.content)
            assert len(response.json()['results']) == 1, (path, field)
    if path == 'banks':
        response = client.get('/api/v1/banks/', {
            'ordering': '-programCount', 'pageSize': 1,
        })
        assert response.json()['results'][0]['id'] == catalog['bank'].pk


@pytest.mark.django_db
def test_key_rate_search_keeps_changes_from_the_full_history(
    client, key_rate_history,
):
    """Search must not change the previous decision used for the delta."""
    url = reverse('api_v1:key_rate_list')
    searched = client.get(url, {'q': '01.03.2026'}).json()
    assert searched['totalCount'] == 1
    assert searched['results'][0]['rateChange'] == '-1.00'
    assert searched['results'][0]['keyRate'] == '11.00'
    by_rate = client.get(url, {'ordering': 'keyRate', 'pageSize': 1}).json()
    assert by_rate['results'][0]['keyRate'] == '10.00'
    assert client.get(url, {'q': '11,00'}).json()['totalCount'] == 1
