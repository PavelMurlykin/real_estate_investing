"""Bounded JSON upload reader shared by catalog imports."""

import json
from decimal import Decimal


class JsonImportError(ValueError):
    """An invalid catalog file or a reference that cannot be resolved."""


def _unique_json_object(pairs):
    """Reject repeated JSON properties rather than silently dropping values."""
    result = {}
    for name, value in pairs:
        if name in result:
            raise JsonImportError(f'Повторяющееся поле JSON: {name[:80]}.')
        result[name] = value
    return result


def _invalid_json_constant(value):
    """Reject numeric tokens outside the JSON specification."""
    raise JsonImportError(f'Недопустимое число JSON: {value}.')


def read_json_upload(upload, max_bytes=1024 * 1024):
    """Read one bounded UTF-8 upload into the source-independent payload."""
    if not upload or not upload.name.lower().endswith('.json'):
        raise JsonImportError('Выберите файл с расширением .json.')
    if upload.size > max_bytes:
        raise JsonImportError(f'Размер файла должен быть не больше {max_bytes // (1024 * 1024)} МБ.')
    try:
        return json.loads(
            upload.read().decode('utf-8-sig'),
            object_pairs_hook=_unique_json_object,
            parse_float=Decimal,
            parse_constant=_invalid_json_constant,
        )
    except JsonImportError:
        raise
    except (ValueError, RecursionError) as error:
        raise JsonImportError('Загрузите корректный JSON в кодировке UTF-8.') from error
