---
name: backend
description: Django backend development workflow for this real_estate_investing project. Use when implementing or reviewing Python/Django backend changes, models, views, forms, services, migrations, Django templates, PostgreSQL queries, security-sensitive logic, performance-sensitive database access, or pytest coverage. Enforce PostgreSQL-aware design, Django security conventions, efficient ORM usage, reuse of existing static JavaScript for templates, PEP 8 style, and tests for all new functionality.
---

# Backend

## Core Workflow

Use this skill for backend work in the Django/PostgreSQL application.

1. Inspect the existing app, model, view, form, URL, and template patterns before editing.
2. Keep changes scoped to the affected Django app unless a shared abstraction is already present or clearly needed.
3. Design data access for PostgreSQL and Django ORM behavior, not only for in-memory correctness.
4. Implement the smallest clear backend change, with migrations when models change.
5. Add or update pytest coverage for every new behavior.
6. Run focused checks first, then broader checks when the change touches shared behavior.

## Project Context

- Framework: Django.
- Database: PostgreSQL via `django.db.backends.postgresql`.
- Settings module: `real_estate_investing.settings`.
- Custom user model: `users.User`.
- Current apps include `bank`, `core`, `customer`, `homepage`, `location`, `mortgage`, `property`, `trench_mortgage`, and `users`.
- Existing JavaScript for Django templates lives in `static/js`, including `catalog.js` and `mortgage_form.js`.
- Current tests are mostly Django `TestCase`; new functionality must be covered with pytest. If pytest tooling is missing, add the minimal project configuration and dependencies needed for pytest-django.

## Implementation Rules

- Prefer existing local patterns over new architecture.
- Keep business logic out of templates; use forms, model methods, queryset helpers, or service functions when the surrounding app already has that shape.
- When developing Django templates, inspect `static/js` first and reuse existing JavaScript functions before adding new scripts, inline handlers, or duplicate client-side behavior.
- Use Django forms and validators for user input. Do not trust request data.
- Use `get_object_or_404`, permission checks, and ownership filters for object access.
- Wrap multi-row writes in `transaction.atomic()` when partial writes would corrupt state.
- Avoid raw SQL unless the ORM cannot express the query safely and clearly. If raw SQL is necessary, parameterize it.
- Keep migrations reviewable. Do not edit applied migrations unless the user explicitly asks and the project state makes it safe.
- Follow PEP 8 naming, imports, line length conventions visible in nearby files, and idiomatic Django style.

## Database Performance

Read `references/django-postgres-checklist.md` for detailed checks when a task touches query shape, list/detail views, reporting, filters, search, imports, bulk updates, or model schema.

Always check:

- Query counts for list and detail views that load related data.
- `select_related` for single-valued relationships and `prefetch_related` for many-valued relationships.
- Indexes for new foreign keys, filters, uniqueness constraints, ordering, and lookup-heavy fields.
- PostgreSQL constraints for invariants that must survive concurrency.
- Bulk operations for large imports or mass updates.
- Pagination or bounded result sets for user-facing lists.

## Security

Read `references/security-checklist.md` when a change touches authentication, authorization, sessions, file uploads, email, external URLs, admin behavior, object ownership, or user-entered HTML.

Always check:

- CSRF is preserved for unsafe requests.
- Authenticated and anonymous paths are deliberate.
- Users cannot access or mutate another user's objects through guessed IDs.
- Secrets remain in environment variables, never in code or tests.
- Redirects are constrained to safe internal URLs.
- Error messages do not leak secrets, tokens, or sensitive personal data.

## Testing With Pytest

Read `references/pytest-django.md` before adding pytest tests or project pytest configuration.

Expect new tests to cover:

- The successful path.
- Validation and permission failures.
- Database side effects.
- Important query/performance expectations when the change is query-sensitive.
- Regression cases for the bug or behavior being changed.

Prefer focused pytest tests near the app being changed. Use Django's test client, `pytest.mark.django_db`, model factories or compact fixture helpers, and `assertNumQueries` where query count is part of the requirement.

## Verification

Run the narrowest useful commands for the change. Typical commands:

```powershell
python manage.py makemigrations --check --dry-run
python -m pytest path\to\test_file.py
python -m pytest
python manage.py check
```

If pytest is not installed yet, add `pytest` and `pytest-django` to the project dependencies and create minimal pytest configuration before writing pytest-only tests.
