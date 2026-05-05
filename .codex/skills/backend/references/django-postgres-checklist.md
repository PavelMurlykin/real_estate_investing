# Django/PostgreSQL Checklist

Use this checklist for model, migration, queryset, reporting, search, filtering, import, and list/detail view changes.

## ORM and Queries

- Start from the existing queryset pattern in the app.
- Use `select_related()` for `ForeignKey` and `OneToOneField` data rendered with each row.
- Use `prefetch_related()` or `Prefetch()` for many-to-many and reverse relations.
- Avoid per-row queries in loops, templates, form choice labels, and properties called by templates.
- Use `.only()` or `.defer()` only when profiling or payload size justifies the extra complexity.
- Use `Exists`, `Subquery`, `annotate`, and database aggregation for set-based logic instead of Python loops over large querysets.
- Use `iterator()`, `bulk_create()`, `bulk_update()`, or batched processing for large data operations.

## PostgreSQL Schema

- Add explicit indexes for fields used in frequent filters, joins, ordering, uniqueness, or partial lookups.
- Prefer database constraints for invariant rules: `UniqueConstraint`, `CheckConstraint`, non-null fields, and conditional unique constraints where appropriate.
- Consider race conditions when checking then inserting/updating. Use constraints plus `transaction.atomic()` when correctness matters.
- Avoid nullable fields unless the domain genuinely has an unknown or absent state.
- Use decimal fields for money and rates; avoid floats for financial values.

## Performance Review

- For user-facing lists, require pagination or another explicit bound.
- For detail views with related sections, inspect query count with realistic related data.
- Keep expensive calculated values out of templates unless they are precomputed or annotated.
- For search/filter endpoints, verify the expected indexes exist and the query cannot scan unbounded data unnecessarily.
- Avoid loading full model instances when `values()`, `values_list()`, or `exists()` answers the question.

## Migrations

- Generate migrations through the project virtual environment, for example `.\.venv\Scripts\python.exe manage.py makemigrations` on Windows/PowerShell.
- Run `.\.venv\Scripts\python.exe manage.py makemigrations --check --dry-run` after edits to ensure no missing migrations.
- Keep data migrations idempotent and chunked for large tables.
- Do not use app models directly in migrations; use `apps.get_model()`.
