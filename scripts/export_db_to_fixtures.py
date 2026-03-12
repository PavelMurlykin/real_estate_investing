#!/usr/bin/env python
from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "real_estate_investing.settings")

import django

django.setup()

from django.apps import apps
from django.conf import settings
from django.core.management import call_command


def _is_local_app(app_config) -> bool:
    app_path = Path(app_config.path).resolve()
    project_root = Path(settings.BASE_DIR).resolve()
    if app_path != project_root and project_root not in app_path.parents:
        return False
    if app_config.name.startswith("django."):
        return False
    if app_config.name.startswith("django_bootstrap5"):
        return False
    return True


def _iter_project_models():
    app_configs = [app_config for app_config in apps.get_app_configs() if _is_local_app(app_config)]
    for app_config in sorted(app_configs, key=lambda item: item.label):
        for model in app_config.get_models():
            meta = model._meta
            if meta.abstract or meta.proxy or meta.auto_created or meta.swapped:
                continue
            yield model


def export_fixtures() -> int:
    models = sorted(_iter_project_models(), key=lambda model: (model._meta.app_label, model._meta.model_name))
    if not models:
        print("No project models found for export.")
        return 0

    exported_count = 0
    for model in models:
        app_config = apps.get_app_config(model._meta.app_label)
        fixture_dir = Path(app_config.path) / "fixtures"
        fixture_dir.mkdir(parents=True, exist_ok=True)

        fixture_path = fixture_dir / f"init_{model._meta.db_table}.json"
        model_label = f"{model._meta.app_label}.{model._meta.model_name}"
        call_command(
            "dumpdata",
            model_label,
            format="json",
            indent=2,
            output=str(fixture_path),
            verbosity=0,
        )
        print(f"[OK] {model_label} -> {fixture_path.relative_to(BASE_DIR)}")
        exported_count += 1

    print(f"Export complete. Generated {exported_count} fixture files.")
    return 0


def main() -> int:
    try:
        return export_fixtures()
    except Exception as exc:  # noqa: BLE001
        print(f"[ERROR] Export failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
