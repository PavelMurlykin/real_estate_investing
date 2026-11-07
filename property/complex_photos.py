"""Gallery operations shared by uploads, imports and legacy forms."""

import hashlib

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from rest_framework import serializers

from .models import RealEstateComplex, RealEstateComplexPhoto
from .validators import validate_property_image_upload


MAX_COMPLEX_PHOTOS = 30


def validate_complex_photos(files):
    """Validate every image before writing database rows or stored files."""
    if not files or len(files) > MAX_COMPLEX_PHOTOS:
        raise serializers.ValidationError('Выберите от 1 до 30 изображений.')
    field = serializers.ImageField(validators=[validate_property_image_upload])
    try:
        return [field.run_validation(file) for file in files]
    except DjangoValidationError as error:
        raise serializers.ValidationError(error.messages) from error


def sync_legacy_complex_photo(complex_object):
    """Expose an existing single-photo upload in the gallery."""
    if complex_object.photo:
        RealEstateComplexPhoto.objects.get_or_create(
            real_estate_complex=complex_object,
            image=complex_object.photo.name,
        )


def add_complex_photos(complex_object, files, primary_index=None, saved_files=None):
    """Append deduplicated photos and clean new files if a write fails."""
    files = validate_complex_photos(files)
    saved = []
    try:
        with transaction.atomic():
            complex_object = RealEstateComplex.objects.select_for_update().get(
                pk=complex_object.pk
            )
            sync_legacy_complex_photo(complex_object)
            existing = list(complex_object.photos.all())
            by_checksum = {}
            for photo in existing:
                if not photo.image.storage.exists(photo.image.name):
                    continue
                if not photo.checksum:
                    with photo.image.open('rb') as stored:
                        photo.checksum = hashlib.file_digest(stored, 'sha256').hexdigest()
                    photo.save(update_fields=['checksum'])
                by_checksum[photo.checksum] = photo
            imported = []
            total_photos = len(existing)
            for file in files:
                checksum = hashlib.sha256(file.read()).hexdigest()
                file.seek(0)
                photo = by_checksum.get(checksum)
                if photo is None:
                    if total_photos >= MAX_COMPLEX_PHOTOS:
                        raise serializers.ValidationError('В галерее допускается до 30 фото.')
                    photo = RealEstateComplexPhoto(
                        real_estate_complex=complex_object, checksum=checksum,
                    )
                    photo.image.save(file.name, file, save=False)
                    saved.append(photo.image.name)
                    photo.save()
                    total_photos += 1
                    by_checksum[checksum] = photo
                imported.append(photo)
            if primary_index is not None or not complex_object.photo:
                selected = imported[primary_index if primary_index is not None else 0]
                complex_object.photo = selected.image.name
                complex_object.save(update_fields=['photo', 'updated_at'])
        if saved_files is not None:
            saved_files.extend(saved)
        return imported
    except Exception:
        storage = RealEstateComplexPhoto._meta.get_field('image').storage
        for name in saved:
            storage.delete(name)
        raise


@transaction.atomic
def select_primary_complex_photo(complex_object, photo_identifier):
    """Select an owned gallery image as the homepage and card photograph."""
    complex_object = RealEstateComplex.objects.select_for_update().get(
        pk=complex_object.pk
    )
    photo = complex_object.photos.get(pk=photo_identifier)
    complex_object.photo = photo.image.name
    complex_object.save(update_fields=['photo', 'updated_at'])
    return photo
