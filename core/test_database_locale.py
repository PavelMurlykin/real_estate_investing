"""Verify PostgreSQL prerequisites for Cyrillic catalog operations."""

import pytest
from django.db import connection


@pytest.mark.django_db
def test_postgresql_maps_cyrillic_case_for_catalog_lookups():
    """Report a broken test locale before missing rows resemble API defects."""
    assert connection.vendor == 'postgresql'
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT UPPER(%s) = UPPER(%s), UPPER(%s) LIKE UPPER(%s)',
            ['Семейная Ёлка', 'семейная ёлка', 'Тест Банк', '%тест%'],
        )
        equality_works, search_works = cursor.fetchone()
    assert equality_works and search_works, (
        'PostgreSQL must support Unicode case mapping for Cyrillic catalogs. '
        'Run scripts/run-backend-tests.ps1. For a new isolated PostgreSQL 18 '
        'cluster use --encoding=UTF8 --locale-provider=builtin '
        '--builtin-locale=C.UTF-8; --no-locale alone uses ASCII-only '
        'case mapping.'
    )
