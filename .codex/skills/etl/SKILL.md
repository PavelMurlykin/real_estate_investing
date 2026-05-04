---
name: etl
description: ETL workflow for this real_estate_investing project. Use when parsing data from websites, APIs, HTML pages, files, spreadsheets, or feeds; cleaning and normalizing real estate, bank, mortgage, customer, or location data; deduplicating records; validating source data; loading data into PostgreSQL through Django models; creating import jobs, management commands, parsers, scrapers, normalization pipelines, or pytest coverage for data ingestion. Enforce polite and lawful collection, repeatable transformations, idempotent loads, observability, database efficiency, and tests.
---

# ETL

## Core Workflow

Use this skill for parsing, normalization, and database loading.

1. Identify the source, allowed access method, data ownership, update frequency, and expected volume.
2. Separate extraction, normalization, validation, and loading into clear units.
3. Preserve raw source data or enough metadata to debug normalization decisions when practical.
4. Normalize into explicit typed records before touching Django models.
5. Make loads idempotent: rerunning the same input should not create duplicates or corrupt existing records.
6. Use Django ORM and PostgreSQL constraints for correctness, with bulk operations for volume.
7. Add pytest coverage for parser fixtures, normalization edge cases, duplicate handling, and DB side effects.

## Project Context

- Backend: Django with PostgreSQL.
- Data domain: real estate investing, property catalogs, locations, banks, mortgage programs, customers, and calculations.
- Prefer management commands or service modules for repeatable imports.
- Use the `backend` skill together with this skill when model/schema changes, permissions, or user-facing backend behavior are involved.

## Extraction

Read `references/extraction.md` before scraping websites, calling external APIs, downloading files, or parsing HTML.

Always check:

- Whether the source permits automated collection.
- Rate limits, retries, timeouts, and user agent behavior.
- Static HTML vs JavaScript-rendered content.
- Encoding, locale, currency, dates, decimals, and units.
- Stable selectors or API fields, with fixture coverage for expected source changes.

## Normalization

Read `references/normalization.md` before transforming raw source data into project records.

Always check:

- Required fields and default behavior for missing values.
- Canonical names, addresses, phone numbers, URLs, money, rates, dates, and percentages.
- Deduplication keys and conflict resolution.
- Validation errors that should reject a row vs warnings that should skip or quarantine it.
- Traceability from normalized records back to source rows/pages.

## Loading to PostgreSQL

Read `references/loading-postgres-django.md` before writing imported data to the database.

Always check:

- Idempotency and uniqueness constraints.
- Transaction boundaries and rollback behavior.
- Bulk create/update strategy.
- Query count and memory usage for large imports.
- Audit fields, timestamps, source metadata, and import summaries.

## Testing and Observability

Read `references/etl-testing-observability.md` before adding parser tests, import tests, logs, metrics, or job summaries.

New ETL functionality should test:

- Parser output from saved source fixtures.
- Normalization edge cases.
- Invalid and partial source data.
- Deduplication and idempotent reruns.
- Database side effects and transaction behavior.

## Verification

Use focused commands for the touched pipeline. Typical commands:

```powershell
python -m pytest path\to\etl_tests.py
python manage.py check
python manage.py makemigrations --check --dry-run
```

For live extraction, prefer dry-run commands and small limits before full ingestion.
