import base64
import json
from io import BytesIO
from pathlib import Path

from rest_framework.exceptions import ValidationError

import pytest
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.contrib.auth.models import Group

from property.complex_import import import_complex_catalog
from property.models import RealEstateComplex, RealEstateComplexPhoto
from users.roles import APPLICATION_ADMINISTRATOR_GROUP_NAME
from .test_real_estate_complexes import complex_catalog, create_catalog_manager


def image_content(color):
    """Create a real image with distinct content for upload tests."""
    output = BytesIO()
    Image.new('RGB', (8, 8), color).save(output, 'JPEG')
    return output.getvalue()


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
    assert RealEstateComplexPhoto.objects.count() == sum(
        len(row['photos']) for row in payload['complexes']
    )
