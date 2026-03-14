#!/usr/bin/env python
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import django
from django.apps import apps
from django.conf import settings
from django.core.management import call_command
from django.db import models, transaction

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


def _model_sort_key(model) -> tuple[str, str]:
    """Описание метода _model_sort_key.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        model: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    return model._meta.app_label, model._meta.model_name


def _dependency_graph(project_models):
    """Описание метода _dependency_graph.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        project_models: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    model_set = set(project_models)
    dependencies = {model: set() for model in project_models}
    dependents = {model: set() for model in project_models}

    for model in project_models:
        for field in model._meta.get_fields():
            if not isinstance(
                field, (models.ForeignKey, models.OneToOneField)
            ):
                continue
            remote_field = getattr(field, 'remote_field', None)
            remote_model = getattr(remote_field, 'model', None)
            if remote_model in model_set and remote_model != model:
                dependencies[model].add(remote_model)
                dependents[remote_model].add(model)

    return dependencies, dependents


def _topological_models(project_models):
    """Описание метода _topological_models.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        project_models: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    dependencies, dependents = _dependency_graph(project_models)
    in_degree = {model: len(dependencies[model]) for model in project_models}

    ready = sorted(
        (model for model, degree in in_degree.items() if degree == 0),
        key=_model_sort_key,
    )
    ordered = []

    while ready:
        model = ready.pop(0)
        ordered.append(model)

        for dependent in sorted(dependents[model], key=_model_sort_key):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                ready.append(dependent)
        ready.sort(key=_model_sort_key)

    if len(ordered) != len(project_models):
        remaining = [model for model in project_models if model not in ordered]
        remaining.sort(key=_model_sort_key)
        print(
            '[WARN] Circular model dependencies detected. '
            'Remaining models will be loaded '
            'in deterministic order.'
        )
        ordered.extend(remaining)

    return ordered


def _fixture_path_for_model(model) -> Path:
    """Описание метода _fixture_path_for_model.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        model: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    app_config = apps.get_app_config(model._meta.app_label)
    return (
        Path(app_config.path)
        / 'fixtures'
        / f'init_{model._meta.db_table}.json'
    )


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
            'Fixture is not UTF-8 encoded: '
            f'{fixture_path.relative_to(BASE_DIR)} '
            f'(byte position {exc.start}). '
            'Please re-save it as UTF-8.'
        ) from exc

    try:
        json.loads(text_content)
    except json.JSONDecodeError as exc:
        raise ValueError(
            'Fixture contains invalid JSON: '
            f'{fixture_path.relative_to(BASE_DIR)} '
            f'(line {exc.lineno}, column {exc.colno}).'
        ) from exc


def import_fixtures() -> int:
    """Описание метода import_fixtures.

    Выполняет прикладную операцию текущего модуля.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    project_models = sorted(_iter_project_models(), key=_model_sort_key)
    if not project_models:
        print('No project models found for import.')
        return 0

    ordered_models = _topological_models(project_models)
    loaded_count = 0
    missing_count = 0

    with transaction.atomic():
        for model in ordered_models:
            fixture_path = _fixture_path_for_model(model)
            if not fixture_path.exists():
                missing_count += 1
                continue

            _validate_utf8_json_fixture(fixture_path)
            call_command('loaddata', str(fixture_path), verbosity=0)
            print(f'[OK] Loaded {fixture_path.relative_to(BASE_DIR)}')
            loaded_count += 1

    print(
        'Import complete. '
        f'Loaded {loaded_count} fixture files. '
        f'Missing files: {missing_count}.'
    )
    return 0


def main() -> int:
    """Описание метода main.

    Выполняет прикладную операцию текущего модуля.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    try:
        return import_fixtures()
    except Exception as exc:  # noqa: BLE001
        print(f'[ERROR] Import failed: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
