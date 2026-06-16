# Backend Performance Review

## Metadata

- Review ID: PERF-20260616-full-project
- Date: 2026-06-16
- Reviewer: Codex
- Repository/branch: real_estate_investing / main
- Scope: Django backend views, ORM/query shape, forms, reports, imports/sync jobs, Docker runtime
- Review type: static + safe local checks
- Environment: local Windows workspace, project virtualenv, no production-sized database benchmark
- Status: complete with measurement limitation

## Executive Summary

The main performance risks are unbounded list/report views and full-table selector payloads. Mortgage calculation lists render all rows without pagination, several form views serialize full property/location/bank dictionaries into JSON on every request, and document exports are generated synchronously inside request handlers. The project has good use of `select_related`/`prefetch_related` in several detail/list paths and the full test suite passes, but there are no query-count or benchmark tests to catch regressions.

Start with pagination/bounds, cache or lazy-load selector dictionaries, and move heavy exports to background jobs when usage grows.

## Commands And Evidence

| Command or source | Purpose | Result |
| --- | --- | --- |
| `rg --files` | Map project files | Django apps, templates, Docker, tests found |
| `rg -n "paginate_by|Paginator|page_obj|calculations" templates mortgage property bank customer` | Check list pagination and templates | Customer/property main lists have pagination; mortgage saved calculation templates do not |
| `rg -n "list\\(|values\\(|select_related|prefetch_related|annotate|order_by|get_or_create"` | Find ORM materialization and query patterns | Multiple full-table `list(values(...))`, unbounded `all()`, per-row `get_or_create` found |
| `rg -n "db_index=True|indexes =|ordering|icontains"` | Review index hints and query-sensitive fields | Several frequently ordered/searched fields lack explicit indexes |
| `.\.venv\Scripts\python.exe manage.py check` | Django sanity check | Passed, 0 issues |
| `.\.venv\Scripts\python.exe -m pytest` | Regression suite | 173 passed |
| `.\.venv\Scripts\python.exe -m py_compile ...` | Compile reviewed modules | Passed |
| `docker compose config` | Validate Compose rendering | Valid config; no app-worker scaling/background job service defined |

## Findings

### PERF-001: Saved Calculation Lists Render Unbounded QuerySets

- Severity: high
- Confidence: high
- Component: `mortgage`
- Category: database
- Evidence:
  - `mortgage/views.py:1032-1040` builds `MortgageCalculation.objects.select_related(...).all()` with no slice or paginator.
  - `mortgage/views.py:1044` annotates and filters the full queryset.
  - `templates/mortgage/mortgage_list.html:63` iterates over every `calculation`.
  - `templates/mortgage/mortgage_list.html:110` includes the detail table for each row.
  - `mortgage/views.py:1211-1215` renders all trench calculations with `annotate_calculation_table_values(_get_trench_calculation_queryset()).order_by('-timestamp')`.
  - `templates/mortgage/trench_calculation_list.html:35` iterates all trench calculations.
- Impact:
  - Query, render time, and HTML size grow linearly with saved calculations; nested detail rows amplify response size.
- Root cause:
  - Function views pass full querysets directly to templates instead of using `Paginator` or `ListView`.
- Recommended fix:
  - Convert `calculation_list` and `trench_calculation_list` to paginated views (`Paginator` or `ListView`, `paginate_by=20`).
  - Render compact rows on the list page and lazy-load detail tables or move them to detail pages.
  - Keep city/filter choices bounded or cached.
- Validation plan:
  - Add tests for pagination context and max rows per page.
  - Add query-count tests for list views with realistic fixture volume.
- Risk:
  - Pagination changes may affect existing templates and customer attach workflow.
- Status: open

### PERF-002: Catalog And Dictionary Views Materialize Full Tables

- Severity: high
- Confidence: high
- Component: `property.views.BaseCatalogView`, `bank.views.BankCatalogView`, `bank.views.KeyRateListView`
- Category: database
- Evidence:
  - `property/views.py:169` starts catalog querysets with `config.model.objects.all()`.
  - `property/views.py:337-368` builds all rows by iterating `for obj in queryset`.
  - `property/views.py:407-415` stores all catalog rows in context.
  - `templates/property/catalog_form.html:120` iterates `rows`.
  - `bank/views.py:214` starts catalog querysets with `config.model.objects.all()`.
  - `bank/views.py:262` paginates only the bank tab; non-bank catalog tabs use the inherited full-row behavior.
  - `bank/views.py:571` materializes all key-rate rows with `rows = list(self.get_queryset())`.
- Impact:
  - Dictionary/catalog pages can become slow and memory-heavy as bank programs, aliases, credit limits, key rates, and property dictionaries grow.
- Root cause:
  - Shared catalog base class was built as `TemplateView` with manual row construction instead of paginated list behavior.
- Recommended fix:
  - Add pagination to `BaseCatalogView` for all model configs, not only the bank tab.
  - Paginate `KeyRateListView`.
  - Keep sortable/filter query parameters compatible with page links.
- Validation plan:
  - Add view tests asserting `page_obj` and bounded row counts for every catalog model tab.
- Risk:
  - Shared catalog templates need careful update to avoid breaking forms/edit/delete actions.
- Status: open

### PERF-003: Full Selector Dictionaries Are Serialized On Every Form Request

- Severity: high
- Confidence: high
- Component: `mortgage`, `property`
- Category: api
- Evidence:
  - `mortgage/views.py:283-322` builds property selector data by querying districts, complexes, buildings, all properties, and serializing lists.
  - `mortgage/views.py:343-396` builds bank/program selector data and loops through regional credit limits.
  - These helpers feed the calculator context on each request (`mortgage/views.py:612-613` from static search).
  - `property/views.py:1056-1085` builds city/district/metro/existing-complex lists for complex forms.
  - `property/views.py:1432-1474` builds region/city/district/developer/complex/building querysets and serializes cascade JSON for property forms.
  - No `cache.get`, `cache.get_or_set`, or project `CACHES` configuration found.
- Impact:
  - Every form load pays the full database and JSON serialization cost; payload size grows with the entire catalog, not the selected parent values.
- Root cause:
  - Cascade selects are preloaded eagerly instead of cached or fetched on demand.
- Recommended fix:
  - Cache stable selector payloads with explicit invalidation on relevant model changes.
  - Prefer lazy endpoint loading filtered by selected parent (`city`, `district`, `developer`, `complex`) for large tables.
  - Use `.values()` and selected fields consistently; avoid full model instances where JSON values are enough.
- Validation plan:
  - Add query-count tests for calculator/property form GET.
  - Add cache invalidation tests or endpoint tests for lazy cascades.
- Risk:
  - Cache invalidation must cover property/location/bank dictionary changes.
- Status: open

### PERF-004: Synchronous Word/Excel Generation Runs Inside Request Handlers

- Severity: medium
- Confidence: high
- Component: `mortgage`, `trench_mortgage`
- Category: cpu
- Evidence:
  - `mortgage/views.py:938-942` exports trench Word/Excel inside calculator POST.
  - `mortgage/views.py:977-979` exports market mortgage Word/Excel inside calculator POST.
  - `mortgage/views.py:1116-1123` exports saved market calculation documents inside detail POST.
  - `mortgage/views.py:1240-1245` exports saved trench calculation documents inside detail POST.
  - `mortgage/excel.py:103` creates workbooks in memory.
  - `mortgage/excel.py:461` iterates `worksheet.columns` to compute widths.
  - `mortgage/word.py:68` writes to `BytesIO`; `mortgage/word.py:101` opens the DOCX template.
  - Compose has `web`/`nginx`/`db` only; no background worker service is defined.
- Impact:
  - Concurrent exports can tie up Gunicorn workers, increase latency, and amplify memory pressure.
- Root cause:
  - Document generation is treated as a synchronous request/response operation.
- Recommended fix:
  - Move heavy exports to a background job queue once usage or document size grows.
  - Add download/status model for generated files or cache generated reports by calculation version.
  - Optimize Excel width calculation by tracking max lengths during row writes.
- Validation plan:
  - Add timing around export functions with representative schedules.
  - Add integration tests for async job creation when background queue is introduced.
- Risk:
  - Background job architecture adds storage, cleanup, and authorization requirements for generated files.
- Status: open

### PERF-005: Repeated QuerySet Evaluation And Per-Row Writes Exist In Hot Paths

- Severity: medium
- Confidence: medium
- Component: `homepage`, `mortgage`, `users`
- Category: orm
- Evidence:
  - `homepage/views.py:24` creates `cities` queryset and then may evaluate filtered variants at `homepage/views.py:33` and `homepage/views.py:36-38`.
  - `homepage/views.py:43-55` creates `complexes`; `homepage/views.py:58-64` iterates it for map data and `homepage/views.py:71` passes the queryset to the template for a second evaluation.
  - `mortgage/views.py:1015-1018` loops selected calculations and calls `_attach_calculation_to_customer`.
  - `mortgage/views.py:80` uses `CustomerCalculation.objects.get_or_create(...)` per selected calculation.
  - `users/backends.py:47-56` performs `.get(query)` and, on collision, performs a second `.filter(query).order_by('id').first()`.
- Impact:
  - Extra database round trips under homepage traffic, bulk customer attach actions, and login collision cases.
- Root cause:
  - Querysets are reused without materializing once, and bulk relation writes use per-row `get_or_create`.
- Recommended fix:
  - Materialize `complexes = list(...)` once when both map data and template rows need it.
  - Reduce selected-city lookup to a single intentional query path.
  - Bulk-create missing `CustomerCalculation` links after fetching existing IDs.
  - Reject ambiguous auth collisions instead of querying again.
- Validation plan:
  - Add query-count tests for homepage and bulk attach actions.
  - Add auth backend collision test.
- Risk:
  - Bulk create must preserve uniqueness constraint behavior.
- Status: open

### PERF-006: Query-Sensitive Fields Lack Explicit Index Strategy

- Severity: medium
- Confidence: medium
- Component: `core`, `property`, `mortgage`
- Category: database
- Evidence:
  - `core/models.py:11` defines `is_active`; `core/models.py:16` defines `created_at`; neither has explicit `db_index=True`.
  - `property/models.py:258` defines `RealEstateComplexBuilding.number`; model ordering at `property/models.py:297` orders by `number`.
  - `property/models.py:450` defines `Property.apartment_number`; model ordering at `property/models.py:505` orders by `apartment_number`.
  - `property/views.py:1253` filters `apartment_number__icontains`.
  - `mortgage/utils.py:118-139` filters calculation ranges over monetary/rate/term fields; `mortgage/utils.py:171` sorts by selected calculation fields.
- Impact:
  - Larger tables can shift to sequential scans for common list/search/sort/filter operations.
- Root cause:
  - Model defaults and view filters evolved without an explicit PostgreSQL index plan.
- Recommended fix:
  - Add btree indexes for common equality/order filters after validating with realistic `EXPLAIN`.
  - For `icontains`, consider PostgreSQL trigram indexes (`pg_trgm`) or change UX to prefix/exact search where appropriate.
  - Add indexes for calculation timestamp/filter fields if saved-calculation volume grows.
- Validation plan:
  - Run `EXPLAIN (ANALYZE, BUFFERS)` on representative list/filter queries against dev/prod-like data.
  - Add migrations and verify no excessive write penalty.
- Risk:
  - Extra indexes increase write cost and migration time; confirm with real query plans.
- Status: needs-data

### PERF-007: Filter Option QuerySets And Annotations Run On Every List Request

- Severity: low
- Confidence: high
- Component: `property`, `bank`
- Category: caching
- Evidence:
  - `property/views.py:943-948` queries developers/cities/classes/types for every complex list request.
  - `property/views.py:1360-1370` queries cities/developers/complexes/buildings/layouts for every property list request.
  - `property/views.py:843-844` annotates `buildings_count` for `RealEstateComplexListView` before knowing if the filter is needed.
  - `bank/views.py:371-372` queries banks/programs for bank-program filters on each request.
- Impact:
  - Extra queries on otherwise paginated list pages; cost grows with dictionary tables.
- Root cause:
  - Filter option data is generated synchronously per request and annotations are eager.
- Recommended fix:
  - Cache low-churn filter dictionaries with TTL and invalidation.
  - Apply `buildings_count` annotation only when display/filtering requires it.
  - Consider lazy-loading large filter lists for building/complex dropdowns.
- Validation plan:
  - Add query-count tests for list views before/after caching.
- Risk:
  - Cache keys must include active filters/permissions if access control is added.
- Status: open

## Remediation Plan

| Priority | Finding | Action | Expected impact | Validation |
| --- | --- | --- | --- | --- |
| P0 | PERF-001 | Add pagination and compact rows to saved calculation lists | Bound query/render/HTML size | Pagination and query-count tests |
| P0 | PERF-002 | Add shared pagination to catalog/key-rate views | Bound admin/catalog table work | Per-tab row count tests |
| P1 | PERF-003 | Cache or lazy-load selector dictionaries | Reduce DB and JSON work on form GET | Query-count and cache invalidation tests |
| P1 | PERF-004 | Move heavy exports to background jobs or cache generated files | Protect web workers from CPU/memory spikes | Export timing benchmarks |
| P2 | PERF-005 | Remove repeated queryset evaluation and per-row `get_or_create` | Reduce round trips | Query-count tests |
| P2 | PERF-006 | Add indexes based on real `EXPLAIN` plans | Improve large-table filter/sort paths | SQL plan comparison |
| P3 | PERF-007 | Cache filter option querysets and make annotations conditional | Trim list-page overhead | Query-count tests |

## AI Handoff

```yaml
performance_review:
  review_id: "PERF-20260616-full-project"
  scope: "Django backend views, ORM/query shape, forms, reports, Docker runtime"
  status: "complete"
  findings:
    - id: "PERF-001"
      severity: "high"
      confidence: "high"
      component: "mortgage calculation lists"
      category: "database"
      evidence:
        - "mortgage/views.py:1032-1040 unbounded MortgageCalculation queryset"
        - "templates/mortgage/mortgage_list.html:63 iterates all calculations"
        - "mortgage/views.py:1211-1215 unbounded trench list"
      recommended_fix:
        - "Add pagination and compact list rendering"
      validation:
        - "Pagination tests and query-count tests"
      status: "open"
    - id: "PERF-002"
      severity: "high"
      confidence: "high"
      component: "property/bank catalog views"
      category: "database"
      evidence:
        - "property/views.py:337-368 iterates full catalog queryset"
        - "bank/views.py:262 paginates only bank tab"
        - "bank/views.py:571 materializes all key-rate rows"
      recommended_fix:
        - "Add shared pagination to catalog/key-rate views"
      validation:
        - "Bounded row count tests"
      status: "open"
    - id: "PERF-003"
      severity: "high"
      confidence: "high"
      component: "mortgage/property selector data"
      category: "api"
      evidence:
        - "mortgage/views.py:283-322 full property selector serialization"
        - "mortgage/views.py:343-396 full bank/program selector serialization"
        - "property/views.py:1056-1085 and 1432-1474 full cascade data serialization"
      recommended_fix:
        - "Cache stable dictionaries or lazy-load filtered endpoints"
      validation:
        - "Query-count and cache invalidation tests"
      status: "open"
  next_actions:
    - "Implement pagination for saved calculations and catalog views."
    - "Add query-count tests around the hottest GET pages."
    - "Introduce cache/lazy endpoints for selector dictionaries."
```

## Open Questions

- What production-sized row counts should be used for benchmark fixtures: properties, buildings, saved calculations, bank programs, key-rate history?
- Which selector data must be available immediately on page load versus lazy-loaded after parent selection?
- Are Word/Excel exports expected to be frequent enough to justify a background worker now?

## Appendix

- Positive observations:
  - `PropertyListView` and `RealEstateComplexListView` use `paginate_by = 20`.
  - `CustomerListView` uses `paginate_by = 20`.
  - Several detail/list querysets already use `select_related` and `prefetch_related`.
  - `CustomerOwnedQuerysetMixin` uses nested `Prefetch` for customer detail calculation data.
  - `annotate_calculation_table_values` performs calculation table values database-side.
- Measurement limitation:
  - No production-sized database was available, so query plans and timings are static hypotheses unless backed by the local checks listed above.
