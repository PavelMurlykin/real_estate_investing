import pytest
from django.urls import reverse

from location.models import City, Region
from property.models import CompanyGroup, Developer


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
