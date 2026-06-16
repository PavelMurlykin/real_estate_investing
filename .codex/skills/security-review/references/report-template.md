# Application Security Review Report Template

Use this template when producing a security review report. Keep the structure stable so another AI agent can parse the report and continue the work.

````markdown
# Application Security Review

## Metadata

- Review ID: SEC-YYYYMMDD-short-topic
- Date: YYYY-MM-DD
- Reviewer: Codex
- Repository/branch: <repo and branch>
- Scope: <endpoint/job/module/configuration/user flow>
- Review type: static | dynamic-local | dependency | configuration | combined
- Environment: <local/dev/test/prod-like; relevant assumptions>
- Authorization: <what the user authorized; note if no live testing was authorized>
- Status: complete | partial | blocked

## Executive Summary

<Short human-readable summary of the highest-risk issues and recommended next step.>

## Scope And Threat Model

- Assets reviewed: <accounts, PII, financial data, admin actions, files, credentials, etc.>
- Primary attacker model: anonymous | authenticated user | staff user | compromised integration | supply-chain | other
- Out of scope: <targets, systems, checks, or data not reviewed>
- Assumptions: <trust boundaries, deployment assumptions, test data assumptions>

## Commands And Evidence

| Command or source | Purpose | Result |
| --- | --- | --- |
| `<command>` | <why it was run> | <key result or "not run: reason"> |

## Findings

### SEC-001: <short title>

- Severity: critical | high | medium | low
- Confidence: high | medium | low
- Component: <app/module/endpoint/job/config>
- Category: authentication | authorization | injection | xss | csrf | ssrf | file-upload | data-exposure | secrets | dependencies | configuration | logging | other
- Status: open | fixed | accepted-risk | needs-data
- Evidence:
  - <file:line, setting, dependency advisory, test result, safe local reproduction, or static code observation>
- Affected assets:
  - <data, account, role, system, or business process>
- Attacker preconditions:
  - <anonymous access, authenticated role, crafted input, compromised token, etc.>
- Impact:
  - <what an attacker could do>
- Root cause:
  - <why the vulnerability exists>
- Recommended fix:
  - <specific implementation plan>
- Validation plan:
  - <test, command, dependency audit, config check, or manual verification>
- Residual risk:
  - <remaining limitation, rollout concern, or monitoring need>

## Remediation Plan

| Priority | Finding | Action | Expected risk reduction | Validation |
| --- | --- | --- | --- | --- |
| P0/P1/P2 | SEC-001 | <fix> | <risk reduction> | <check> |

## AI Handoff

```yaml
security_review:
  review_id: "SEC-YYYYMMDD-short-topic"
  scope: "<scope>"
  status: "complete|partial|blocked"
  authorization: "<authorized scope>"
  findings:
    - id: "SEC-001"
      severity: "critical|high|medium|low"
      confidence: "high|medium|low"
      component: "<component>"
      category: "authentication|authorization|injection|xss|csrf|ssrf|file-upload|data-exposure|secrets|dependencies|configuration|logging|other"
      status: "open|fixed|accepted-risk|needs-data"
      evidence:
        - "<specific redacted evidence>"
      affected_assets:
        - "<asset>"
      attacker_preconditions:
        - "<precondition>"
      recommended_fix:
        - "<specific action>"
      validation:
        - "<command or check>"
      residual_risk:
        - "<remaining risk or monitoring need>"
  next_actions:
    - "<ordered next action>"
```

## Open Questions

- <Question, missing data, authorization boundary, or environment dependency>

## Appendix

<Optional dependency audit excerpts, redacted config snippets, safe reproduction notes, or test output. Keep excerpts short and avoid sensitive values.>
````

## Reporting Rules

- Do not include live secrets, tokens, passwords, keys, personal data, or exploit payloads that enable misuse.
- Use `<redacted>` for sensitive values and identify the source by file, setting, key name, or data path.
- Use `not tested` when live or dynamic validation was outside the authorized scope.
- Prefer concrete file references and safe local evidence over broad claims.
- Group duplicate symptoms under one finding when they share a root cause.
- Keep remediation steps executable by a future agent.
