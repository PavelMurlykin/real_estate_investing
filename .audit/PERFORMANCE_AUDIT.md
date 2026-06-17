# Backend Performance Review

## Metadata

- Review ID: PERF-20260617-full-project-refresh
- Date: 2026-06-17
- Reviewer: Codex
- Repository/branch: real_estate_investing / main
- Scope: Django backend views, ORM/query shape, forms, selector APIs, cache usage, document exports, imports/sync jobs, Docker runtime, tests
- Review type: static + safe local checks
- Environment: local Windows workspace, project virtualenv, no production-sized database benchmark
- Status: complete with measurement limitation

## Executive Summary

The highest-priority performance issues from the previous audit have been substantially improved. Saved calculation lists, catalog views, key-rate lists, and public selector APIs are now bounded or paginated; mortgage/property selector payloads are cached; homepage repeated queryset evaluation and bulk customer-calculation attach were improved; and the test suite covers several pagination behaviors.

The remaining meaningful risks are scaling and worker-availability risks rather than immediate local-test failures. Form selector caches still serialize full catalog/property dictionaries and use Django's default in-process cache unless a shared cache is configured. Word/Excel export and external synchronization still run synchronously in request handlers and can monopolize Gunicorn workers. Query-count/performance regression tests are still absent, and several search/filter paths need real PostgreSQL `EXPLAIN` validation before production-sized data.

## Commands And Evidence

| Command or source | Purpose | Result |
| --- | --- | --- |
| `git status --short` | Confirm working tree before review | Clean before audit edits |
| `.\.venv\Scripts\python.exe manage.py check` | Django sanity check | Passed, 0 issues |
| `.\.venv\Scripts\python.exe -m pytest` | Regression suite | 197 passed |
| `.\.venv\Scripts\python.exe -m pip check` | Dependency compatibility | No broken requirements |
| `rg -n "Paginator|paginate_by|page_obj"` | Find bounded list views | Saved calculations, catalogs, key rate, property/customer lists use pagination |
| `rg -n "cache.get_or_set|cache.delete_many|FORM_DATA_CACHE"` | Find selector caches/invalidation | Mortgage and property form selector payloads cached and invalidated by app signals |
| `rg -n "export_.*word|export_.*excel|BytesIO|worksheet.columns"` | Find synchronous export work | Word/Excel generation remains request-synchronous |
| `rg -n "urlopen|timeout|BANKI_MAX_PAGES"` | Find external sync I/O | Sync jobs use timeouts, but run inside admin POST requests |
| `docker compose config` | Runtime shape | Valid three-service stack; no background worker/cache service |

## Findings

### PERF-001: Saved Calculation Lists Render Unbounded QuerySets

- Severity: high
- Confidence: high
- Component: `mortgage`
- Category: database / rendering
- Status: closed
- Evidence:
  - `mortgage/views.py:1171` paginates saved mortgage calculations with `Paginator`.
  - `mortgage/views.py:1357` paginates saved trench calculations with `Paginator`.
  - Pagination context is passed at `mortgage/views.py:1189` and `mortgage/views.py:1365`.
  - Regression tests assert page size in `mortgage/tests.py:728` and `mortgage/tests.py:951`.
- Validation:
  - Full test suite passed: 197 tests.
- Residual risk:
  - No query-count tests exist yet for the paginated list pages.

### PERF-002: Catalog And Dictionary Views Materialize Full Tables

- Severity: high
- Confidence: high
- Component: `property.views.BaseCatalogView`, `bank.views.BankCatalogView`, `bank.views.KeyRateListView`
- Category: database / rendering
- Status: closed
- Evidence:
  - Shared catalog pagination is implemented in `property/views.py:421`.
  - Catalog rows are built from `page_obj.object_list` in `property/views.py:504` and `property/views.py:513`.
  - Bank catalog pagination exists in `bank/views.py:274`.
  - Key-rate list pagination exists in `bank/views.py:592`.
  - Tests assert page size in `property/tests.py:822`, `bank/tests.py:526`, and `bank/tests.py:1491`.
- Validation:
  - Full test suite passed: 197 tests.
- Residual risk:
  - Query-count tests are still missing for catalog pages with realistic related rows.

### PERF-003: Selector Payloads Are Cached But Still Full-Table And In-Process

- Severity: high
- Confidence: high
- Component: `mortgage`, `property`, Django cache settings
- Category: payload size / cache architecture
- Status: open
- Evidence:
  - Mortgage property selector payload is cached at `mortgage/views.py:363`, but `_build_property_form_data` still serializes all cities, districts, complexes, buildings, and properties at `mortgage/views.py:370`.
  - Mortgage program selector payload is cached at `mortgage/views.py:432`, but `_build_mortgage_program_form_data` still serializes all active banks/programs/regional limits at `mortgage/views.py:439`.
  - Property complex/property form payloads are cached at `property/views.py:1168` and `property/views.py:1555`, but `build_complex_form_location_payload` and `build_property_form_location_payload` still serialize full selector dictionaries at `property/views.py:57` and `property/views.py:85`.
  - Cache invalidation signals exist in `mortgage/apps.py:14` and `property/apps.py:14`.
  - No project `CACHES` setting was found, so Django uses default local memory cache behavior unless overridden externally.
- Impact:
  - Payload size and initial render time still grow with global catalog/property row count.
  - With Gunicorn workers, default local memory cache duplicates payloads per process and may produce stale selector data across workers after mutations.
- Root cause:
  - Current fix bounds repeated recomputation but keeps eager full-table JSON and lacks a shared production cache.
- Recommended fix:
  - Introduce lazy filtered selector endpoints for large child collections, especially properties/apartments and buildings.
  - Configure a shared cache backend for production if server-side cache remains the strategy.
  - Add payload-size and query-count tests for form GET paths with realistic fixture volume.
- Validation plan:
  - Capture response size and query count for `/mortgage/`, property create/update, and complex create/update before/after lazy loading.
  - Verify cache invalidation across all production workers when a shared cache is configured.

### PERF-004: Word/Excel Generation Runs Synchronously In Request Handlers

- Severity: medium
- Confidence: high
- Component: `mortgage`, `trench_mortgage`
- Category: CPU / memory / worker availability
- Status: open
- Evidence:
  - Calculator export branch runs in request handling at `mortgage/views.py:973`.
  - Trench Word/Excel export returns synchronously at `mortgage/views.py:1056` and `mortgage/views.py:1060`.
  - Market Word/Excel export returns synchronously at `mortgage/views.py:1095` and `mortgage/views.py:1097`.
  - Saved market exports run synchronously at `mortgage/views.py:1253` and `mortgage/views.py:1260`.
  - Saved trench exports run synchronously at `mortgage/views.py:1395` and `mortgage/views.py:1400`.
  - Word generation writes to `BytesIO` in `mortgage/word.py:68`.
  - Excel generation scans worksheet columns for widths in `mortgage/excel.py:461`.
  - Compose has `web`, `nginx`, and `db`; no background worker service exists.
- Impact:
  - Large schedules or concurrent exports can block Gunicorn workers and increase memory pressure.
- Root cause:
  - Report generation is implemented as synchronous request/response work.
- Recommended fix:
  - Keep synchronous exports only while data sizes are known small.
  - Add timing instrumentation around export functions.
  - Move large/frequent exports to a background job with authenticated download records.
  - Optimize Excel width calculation by tracking max widths while writing rows.
- Validation plan:
  - Add focused timing benchmark for representative 20-30 year market/trench schedules.
  - Add tests for async job ownership and download authorization when background generation is introduced.

### PERF-005: Repeated QuerySet Evaluation And Per-Row Writes In Hot Paths

- Severity: medium
- Confidence: medium
- Component: `homepage`, `mortgage`, `users`
- Category: ORM
- Status: closed
- Evidence:
  - Homepage now materializes `cities` once and `complexes` once in `homepage/views.py:14` and `homepage/views.py:33`.
  - Bulk customer-calculation attach uses preload + `bulk_create(ignore_conflicts=True)` in `mortgage/views.py:128`.
  - Ambiguous auth collisions now return `None` without a second `.filter(...).first()` branch in `users/backends.py:55`.
- Validation:
  - Full test suite passed: 197 tests.
- Residual risk:
  - Query-count tests are still absent, so regressions would be caught only functionally.

### PERF-006: Query-Sensitive Search And Filter Paths Need PostgreSQL Plan Validation

- Severity: medium
- Confidence: medium
- Component: `property`, `mortgage`, `bank`
- Category: database indexes / query plans
- Status: needs-data
- Evidence:
  - Common timestamp fields now have indexes (`mortgage/models.py:97`, `trench_mortgage/models.py:74`).
  - Base active/time fields are indexed in `core/models.py:10` and `core/models.py:16`.
  - Property and building ordering fields have indexes in `property/models.py:301` and `property/models.py:515`.
  - `PropertyListView` still supports `apartment_number__icontains` at `property/views.py:1348`; a regular btree index will not optimize arbitrary contains search in PostgreSQL.
  - Saved calculation filters/sorts operate on annotated and range-filtered values in `mortgage/utils.py` (static search found range/sort helpers), but no `EXPLAIN` evidence exists against production-sized data.
- Impact:
  - Larger datasets may still produce sequential scans for substring search, multi-column sort/filter combinations, and annotated saved-calculation filters.
- Root cause:
  - Indexes were added for obvious fields, but no PostgreSQL query-plan baseline exists.
- Recommended fix:
  - Capture `EXPLAIN (ANALYZE, BUFFERS)` for property list filters, calculation list filters, bank catalog filters, and homepage city view on production-like data.
  - Consider `pg_trgm`/GIN for `icontains` search or change UX to prefix/exact search.
  - Add only measured indexes to avoid unnecessary write overhead.
- Validation plan:
  - Store representative query plans in `.audit/` or documentation before adding migrations.

### PERF-007: Filter Option QuerySets And Query Counts Are Not Guarded By Tests

- Severity: low
- Confidence: high
- Component: `property`, `bank`, tests
- Category: observability / regression coverage
- Status: open
- Evidence:
  - Property list filter option querysets are built on every request in `property/views.py:1464`, `property/views.py:1468`, and neighboring context fields.
  - Bank catalog filter querysets are built per request in `bank/views.py:371` and `bank/views.py:374`.
  - Static test scan found pagination assertions, but no `assertNumQueries`, `django_assert_num_queries`, or `CaptureQueriesContext` usage.
- Impact:
  - Future template/context changes can reintroduce N+1 queries or unbounded option payloads without test failures.
- Recommended fix:
  - Add query-count tests for homepage, property list, bank catalog, mortgage calculator GET, saved calculation list, and customer detail.
  - Cache low-churn filter dictionaries if measured query counts matter.
- Validation plan:
  - Establish per-view query budgets and fail tests on meaningful regressions.

### PERF-008: External Synchronization Runs Sequentially Inside Admin Requests

- Severity: medium
- Confidence: high
- Component: `bank`
- Category: external I/O / worker availability
- Status: open
- Evidence:
  - Bank mortgage sync is invoked directly from `BankCatalogView.post` at `bank/views.py:117` and `bank/views.py:124`.
  - Key-rate sync is invoked directly from `KeyRateListView.post` at `bank/views.py:549`.
  - Download timeouts are 30 seconds in `bank/key_rate_sync.py:21`, `bank/mortgage_offer_sync.py:63`, and `bank/mortgage_offer_sync.py:64`.
  - Banki pagination can process up to `BANKI_MAX_PAGES = 20` at `bank/mortgage_offer_sync.py:65`.
  - Sequential download loop starts in `bank/mortgage_offer_sync.py:856`.
- Impact:
  - An administrator-triggered sync can block a web worker for a long time, especially during slow external responses or multi-page downloads.
- Root cause:
  - External ETL/sync is handled synchronously in request/response views.
- Recommended fix:
  - Move sync jobs to a management command or background worker before internet-facing/admin-heavy use.
  - Return a job/status page instead of holding the HTTP request open.
  - Record batch counts and duration in a sync run model/log entry.
- Validation plan:
  - Add tests for job creation and permission checks when background execution is introduced.
  - Add timing logs for current sync runs if synchronous mode remains for local testing.

## Remediation Plan

| Priority | Finding | Action | Expected impact | Validation |
| --- | --- | --- | --- | --- |
| P1 | PERF-003 | Replace full-table selector JSON with lazy filtered endpoints and/or configure shared cache | Lower form payload and DB/cache pressure | Query count + response size benchmarks |
| P1 | PERF-008 | Move external sync to background job/management flow | Protect web workers from slow external I/O | Job/status tests + timing logs |
| P2 | PERF-004 | Add export timing and background generation threshold | Bound CPU/memory impact from exports | Export benchmark |
| P2 | PERF-006 | Capture PostgreSQL query plans and add measured indexes | Improve large-table search/filter performance | `EXPLAIN` comparison |
| P3 | PERF-007 | Add query-count regression tests | Prevent N+1/unbounded context regressions | Query budget tests |

## AI Handoff

```yaml
performance_review:
  review_id: "PERF-20260617-full-project-refresh"
  status: "complete"
  summary:
    closed:
      - "PERF-001 saved calculation list pagination"
      - "PERF-002 catalog/key-rate pagination"
      - "PERF-005 repeated queryset/per-row write cleanup"
    open:
      - id: "PERF-003"
        severity: "high"
        topic: "full-table selector payloads and in-process cache"
      - id: "PERF-004"
        severity: "medium"
        topic: "synchronous Word/Excel generation"
      - id: "PERF-006"
        severity: "medium"
        topic: "PostgreSQL plan/index validation"
      - id: "PERF-007"
        severity: "low"
        topic: "missing query-count tests"
      - id: "PERF-008"
        severity: "medium"
        topic: "synchronous external sync in admin requests"
  validation:
    django_check: "passed"
    pytest: "197 passed"
    measurement_limitation: "No production-sized database; query plans not measured"
  next_actions:
    - "Measure response size/query count for /mortgage/ and property forms with large fixture data."
    - "Move bank/key-rate sync to background or management-command workflow."
    - "Add query-count regression tests for the hot list/detail/form pages."
```

## Open Questions

- What row counts should define the target production fixture: properties, buildings, complexes, saved calculations, bank programs, key-rate history?
- Is a shared cache backend planned for production, or should selector data move fully to lazy endpoints?
- How frequently will Word/Excel exports and bank sync jobs be used by administrators?
- Should background jobs be implemented with Celery/RQ/Django-Q, or should the first step be management commands plus manual operational workflow?

## Appendix

- Positive observations:
  - Main user-facing lists now use pagination.
  - Several detail/list querysets use `select_related` and `prefetch_related`.
  - Selector data has cache keys and model signal invalidation in `mortgage/apps.py` and `property/apps.py`.
  - Full test suite passes after recent role, upload, API, pagination, and cache changes.
- Measurement limitation:
  - No production-sized database was available, so remaining database/index findings are static hypotheses until validated with PostgreSQL query plans.
