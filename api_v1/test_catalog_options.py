import pytest
from django.urls import reverse

from location.models import City, Region
from property.models import CompanyGroup, Developer
from bank.models import MortgageProgram


@pytest.mark.django_db
def test_catalog_options_search_before_pagination_and_keep_selected(
    client, django_assert_num_queries,
):
    """Make entries beyond the first page reachable and preserve current values."""
    region = Region.objects.create(name='Регион', code='T')
    cities = City.objects.bulk_create([
        City(name=f'Город {index:03}', region=region) for index in range(105)
    ])
    url = reverse('api_v1:catalog_options', args=['cities'])
    with django_assert_num_queries(3):
        response = client.get(url, {'selected': cities[-1].pk, 'pageSize': 50})
    payload = response.json()
    assert len(payload['results']) == 50
    assert payload['nextPage'] == 2
    assert payload['selected'][0]['id'] == cities[-1].pk
    assert payload['selected'][0]['regionId'] == region.pk
    assert client.get(url, {'page': 3}).json()['results'][-1]['id'] == cities[-1].pk
    searched = client.get(url, {'q': '104'}).json()
    assert searched['totalCount'] == 1
    assert searched['results'][0]['id'] == cities[-1].pk


@pytest.mark.django_db
def test_catalog_options_enforce_parent_filters_and_public_projection(client):
    """Keep cascades coherent and never expose developer requisites."""
    group = CompanyGroup.objects.create(name='Группа')
    developer = Developer.objects.create(name='Застройщик', company_group=group,
        legal_address='Закрытый адрес', taxpayer_identification_number='1234567890')
    payload = client.get(reverse('api_v1:catalog_options', args=['developers']),
        {'q': 'Группа'}).json()
    assert payload['results'] == [{'id': developer.pk, 'label': 'Застройщик (Группа)'}]
    region = Region.objects.create(name='Регион', code='T')
    other = Region.objects.create(name='Другой', code='O')
    City.objects.create(name='Город', region=region)
    url = reverse('api_v1:catalog_options', args=['cities'])
    assert client.get(url, {'regionId': other.pk}).json()['results'] == []
    assert client.get(url, {'pageSize': 101}).status_code == 400
    assert client.get(reverse('api_v1:catalog_options', args=['users'])).status_code == 404


@pytest.mark.django_db
def test_multiple_selections_survive_search_and_remain_bounded(
    client, django_assert_num_queries,
):
    """Return every selected public choice even outside the search page."""
    programs = MortgageProgram.objects.bulk_create([
        MortgageProgram(name=f'Программа {index}', is_preferential=True)
        for index in range(3)
    ])
    ordinary = MortgageProgram.objects.create(
        name='Рыночная программа', is_preferential=False,
    )
    url = reverse('api_v1:catalog_options', args=['preferential-programs'])
    with django_assert_num_queries(3):
        response = client.get(url, {
            'q': 'нет совпадений',
            'selectedIds': [programs[0].pk, programs[2].pk, ordinary.pk],
        })
    assert response.status_code == 200
    assert response.json()['results'] == []
    assert {item['id'] for item in response.json()['selected']} == {
        programs[0].pk, programs[2].pk,
    }
    assert client.get(url, {'selectedIds': [1] * 101}).status_code == 400
