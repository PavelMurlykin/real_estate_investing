#!/usr/bin/env python
from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path

import django
from django.apps import apps
from django.conf import settings
from django.core.management import call_command

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault(
    'DJANGO_SETTINGS_MODULE', 'real_estate_investing.settings'
)


django.setup()


def _is_local_app(app_config) -> bool:
    """Описание метода _is_local_app.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        app_config: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    app_path = Path(app_config.path).resolve()
    project_root = Path(settings.BASE_DIR).resolve()
    if app_path != project_root and project_root not in app_path.parents:
        return False
    if app_config.name.startswith('django.'):
        return False
    if app_config.name.startswith('django_bootstrap5'):
        return False
    return True


def _iter_project_models():
    """Описание метода _iter_project_models.

    Выполняет прикладную операцию текущего модуля.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    app_configs = [
        app_config
        for app_config in apps.get_app_configs()
        if _is_local_app(app_config)
    ]
    for app_config in sorted(app_configs, key=lambda item: item.label):
        for model in app_config.get_models():
            meta = model._meta
            if (
                meta.abstract
                or meta.proxy
                or meta.auto_created
                or meta.swapped
            ):
                continue
            yield model


def _validate_utf8_json_fixture(fixture_path: Path) -> None:
    """Описание метода _validate_utf8_json_fixture.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        fixture_path: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    try:
        raw_content = fixture_path.read_bytes()
        text_content = raw_content.decode('utf-8-sig')
    except UnicodeDecodeError as exc:
        raise ValueError(
            'Exported fixture is not UTF-8 encoded: '
            f'{fixture_path.relative_to(BASE_DIR)} '
            f'(byte position {exc.start}).'
        ) from exc

    try:
        json.loads(text_content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            'Exported fixture contains invalid JSON: '
            f'{fixture_path.relative_to(BASE_DIR)} '
            f'(line {exc.lineno}, column {exc.colno}).'
        ) from exc


def export_fixtures() -> int:
    """Описание метода export_fixtures.

    Выполняет прикладную операцию текущего модуля.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    models = sorted(
        _iter_project_models(),
        key=lambda model: (model._meta.app_label, model._meta.model_name),
    )
    if not models:
        print('No project models found for export.')
        return 0

    exported_count = 0
    for model in models:
        app_config = apps.get_app_config(model._meta.app_label)
        fixture_dir = Path(app_config.path) / 'fixtures'
        fixture_dir.mkdir(parents=True, exist_ok=True)

        fixture_path = fixture_dir / f'init_{model._meta.db_table}.json'
        model_label = f'{model._meta.app_label}.{model._meta.model_name}'
        output_buffer = io.StringIO()
        call_command(
            'dumpdata',
            model_label,
            format='json',
            indent=2,
            stdout=output_buffer,
            verbosity=0,
        )
        fixture_path.write_text(
            output_buffer.getvalue(), encoding='utf-8', newline='\n'
        )
        _validate_utf8_json_fixture(fixture_path)
        print(f'[OK] {model_label} -> {fixture_path.relative_to(BASE_DIR)}')
        exported_count += 1

    print(f'Export complete. Generated {exported_count} fixture files.')
    return 0


def main() -> int:
    """Описание метода main.

    Выполняет прикладную операцию текущего модуля.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    try:
        return export_fixtures()
    except Exception as exc:  # noqa: BLE001
        print(f'[ERROR] Export failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
