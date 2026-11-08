import base64
import json
from decimal import Decimal
from io import BytesIO
from pathlib import Path

from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth.models import Group

from core.json_import import JsonImportError
from property.complex_import import import_complex_catalog
from property.models import (
    ApartmentDecoration, ApartmentLayout, Property, RealEstateComplex,
    RealEstateComplexBuilding, RealEstateComplexPhoto,
)
from users.roles import APPLICATION_ADMINISTRATOR_GROUP_NAME
from .test_real_estate_complexes import complex_catalog, create_catalog_manager


def image_content(color):
    """Create a real image with distinct content for upload tests."""
    output = BytesIO()
    Image.new('RGB', (8, 8), color).save(output, 'JPEG')
    return output.getvalue()


@pytest.mark.django_db
def test_complex_form_creates_multiple_photos_with_selected_primary(
    client, complex_catalog, settings, tmp_path,
):
    """Create the complete gallery and homepage choice in one multipart save."""
    settings.MEDIA_ROOT = tmp_path
    client.force_login(create_catalog_manager())
    payload = {
        'name': 'Новый квартал',
        'developerId': complex_catalog['developer'].pk,
        'districtId': complex_catalog['district'].pk,
        'realEstateClassId': complex_catalog['real_estate_class'].pk,
        'realEstateTypeId': complex_catalog['real_estate_type'].pk,
        'photos': [
            SimpleUploadedFile('one.jpg', image_content('red'), 'image/jpeg'),
            SimpleUploadedFile('two.jpg', image_content('blue'), 'image/jpeg'),
        ],
        'primaryPhotoIndex': '1',
    }
    url = reverse('api_v1:real_estate_complex_list')
    response = client.post(url, payload)
    assert response.status_code == 201, response.json()
    result = response.json()
    assert len(result['photos']) == 2
    assert result['photoUrl'] == result['photos'][1]['url']
    assert [photo['isPrimary'] for photo in result['photos']] == [False, True]


@pytest.mark.django_db
def test_complex_form_preserves_gallery_and_relations_when_changing_primary(
    client, complex_catalog, settings, tmp_path, django_capture_on_commit_callbacks,
):
    """Select another existing image without deleting the previous main photo."""
    from property.complex_photos import add_complex_photos

    settings.MEDIA_ROOT = tmp_path
    complex_object = complex_catalog['complex']
    photos = add_complex_photos(complex_object, [
        SimpleUploadedFile('one.jpg', image_content('red'), 'image/jpeg'),
        SimpleUploadedFile('two.jpg', image_content('blue'), 'image/jpeg'),
    ])
    client.force_login(create_catalog_manager())
    with django_capture_on_commit_callbacks(execute=True):
        response = client.patch(
            reverse('api_v1:real_estate_complex_detail', kwargs={'pk': complex_object.pk}),
            json.dumps({'name': 'Обновлённый ЖК', 'primaryPhotoId': photos[1].pk}),
            content_type='application/json',
        )
    assert response.status_code == 200, response.json()
    assert response.json()['photoUrl'] == photos[1].image.url
    assert list(complex_object.photos.values_list('pk', flat=True)) == [photo.pk for photo in photos]
    assert all(photo.image.storage.exists(photo.image.name) for photo in photos)
    assert complex_object.realestatecomplexbuilding_set.get().pk == complex_catalog['building'].pk
    assert complex_object.metro_availability.get().pk == complex_catalog['availability'].pk


@pytest.mark.django_db
@pytest.mark.parametrize('selection', [
    {'primaryPhotoId': 999999},
    {'primaryPhotoIndex': 2},
    {'primaryPhotoIndex': 0, 'primaryPhotoId': 999999},
])
def test_complex_form_rejects_invalid_primary_without_partial_updates(
    client, complex_catalog, selection,
):
    """Reject unowned images, missing uploads and conflicting main choices."""
    complex_object = complex_catalog['complex']
    original_name = complex_object.name
    client.force_login(create_catalog_manager())
    response = client.patch(
        reverse('api_v1:real_estate_complex_detail', kwargs={'pk': complex_object.pk}),
        json.dumps({'name': 'Не сохранять', **selection}),
        content_type='application/json',
    )
    assert response.status_code == 400
    complex_object.refresh_from_db()
    assert complex_object.name == original_name


@pytest.mark.django_db
def test_complex_form_rolls_back_changes_and_files_on_gallery_overflow(
    client, complex_catalog, settings, tmp_path, monkeypatch,
):
    """An overflow after writing one image rolls back the entire form save."""
    from property.complex_photos import add_complex_photos

    settings.MEDIA_ROOT = tmp_path
    complex_object = complex_catalog['complex']
    original_name = complex_object.name
    original = add_complex_photos(complex_object, [
        SimpleUploadedFile('old.jpg', image_content('red'), 'image/jpeg'),
    ])[0]
    monkeypatch.setattr('property.complex_photos.MAX_COMPLEX_PHOTOS', 2)
    api_client = APIClient()
    api_client.force_authenticate(create_catalog_manager())
    response = api_client.patch(
        reverse('api_v1:real_estate_complex_detail', kwargs={'pk': complex_object.pk}),
        {'name': 'Не сохранять', 'photos': [
            SimpleUploadedFile('new.jpg', image_content('blue'), 'image/jpeg'),
            SimpleUploadedFile('excess.jpg', image_content('green'), 'image/jpeg'),
        ]}, format='multipart',
    )
    assert response.status_code == 400, response.json()
    complex_object.refresh_from_db()
    assert complex_object.name == original_name
    assert complex_object.photo.name == original.image.name
    assert complex_object.photos.count() == 1
    assert len(list(tmp_path.rglob('*.jpg'))) == 1


@pytest.fixture
def import_payload(complex_catalog):
    """Describe an existing project using portable natural keys."""
    return {
        'version': 1,
        'complexes': [{
            'key': 'test:white-nights', 'name': 'Белые Ночи',
            'region_code': 'TC', 'region': 'Тестовый регион', 'city': 'Тестоград',
            'district': 'Центральный', 'developer': 'Северный девелопер',
            'real_estate_class': 'Бизнес', 'real_estate_type': 'Квартира',
            'description': 'Дополненное описание',
            'buildings': [{'number': '1', 'address': 'Обновлённая улица, 1'}],
            'metro': [{'station': 'Тестовая', 'line': 'Зелёная', 'color': '#118844',
                       'mode': 'Пешком', 'minutes': 9}],
            'photos': [{'name': 'one.jpg', 'data': base64.b64encode(image_content('red')).decode()}],
            'sources': ['https://example.com/project'],
        }],
    }


@pytest.mark.django_db
def test_import_matches_and_preserves_related_ids(import_payload, complex_catalog, settings, tmp_path):
    """Reuse project and child IDs and deduplicate media on a rerun."""
    settings.MEDIA_ROOT = tmp_path
    complex_object = complex_catalog['complex']
    original_building = complex_catalog['building'].pk
    original_metro = complex_catalog['availability'].pk
    first = import_complex_catalog(import_payload)
    second = import_complex_catalog(import_payload)
    assert first['created'] == second['created'] == 0
    assert first['photos'] == 1
    assert second['photos'] == 0
    assert RealEstateComplex.objects.count() == 1
    complex_object.refresh_from_db()
    assert complex_object.description == 'Дополненное описание'
    assert complex_object.realestatecomplexbuilding_set.get().pk == original_building
    assert complex_object.metro_availability.get().pk == original_metro
    assert complex_object.metro_availability.get().walking_time_minutes == 9
    assert complex_object.photo.name == complex_object.photos.get().image.name


@pytest.mark.django_db
def test_import_renames_building_and_preserves_properties_on_rerun(
    import_payload, complex_catalog, settings, tmp_path,
):
    """Replace a placeholder number while keeping properties and omitted rows."""
    settings.MEDIA_ROOT = tmp_path
    building = complex_catalog['building']
    omitted = RealEstateComplexBuilding.objects.create(
        number='2', real_estate_complex=complex_catalog['complex'],
    )
    property_object = Property.objects.create(
        apartment_number='7', building=building,
        decoration=ApartmentDecoration.objects.create(name='Без отделки'),
        layout=ApartmentLayout.objects.create(name='Студия'),
        area=Decimal('32.60'), floor=5, property_cost=Decimal('1000000.00'),
    )
    original_property = Property.objects.values().get(pk=property_object.pk)
    import_payload['complexes'][0]['buildings'][0].update(
        number='3', match_number='1',
    )
    first = import_complex_catalog(import_payload)
    second = import_complex_catalog(import_payload)

    building.refresh_from_db()
    assert building.number == '3'
    assert building.address == 'Обновлённая улица, 1'
    assert building.commissioning_year == 2028
    assert RealEstateComplexBuilding.objects.count() == 2
    assert RealEstateComplexBuilding.objects.filter(
        pk=omitted.pk, number='2',
    ).exists()
    assert Property.objects.values().get(pk=property_object.pk) == original_property
    assert first['created'] == second['created'] == second['photos'] == 0


@pytest.mark.django_db
@pytest.mark.parametrize('buildings', [
    [{'number': '2', 'match_number': '1'}],
    [{'number': '3', 'match_number': '404'}],
    [{'number': '3', 'match_number': '1'}, {'number': '4', 'match_number': '1'}],
    [{'number': '3', 'match_number': '1'}, {'number': '1'}],
])
def test_import_rejects_ambiguous_building_renames(
    import_payload, complex_catalog, buildings, settings, tmp_path,
):
    """Reject merges and reused aliases atomically instead of creating copies."""
    settings.MEDIA_ROOT = tmp_path
    RealEstateComplexBuilding.objects.create(
        number='2', real_estate_complex=complex_catalog['complex'],
    )
    original = list(RealEstateComplexBuilding.objects.order_by('pk').values())
    import_payload['complexes'][0]['buildings'] = buildings
    with pytest.raises(JsonImportError):
        import_complex_catalog(import_payload)
    assert list(RealEstateComplexBuilding.objects.order_by('pk').values()) == original
    assert not RealEstateComplexPhoto.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize('previous_number', [None, '', ' ', '---', 1, '1' * 101])
def test_import_rejects_invalid_previous_building_number(
    import_payload, previous_number, settings, tmp_path,
):
    """Require an explicit nonempty previous number for a rename."""
    settings.MEDIA_ROOT = tmp_path
    import_payload['complexes'][0]['buildings'][0]['match_number'] = previous_number
    with pytest.raises(JsonImportError):
        import_complex_catalog(import_payload)


@pytest.mark.django_db
def test_import_rolls_back_all_database_and_media(import_payload, settings, tmp_path, complex_catalog):
    """Roll back files written for an earlier record when a later row fails."""
    settings.MEDIA_ROOT = tmp_path
    invalid = {**import_payload['complexes'][0], 'key': 'test:bad', 'name': 'Другой ЖК',
               'buildings': [{'number': ''}]}
    import_payload['complexes'].append(invalid)
    with pytest.raises(ValidationError):
        import_complex_catalog(import_payload)
    assert not RealEstateComplexPhoto.objects.exists()
    complex_catalog['complex'].refresh_from_db()
    assert complex_catalog['complex'].description == 'Комплекс у парка'
    assert not list(tmp_path.rglob('*.jpg'))


@pytest.mark.django_db
def test_gallery_upload_validation_permissions_and_primary(client, complex_catalog, settings, tmp_path):
    """Upload multiple images and change the homepage photo by owned ID."""
    settings.MEDIA_ROOT = tmp_path
    complex_object = complex_catalog['complex']
    url = reverse('api_v1:complex_photo_upload', kwargs={'pk': complex_object.pk})
    assert client.post(url).status_code == 403
    client.force_login(create_catalog_manager())
    broken = client.post(url, {'files': [
        SimpleUploadedFile('valid.jpg', image_content('red'), 'image/jpeg'),
        SimpleUploadedFile('broken.jpg', b'broken', 'image/jpeg'),
    ]})
    assert broken.status_code == 400
    assert not complex_object.photos.exists()
    response = client.post(url, {'files': [
        SimpleUploadedFile('one.jpg', image_content('red'), 'image/jpeg'),
        SimpleUploadedFile('two.jpg', image_content('blue'), 'image/jpeg'),
    ]})
    assert response.status_code == 200, response.json()
    photos = response.json()['photos']
    assert len(photos) == 2
    assert photos[0]['isPrimary']
    selection = client.post(reverse('api_v1:complex_photo_primary', kwargs={
        'pk': complex_object.pk, 'photo_id': photos[1]['id'],
    }))
    assert selection.status_code == 200
    assert selection.json()['photoUrl'] == photos[1]['url']
    assert [photo['isPrimary'] for photo in selection.json()['photos']] == [False, True]
    complex_object.refresh_from_db()
    assert complex_object.photo.name == complex_object.photos.get(pk=photos[1]['id']).image.name


@pytest.mark.django_db
def test_photo_selection_rejects_foreign_photo(client, complex_catalog):
    """A photo ID from another complex cannot change the requested card."""
    complex_object = complex_catalog['complex']
    other = RealEstateComplex.objects.create(
        name='Другой', developer=complex_object.developer, district=complex_object.district,
        real_estate_class=complex_object.real_estate_class,
        real_estate_type=complex_object.real_estate_type,
    )
    photo = RealEstateComplexPhoto.objects.create(
        real_estate_complex=other, image='other.jpg',
    )
    client.force_login(create_catalog_manager())
    response = client.post(reverse('api_v1:complex_photo_primary', kwargs={
        'pk': complex_object.pk, 'photo_id': photo.pk,
    }))
    assert response.status_code == 404


@pytest.mark.django_db
def test_import_endpoint_requires_administrator_and_accepts_json(
    client, import_payload, settings, tmp_path,
):
    """Enforce the import role and process a real multipart JSON upload."""
    settings.MEDIA_ROOT = tmp_path
    url = reverse('api_v1:complex_import')
    assert client.post(url).status_code == 403
    user = create_catalog_manager()
    client.force_login(user)
    assert client.post(url).status_code == 403
    group, _ = Group.objects.get_or_create(
        name=APPLICATION_ADMINISTRATOR_GROUP_NAME,
    )
    user.groups.add(group)
    response = client.post(url, {'file': SimpleUploadedFile(
        'complexes.json', json.dumps(import_payload).encode('utf-8'),
        'application/json',
    )})
    assert response.status_code == 200, response.json()
    assert response.json()['updated'] == 1
    assert response.json()['photos'] == 1


@pytest.mark.django_db
def test_prepared_complex_snapshot_is_portable(settings, tmp_path):
    """Import the real delivered file into an empty catalog and rerun it."""
    from property.models import RealEstateClass

    settings.MEDIA_ROOT = tmp_path
    path = Path(__file__).resolve().parents[1] / 'data/complexes-moscow-spb-2026-11.json'
    payload = json.loads(path.read_text(encoding='utf-8'))
    for name in {row['real_estate_class'] for row in payload['complexes']}:
        RealEstateClass.objects.create(name=name, weight='1.00')
    first = import_complex_catalog(payload)
    second = import_complex_catalog(payload)
    assert first['created'] == len(payload['complexes'])
    assert second['created'] == 0
    assert second['photos'] == 0
    assert RealEstateComplex.objects.count() == len(payload['complexes'])
    assert RealEstateComplexBuilding.objects.count() == sum(
        len(row['buildings']) for row in payload['complexes']
    )
    assert RealEstateComplexPhoto.objects.count() == sum(
        len(row['photos']) for row in payload['complexes']
    )
