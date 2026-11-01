import pytest
from django.urls import reverse
from django.utils.text import Truncator

from location.models import City, District
from property.models import RealEstateComplex

from .test_saved_mortgage import saved_calculation_property


@pytest.fixture
def homepage_catalog(saved_calculation_property):
    """Create two cities including the legacy preferred default."""
    original = saved_calculation_property.building.real_estate_complex
    city = City.objects.create(
        name='Санкт-Петербург', region=original.district.city.region,
    )
    district = District.objects.create(name='Приморский', city=city)
    preferred = RealEstateComplex.objects.create(
        name='ЖК Петербург', district=district, developer=original.developer,
        real_estate_class=original.real_estate_class,
        real_estate_type=original.real_estate_type,
        description='Описание локации. ' * 30,
        map_link='https://yandex.ru/maps/?ll=30.3%2C59.9',
        presentation_link='https://example.com/complex.pdf',
        photo='complexes/homepage.jpg',
    )
    return original, preferred


@pytest.mark.django_db
def test_homepage_defaults_match_django_and_preserve_card_fields(
    client, homepage_catalog, django_assert_num_queries,
):
    """Restore the preferred city, image and location preview without N+1."""
    original, preferred = homepage_catalog
    with django_assert_num_queries(3):
        response = client.get(reverse('api_v1:homepage_complex_list'))
    assert response.status_code == 200
    data = response.json()
    assert data['selectedCity']['id'] == preferred.district.city_id
    assert data['totalCount'] == 1
    row = data['results'][0]
    assert row['id'] == preferred.pk
    assert row['district'] == 'Приморский'
    assert row['description'] == Truncator(preferred.description).chars(220)
    assert row['photoUrl'].endswith('/homepage.jpg')
    assert row['mapUrl'] == preferred.map_link
    assert row['presentationUrl'] == preferred.presentation_link
    django_page = client.get(reverse('homepage:index'))
    assert django_page.context['selected_city'].pk == data['selectedCity']['id']
    assert client.get(reverse('api_v1:homepage_complex_list'), {
        'city': original.district.city_id,
    }).json()['results'][0]['id'] == original.pk


@pytest.mark.django_db
def test_homepage_excludes_inactive_complexes_and_districts(
    client, homepage_catalog,
):
    """Use the legacy activity rules and fallback for invalid selected cities."""
    original, preferred = homepage_catalog
    url = reverse('api_v1:homepage_complex_list')
    original.district.is_active = False
    original.district.save(update_fields=['is_active'])
    assert client.get(url, {'city': original.district.city_id}).json()[
        'totalCount'
    ] == 0
    preferred.is_active = False
    preferred.save(update_fields=['is_active'])
    assert client.get(url).json()['totalCount'] == 0
    preferred.is_active = True
    preferred.save(update_fields=['is_active'])
    for identifier in ('bad', '99999999999999999999', '999999'):
        data = client.get(url, {'city': identifier}).json()
        assert data['selectedCity']['id'] == preferred.district.city_id
    city = original.district.city
    city.is_active = False
    city.save(update_fields=['is_active'])
    assert client.get(url, {'city': city.pk}).json()['selectedCity']['id'] == (
        preferred.district.city_id
    )
    choices = client.get(reverse('api_v1:catalog_options', args=['cities']), {
        'activeOnly': True, 'selected': city.pk,
    }).json()
    assert city.pk not in {item['id'] for item in choices['results']}
    assert choices['selected'] == []


@pytest.mark.django_db
def test_homepage_city_is_paginated_without_losing_later_complexes(
    client, homepage_catalog, django_assert_num_queries,
):
    """Keep every city result reachable using bounded projection queries."""
    _, preferred = homepage_catalog
    RealEstateComplex.objects.bulk_create([
        RealEstateComplex(
            name=f'ЖК {index:03}', district=preferred.district,
            developer=preferred.developer,
            real_estate_class=preferred.real_estate_class,
            real_estate_type=preferred.real_estate_type,
        ) for index in range(104)
    ])
    url = reverse('api_v1:homepage_complex_list')
    with django_assert_num_queries(3):
        response = client.get(url, {'pageSize': 50})
    assert response.json()['totalCount'] == 105
    assert len(response.json()['results']) == 50
    assert len(client.get(url, {'pageSize': 50, 'page': 3}).json()['results']) == 5
    assert client.get(url, {'pageSize': 101}).status_code == 400


@pytest.mark.django_db
def test_homepage_without_cities_has_a_deliberate_empty_response(client):
    """Return the same empty-city state without invalid object lookups."""
    data = client.get(reverse('api_v1:homepage_complex_list')).json()
    assert data['selectedCity'] is None
    assert data['results'] == []
