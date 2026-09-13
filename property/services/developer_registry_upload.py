"""Validated upload adapter for developer registry import files."""

from pathlib import Path
from tempfile import NamedTemporaryFile

from .developer_registry_file_client import (
    FileDeveloperRegistryClient,
    SUPPORTED_SOURCE_FILE_EXTENSIONS,
)
from .developer_registry_importer import (
    DeveloperRegistryImportError,
    import_dom_rf_developers,
)


MAX_DEVELOPER_REGISTRY_UPLOAD_SIZE = 20 * 1024 * 1024


def validate_developer_registry_uploaded_file(uploaded_file):
    """Validate the extension and size of one registry source upload."""
    uploaded_file_name = getattr(uploaded_file, 'name', '')
    extension = Path(uploaded_file_name).suffix.casefold()
    if extension not in SUPPORTED_SOURCE_FILE_EXTENSIONS:
        supported_extensions = ', '.join(SUPPORTED_SOURCE_FILE_EXTENSIONS)
        raise DeveloperRegistryImportError(
            f'Файл импорта должен быть в формате {supported_extensions}.'
        )

    uploaded_file_size = getattr(uploaded_file, 'size', 0)
    if uploaded_file_size > MAX_DEVELOPER_REGISTRY_UPLOAD_SIZE:
        raise DeveloperRegistryImportError(
            'Файл импорта не должен превышать 20 МБ.'
        )


def save_developer_registry_uploaded_file(uploaded_file):
    """Persist an uploaded registry file to a parser-readable temporary path."""
    uploaded_file_name = getattr(uploaded_file, 'name', '')
    extension = Path(uploaded_file_name).suffix.casefold()
    with NamedTemporaryFile(delete=False, suffix=extension) as source_file:
        for chunk in uploaded_file.chunks():
            source_file.write(chunk)
        return source_file.name


def import_developer_registry_uploaded_file(uploaded_file):
    """Validate, import, and remove one temporary registry source file."""
    validate_developer_registry_uploaded_file(uploaded_file)
    source_file_path = save_developer_registry_uploaded_file(uploaded_file)
    try:
        return import_dom_rf_developers(
            client=FileDeveloperRegistryClient(source_file_path)
        )
    finally:
        Path(source_file_path).unlink(missing_ok=True)
