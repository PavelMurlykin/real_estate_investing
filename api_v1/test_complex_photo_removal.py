"""Exercise transactional gallery removal through the complex edit API."""

import json

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError

from property.complex_photos import add_complex_photos, remove_complex_photos
from property.models import RealEstateComplex, RealEstateComplexPhoto

from .serializers import RealEstateComplexWriteSerializer
from .test_complex_import_photos import image_content
from .test_real_estate_complexes import complex_catalog, create_catalog_manager


@pytest.fixture
def gallery(complex_catalog, settings, tmp_path):
    """Create three stored images with the middle image selected as primary."""
    settings.MEDIA_ROOT = tmp_path
    complex_object = complex_catalog['complex']
    photos = add_complex_photos(complex_object, [
        SimpleUploadedFile(f'{color}.jpg', image_content(color), 'image/jpeg')
        for color in ('red', 'blue', 'green')
    ], primary_index=1)
    return complex_object, photos


@pytest.fixture
def gallery_client():
    """Authenticate a moderator for multipart and JSON gallery edits."""
    client = APIClient()
    client.force_authenticate(create_catalog_manager())
    return client


def detail_url(complex_object):
    """Return the edit endpoint for the test complex."""
    return reverse(
        'api_v1:real_estate_complex_detail', kwargs={'pk': complex_object.pk},
    )


@pytest.mark.django_db
@pytest.mark.parametrize(('removed_indices', 'primary_index'), [
    ([1], 0), ([0], 1), ([0, 1], 2), ([0, 1, 2], None),
])
def test_removal_selects_next_or_keeps_main_and_deletes_files_after_commit(
    gallery, gallery_client, removed_indices, primary_index,
    django_capture_on_commit_callbacks, complex_catalog,
):
    """Choose the next displayed image and keep child rows unchanged."""
    complex_object, photos = gallery
    with django_capture_on_commit_callbacks(execute=True):
        response = gallery_client.patch(detail_url(complex_object), {
            'removedPhotoIds': [photos[index].pk for index in removed_indices],
        }, format='json')
        assert response.status_code == 200, response.json()
        assert all(photo.image.storage.exists(photo.image.name) for photo in photos)
    remaining = [
        photo for index, photo in enumerate(photos) if index not in removed_indices
    ]
    result = response.json()
    assert [photo['id'] for photo in result['photos']] == [
        photo.pk for photo in remaining
    ]
    expected_url = photos[primary_index].image.url if primary_index is not None else None
    assert result['photoUrl'] == expected_url
    for index, photo in enumerate(photos):
        assert photo.image.storage.exists(photo.image.name) == (
            index not in removed_indices
        )
    assert complex_object.realestatecomplexbuilding_set.get().pk == (
        complex_catalog['building'].pk
    )
    assert complex_object.metro_availability.get().pk == (
        complex_catalog['availability'].pk
    )


@pytest.mark.django_db
def test_removed_slots_can_be_reused_by_multipart_uploads(
    gallery, gallery_client, monkeypatch, django_capture_on_commit_callbacks,
):
    """Apply removals before enforcing gallery capacity for new files."""
    complex_object, photos = gallery
    monkeypatch.setattr('property.complex_photos.MAX_COMPLEX_PHOTOS', 3)
    with django_capture_on_commit_callbacks(execute=True):
        response = gallery_client.patch(detail_url(complex_object), {
            'removedPhotoIds': json.dumps([photo.pk for photo in photos]),
            'photos': [SimpleUploadedFile(
                'new.jpg', image_content('yellow'), 'image/jpeg',
            )],
        }, format='multipart')
    assert response.status_code == 200, response.json()
    result = response.json()
    assert len(result['photos']) == 1
    assert result['photoUrl'] == result['photos'][0]['url']
    assert result['photos'][0]['isPrimary']


@pytest.mark.django_db
def test_removal_rolls_back_rows_main_and_files_when_upload_overflows(
    gallery, gallery_client, monkeypatch, tmp_path,
    django_capture_on_commit_callbacks,
):
    """Retain removed images when a later operation rejects the same form."""
    complex_object, photos = gallery
    original_files = set(tmp_path.rglob('*.jpg'))
    monkeypatch.setattr('property.complex_photos.MAX_COMPLEX_PHOTOS', 3)
    with django_capture_on_commit_callbacks(execute=True) as callbacks:
        response = gallery_client.patch(detail_url(complex_object), {
            'name': 'Не сохранять',
            'removedPhotoIds': json.dumps([photos[1].pk]),
            'photos': [
                SimpleUploadedFile('new.jpg', image_content('yellow'), 'image/jpeg'),
                SimpleUploadedFile('extra.jpg', image_content('black'), 'image/jpeg'),
            ],
        }, format='multipart')
    assert response.status_code == 400, response.json()
    complex_object.refresh_from_db()
    assert complex_object.name == 'Белые ночи'
    assert complex_object.photo.name == photos[1].image.name
    assert complex_object.photos.count() == 3
    assert set(tmp_path.rglob('*.jpg')) == original_files
    assert not callbacks


@pytest.mark.django_db
def test_foreign_and_selected_removed_images_are_rejected(gallery, gallery_client):
    """Do not allow deletion across complexes or selecting a deleted image."""
    complex_object, photos = gallery
    other = RealEstateComplex.objects.create(
        name='Другой ЖК', developer=complex_object.developer,
        district=complex_object.district,
        real_estate_class=complex_object.real_estate_class,
        real_estate_type=complex_object.real_estate_type,
    )
    foreign_photo = RealEstateComplexPhoto.objects.create(
        real_estate_complex=other, image='foreign.jpg',
    )
    for payload in (
        {'removedPhotoIds': [foreign_photo.pk]},
        {'removedPhotoIds': [photos[1].pk], 'primaryPhotoId': photos[1].pk},
    ):
        response = gallery_client.patch(
            detail_url(complex_object), payload, format='json',
        )
        assert response.status_code == 400
    assert complex_object.photos.count() == 3
    assert other.photos.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('identifiers', [{'id': 1}, [True], [-1], list(range(1, 32))])
def test_removal_requires_bounded_positive_identifiers(
    gallery, gallery_client, identifiers,
):
    """Reject malformed removal requests before changing any data."""
    complex_object, _photos = gallery
    response = gallery_client.patch(detail_url(complex_object), {
        'removedPhotoIds': identifiers,
    }, format='json')
    assert response.status_code == 400
    assert complex_object.photos.count() == 3


@pytest.mark.django_db
def test_removal_requires_catalog_permissions(gallery, client):
    """Keep anonymous callers from deleting photos through the edit API."""
    complex_object, photos = gallery
    response = client.patch(
        detail_url(complex_object),
        json.dumps({'removedPhotoIds': [photos[0].pk]}),
        content_type='application/json',
    )
    assert response.status_code == 403
    assert complex_object.photos.count() == 3


@pytest.mark.django_db
def test_removing_legacy_main_chooses_gallery_photo(
    complex_catalog, gallery_client, settings, tmp_path,
    django_capture_on_commit_callbacks,
):
    """Handle an old main image that has no separate gallery row."""
    settings.MEDIA_ROOT = tmp_path
    complex_object = complex_catalog['complex']
    complex_object.photo.save('legacy.jpg', SimpleUploadedFile(
        'legacy.jpg', image_content('red'), 'image/jpeg',
    ))
    legacy_name = complex_object.photo.name
    legacy_storage = complex_object.photo.storage
    photo = RealEstateComplexPhoto.objects.create(
        real_estate_complex=complex_object,
        image=SimpleUploadedFile('gallery.jpg', image_content('blue'), 'image/jpeg'),
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = gallery_client.patch(detail_url(complex_object), {
            'clearPhoto': True,
        }, format='json')
    assert response.status_code == 200, response.json()
    assert response.json()['photoUrl'] == photo.image.url
    assert not legacy_storage.exists(legacy_name)


@pytest.mark.django_db
def test_shared_image_is_not_deleted_from_storage(
    gallery, gallery_client, django_capture_on_commit_callbacks,
):
    """Keep a physical file when another complex still references it."""
    complex_object, photos = gallery
    RealEstateComplex.objects.create(
        name='Общее фото', developer=complex_object.developer,
        district=complex_object.district,
        real_estate_class=complex_object.real_estate_class,
        real_estate_type=complex_object.real_estate_type,
        photo=photos[1].image.name,
    )
    with django_capture_on_commit_callbacks(execute=True):
        response = gallery_client.patch(detail_url(complex_object), {
            'removedPhotoIds': [photos[1].pk],
        }, format='json')
    assert response.status_code == 200
    assert photos[1].image.storage.exists(photos[1].image.name)


@pytest.mark.django_db
def test_concurrent_primary_removal_returns_field_error(gallery):
    """Handle a photo deleted after validation without a partial form save."""
    complex_object, photos = gallery
    serializer = RealEstateComplexWriteSerializer(
        complex_object, data={
            'name': 'Не сохранять', 'primaryPhotoId': photos[0].pk,
        }, partial=True,
    )
    serializer.is_valid(raise_exception=True)
    remove_complex_photos(complex_object, [photos[0].pk])
    with pytest.raises(ValidationError, match='primaryPhotoId'):
        serializer.save()
    complex_object.refresh_from_db()
    assert complex_object.name == 'Белые ночи'
    assert complex_object.photo.name == photos[1].image.name
    assert list(complex_object.photos.values_list('pk', flat=True)) == [
        photos[1].pk, photos[2].pk,
    ]
