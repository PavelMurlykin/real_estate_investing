# Backend Performance Review Report Template

Use this template when producing a performance review report. Keep the structure stable so another AI agent can parse the report and continue the work.

````markdown
# Backend Performance Review

## Metadata

- Review ID: PERF-YYYYMMDD-short-topic
- Date: YYYY-MM-DD
- Reviewer: Codex
- Repository/branch: <repo and branch>
- Scope: <endpoint/job/module/user flow>
- Review type: static | measured | static+measured
- Environment: <local/dev/test/prod-like; database and data assumptions>
- Status: complete | partial | blocked

## Executive Summary

<Short human-readable summary of the highest-impact bottlenecks and recommended next step.>

## Commands And Evidence

| Command or source | Purpose | Result |
| --- | --- | --- |
| `<command>` | <why it was run> | <key result or "not run: reason"> |

## Findings

### PERF-001: <short title>

- Severity: critical | high | medium | low
- Confidence: high | medium | low
- Component: <app/module/endpoint/job>
- Category: database | orm | api | caching | external-io | cpu | memory | concurrency | observability | other
- Evidence:
  - <file:line, query count, SQL plan detail, timing, profile result, log line, or static code observation>
- Impact:
  - <user-visible, infrastructure, data volume, or scaling effect>
- Root cause:
  - <why the bottleneck happens>
- Recommended fix:
  - <specific implementation plan>
- Validation plan:
  - <test, benchmark, query count, EXPLAIN, or manual check>
- Risk:
  - <behavioral, migration, cache invalidation, rollout, or data-risk note>
- Status: open | fixed | accepted-risk | needs-data

## Remediation Plan

| Priority | Finding | Action | Expected impact | Validation |
| --- | --- | --- | --- | --- |
| P0/P1/P2 | PERF-001 | <fix> | <impact> | <check> |

## AI Handoff

```yaml
performance_review:
  review_id: "PERF-YYYYMMDD-short-topic"
  scope: "<scope>"
  status: "complete|partial|blocked"
  findings:
    - id: "PERF-001"
      severity: "critical|high|medium|low"
      confidence: "high|medium|low"
      component: "<component>"
      category: "database|orm|api|caching|external-io|cpu|memory|concurrency|observability|other"
      evidence:
        - "<specific evidence>"
      recommended_fix:
        - "<specific action>"
      validation:
        - "<command or check>"
      status: "open|fixed|accepted-risk|needs-data"
  next_actions:
    - "<ordered next action>"
```

## Open Questions

- <Question, missing data, or environment dependency>

## Appendix

<Optional raw timings, query summaries, EXPLAIN notes, profile excerpts, or payload samples. Keep excerpts short and relevant.>
````

## Reporting Rules

- Do not invent timings, query counts, or production impact.
- Use `not measured` when evidence is static only.
- Prefer concrete file references over broad statements.
- Group duplicate symptoms under one finding when they share a root cause.
- Keep remediation steps executable by a future agent.
