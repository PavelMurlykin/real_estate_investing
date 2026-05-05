# Pytest-Django Guide

Use pytest for all new backend functionality.

## Minimal Configuration

If pytest is not configured, add the minimal setup:

```ini
[pytest]
DJANGO_SETTINGS_MODULE = real_estate_investing.settings
python_files = tests.py test_*.py *_tests.py
```

Add dependencies when missing:

```text
pytest
pytest-django
```

## Test Style

- Mark database tests with `@pytest.mark.django_db`.
- Keep tests near the app being changed unless the project establishes a separate tests package.
- Use compact fixtures for repeated model setup.
- Prefer explicit assertions over broad snapshot-like checks.
- Cover validation failures, permissions, side effects, and regressions.

## Common Patterns

```python
import pytest
from django.urls import reverse


@pytest.mark.django_db
def test_view_requires_login(client):
    response = client.get(reverse("some_app:private_view"))

    assert response.status_code == 302
```

```python
import pytest


@pytest.mark.django_db
def test_creates_expected_record(client, user):
    client.force_login(user)

    response = client.post("/path/", data={"name": "Example"})

    assert response.status_code in {200, 302}
    assert Model.objects.filter(name="Example").exists()
```

## Query Count Tests

Use query count tests when performance is a requirement or when fixing N+1 behavior:

```python
import pytest
from django.test.utils import CaptureQueriesContext
from django.db import connection


@pytest.mark.django_db
def test_list_query_count(client, django_assert_num_queries):
    with django_assert_num_queries(5):
        response = client.get("/path/")

    assert response.status_code == 200
```

If `django_assert_num_queries` is unavailable, use `CaptureQueriesContext`:

```python
with CaptureQueriesContext(connection) as queries:
    response = client.get("/path/")

assert response.status_code == 200
assert len(queries) <= 5
```

## Verification Commands

Run focused tests first:

```powershell
.\.venv\Scripts\python.exe -m pytest app\tests.py
```

Then broaden when the change touches shared behavior:

```powershell
.\.venv\Scripts\python.exe -m pytest
.\.venv\Scripts\python.exe manage.py check
```
