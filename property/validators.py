from pathlib import Path

from django.conf import settings
from django.core.exceptions import ValidationError

DEFAULT_PROPERTY_IMAGE_ALLOWED_CONTENT_TYPES = (
    'image/gif',
    'image/jpeg',
    'image/png',
    'image/webp',
)
DEFAULT_PROPERTY_IMAGE_ALLOWED_EXTENSIONS = (
    '.gif',
    '.jpeg',
    '.jpg',
    '.png',
    '.webp',
)
DEFAULT_PROPERTY_IMAGE_MAX_UPLOAD_SIZE = 5 * 1024 * 1024


def format_file_size(size):
    """Return a compact human-readable file size."""
    if size >= 1024 * 1024:
        return f'{size / 1024 / 1024:.0f} МБ'
    if size >= 1024:
        return f'{size / 1024:.0f} КБ'
    return f'{size} Б'


def validate_property_image_upload(file_obj):
    """Validate uploaded property image extension, content type, and size."""
    if not file_obj:
        return

    max_upload_size = getattr(
        settings,
        'PROPERTY_IMAGE_MAX_UPLOAD_SIZE',
        DEFAULT_PROPERTY_IMAGE_MAX_UPLOAD_SIZE,
    )
    if getattr(file_obj, 'size', 0) > max_upload_size:
        raise ValidationError(
            (
                'Размер изображения не должен превышать '
                f'{format_file_size(max_upload_size)}.'
            )
        )

    allowed_extensions = getattr(
        settings,
        'PROPERTY_IMAGE_ALLOWED_EXTENSIONS',
        DEFAULT_PROPERTY_IMAGE_ALLOWED_EXTENSIONS,
    )
    extension = Path(file_obj.name or '').suffix.lower()
    if extension not in allowed_extensions:
        raise ValidationError(
            (
                'Недопустимый формат изображения. Разрешены: '
                f'{", ".join(allowed_extensions)}.'
            )
        )

    allowed_content_types = getattr(
        settings,
        'PROPERTY_IMAGE_ALLOWED_CONTENT_TYPES',
        DEFAULT_PROPERTY_IMAGE_ALLOWED_CONTENT_TYPES,
    )
    content_type = getattr(file_obj, 'content_type', '')
    if content_type and content_type.lower() not in allowed_content_types:
        raise ValidationError('Недопустимый тип содержимого изображения.')
