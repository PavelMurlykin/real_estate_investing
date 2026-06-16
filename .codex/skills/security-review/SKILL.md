---
name: security-review
description: Application security review workflow for this real_estate_investing project. Use when Codex is asked to check application security, audit Django/Python backend code, review authentication or authorization, inspect data exposure, validate input handling, assess dependency or configuration risk, find vulnerabilities, or produce a structured security report with identified problems and remediation steps.
---

# Security Review

## Core Rule

Perform security review as defensive work only. Do not exploit live systems, bypass access controls, run destructive payloads, exfiltrate secrets, or perform scans against external targets unless the user explicitly authorizes a safe scope.

Treat findings as evidence-based. Verify from code, tests, configuration, logs, dependency metadata, or safe local checks. Clearly label unverified risks as hypotheses.

When reviewing or changing backend code in this project, also follow the local `backend` skill if it is available. When infrastructure or deployment configuration is in scope, also follow the local `infrastructure` skill if it is available.

## Workflow

1. Define scope:
   - Identify the feature, endpoint, job, model, configuration, dependency set, or user flow under review.
   - Record whether the task is a static review, safe dynamic check, dependency/config audit, or combined review.
   - Confirm boundaries before touching production-like systems, third-party targets, credentials, or destructive actions.

2. Gather context:
   - Check repository state before edits.
   - Use `rg` first for code search.
   - Inspect relevant Django views, URLs, serializers/forms, services, model methods, managers, middleware, permissions, templates, management commands, settings, environment examples, Docker/CI configuration, and tests.
   - Prefer existing local tests and fixtures for validation.

3. Review security controls:
   - Authentication: login/session handling, password reset, token storage, logout, session fixation, user enumeration, remember-me behavior, and MFA assumptions.
   - Authorization: object-level checks, role boundaries, ownership filters, admin-only actions, IDOR risks, queryset scoping, and privilege escalation paths.
   - Input and output handling: validation, normalization, unsafe deserialization, file upload controls, path traversal, template escaping, XSS, CSV/Excel formula injection, and SSRF.
   - Data protection: sensitive fields, PII exposure, logging of secrets, encryption assumptions, backups, exports, and least-privilege access.
   - Database and ORM safety: raw SQL, unsafe interpolation, migrations with data exposure risk, transaction boundaries, and multi-tenant isolation.
   - API and browser security: CSRF, CORS, security headers, cookies, rate limiting, pagination abuse, error leakage, and content type handling.
   - Dependencies and supply chain: vulnerable packages, unpinned versions, unsafe install scripts, abandoned packages, and CI secret exposure.
   - Configuration and deployment: `DEBUG`, `ALLOWED_HOSTS`, secret management, HTTPS settings, HSTS, proxy headers, container privileges, open ports, and environment-specific settings.
   - Background jobs and ETL: untrusted source handling, retry abuse, credential handling, safe temporary files, and idempotency around security-sensitive writes.
   - Observability and incident response: audit logs, tamper-resistant events, failed authorization visibility, and actionable security monitoring.

4. Validate safely:
   - Prefer unit/integration tests for authorization, CSRF behavior, input validation, and object scoping.
   - Use Django checks and dependency audit tools when available and safe.
   - For suspected vulnerabilities, create minimal local reproductions that do not target real users, real credentials, or external systems.
   - Never print secret values. If a secret exposure is found, redact the value and identify only the file, setting, key name, or data path.

5. Propose fixes:
   - Start with changes that remove the vulnerability at the correct trust boundary.
   - Tie every fix to evidence, exploitability, affected asset, expected impact, and a validation plan.
   - Prefer Django security conventions, project patterns, least privilege, deny-by-default authorization, explicit allowlists, and secure defaults.
   - Add or update tests when implementing changes, especially for authorization, validation, CSRF/CORS behavior, sensitive data filtering, and regression coverage.

6. Report:
   - Use `references/report-template.md` for security review reports.
   - Order findings by severity and exploitability.
   - Include file and line references for code-level findings.
   - Use stable finding IDs so humans and AI agents can refer to items unambiguously.
   - Include remediation steps that another agent can execute without guessing.

## Severity

- `critical`: Trivially exploitable issue that can cause remote code execution, account takeover, credential disclosure, broad PII/data breach, privilege escalation to admin, or production compromise.
- `high`: Realistic exploitation path with significant data exposure, cross-user access, financial/business impact, or bypass of important security controls.
- `medium`: Security weakness with meaningful impact but requiring specific conditions, limited access, or chained issues.
- `low`: Hardening gap, limited information disclosure, missing defense-in-depth, or observability issue with low immediate exploitability.

## Evidence Rules

- Do not include live secrets, tokens, passwords, private keys, or personal data in the report.
- Redact sensitive values as `<redacted>` and describe the source precisely.
- Distinguish confirmed vulnerabilities from theoretical concerns.
- Explain attacker preconditions and affected assets for every finding.
- Avoid overstating risk when exploitability is unknown.

## Validation Expectations

For each implemented fix, verify at least one of:

- A regression test fails before the fix and passes after it.
- A Django/system check or dependency audit no longer reports the issue.
- A safe local reproduction can no longer trigger the vulnerable behavior.
- A configuration check confirms secure settings are enforced.
- Logs or audit events now capture security-relevant failures without leaking sensitive data.

If validation cannot run locally, state exactly why and provide the command or procedure the user or another agent should run.
