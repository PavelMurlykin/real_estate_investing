---
name: performance-review
description: Backend performance review workflow for Django/Python services in this real_estate_investing project. Use when Codex is asked to check backend performance, find bottlenecks, review ORM/database/query efficiency, inspect slow endpoints, profile CPU/memory/I/O behavior, evaluate caching or pagination, or produce a structured report with identified performance problems and remediation steps.
---

# Performance Review

## Core Rule

Treat performance findings as evidence-based. Measure when possible, inspect code when measurement is not available, and clearly label every unmeasured conclusion as a hypothesis.

When reviewing or changing backend code in this project, also follow the local `backend` skill if it is available.

## Workflow

1. Define scope:
   - Identify the feature, endpoint, job, command, model, query, or user flow under review.
   - Record whether the task is a static review, a measured benchmark, or both.
   - Avoid production-impacting load tests, destructive data changes, and expensive external calls unless the user explicitly approves them.

2. Gather context:
   - Check repository state before editing or benchmarking.
   - Inspect relevant Django views, serializers/forms, services, model managers, templates, management commands, Celery/background jobs, ETL code, settings, middleware, and tests.
   - Use `rg` first for code search.
   - Prefer existing test fixtures, factories, and local development data over inventing unrealistic workloads.

3. Measure when feasible:
   - Use existing tests, Django test client, management commands, or focused scripts to reproduce the slow path.
   - For database-heavy paths, capture query count, repeated query patterns, and representative SQL. Use `EXPLAIN` or `EXPLAIN ANALYZE` only against safe local/dev data.
   - For Python-heavy paths, use focused profiling (`cProfile`, timing around the target function, memory sampling if available).
   - Save commands, inputs, data assumptions, and observed results in the report.

4. Audit likely bottlenecks:
   - Database and ORM: N+1 queries, missing `select_related`/`prefetch_related`, unnecessary QuerySet evaluation, inefficient annotations, excessive joins, missing indexes, non-sargable filters, large result sets, unbounded ordering, per-row saves, and avoidable transactions.
   - API and rendering: slow serialization, repeated permission checks, large payloads, missing pagination, expensive template tags, synchronous file generation, and repeated static lookups.
   - Caching: cacheable reads without cache, stale or unsafe cache keys, missing invalidation, duplicated expensive computation, and overbroad cache scope.
   - External I/O: sequential API calls, missing timeouts, retry storms, synchronous network calls in request/response paths, and avoidable downloads.
   - CPU and memory: quadratic loops, repeated parsing, large in-memory lists, inefficient dataframe/spreadsheet handling, excessive object creation, and blocking work that should move to a background job.
   - Concurrency and reliability: long transactions, lock contention risks, race-prone cache writes, connection pool exhaustion, and request paths that can monopolize workers.
   - Observability: missing timings, query visibility, logging around batch sizes, metrics for background jobs, and alerts for known slow paths.

5. Propose fixes:
   - Start with the smallest safe change that removes the measured or most plausible bottleneck.
   - Tie every fix to evidence, expected impact, risk, and a validation plan.
   - Prefer project patterns and Django/PostgreSQL-aware solutions.
   - Add or update tests when implementing changes, especially for query counts, pagination behavior, cache correctness, or batch processing.

6. Report:
   - Use `references/report-template.md` for performance review reports.
   - Save project-level audit reports in `.audit/` at the repository root.
   - Keep findings ordered by severity and practical impact.
   - Include file and line references for code-level findings.
   - Use stable finding IDs so humans and AI agents can refer to items unambiguously.

## Severity

- `critical`: Can take down the service, corrupt performance-sensitive data, or create runaway resource usage under normal traffic.
- `high`: Likely user-visible slowness, timeout risk, large database load, or serious scaling limit.
- `medium`: Meaningful inefficiency with plausible production impact, but not an immediate outage risk.
- `low`: Localized cleanup, missing observability, or optimization opportunity with limited impact.

## Validation Expectations

For each implemented fix, verify at least one of:

- Reduced query count or improved representative SQL plan.
- Faster focused benchmark or test path.
- Lower memory footprint or smaller payload.
- Added pagination, batching, timeout, cache, or background processing behavior covered by tests.
- Improved observability that makes the bottleneck measurable in the future.

If validation cannot run locally, state exactly why and provide the command or procedure the user or another agent should run.
