# Application Security Review

## Metadata

- Review ID: SEC-20260616-full-project
- Date: 2026-06-16
- Reviewer: Codex
- Repository/branch: real_estate_investing / main
- Scope: Django application, auth flows, business CRUD, JSON APIs, settings, dependencies, Docker Compose, nginx
- Review type: static + dynamic-local + dependency/configuration
- Environment: local Windows workspace, project virtualenv, local `.env` loaded by Django/Docker Compose
- Authorization: local defensive review only; no live external scanning or exploitation
- Status: complete with dependency-audit limitation

## Executive Summary

The largest risk is missing access control on business-critical areas. `property`, `bank`, mortgage calculation views, and JSON APIs are reachable without explicit authentication or authorization, while saved mortgage calculations have no owner field and are retrieved by raw primary key. Production hardening is also incomplete: `check --deploy` reports missing HTTPS/HSTS/secure-cookie settings, `SECRET_KEY` can fall back to an empty string in Django settings, and Docker Compose still contains unsafe secret fallbacks.

Immediate remediation should start with authentication/authorization on all private business views, ownership scoping for saved calculations, and production security settings.

## Scope And Threat Model

- Assets reviewed: user accounts, customers, mortgage calculations, property/catalog data, bank programs, uploaded media, secrets/configuration, deployment stack.
- Primary attacker model: anonymous internet user, authenticated low-privilege user, supply-chain/deployment mistake.
- Out of scope: live production testing, external vulnerability database query, destructive payloads, real credential validation.
- Assumptions: property/bank/catalog/mortgage/customer data is private business data unless explicitly declared public.

## Commands And Evidence

| Command or source | Purpose | Result |
| --- | --- | --- |
| `git status --short` | Confirm working tree before review | Clean before report edits |
| `rg --files` | Map repository | Django apps, Docker, templates, tests, existing audit files found |
| `rg -n "login_required|LoginRequiredMixin|permission_required" property bank mortgage property/api_urls.py` | Find explicit access controls | No matches in property/bank/mortgage/API views; customer views do use `LoginRequiredMixin` |
| `rg -n "csrf_exempt|mark_safe|eval|exec|cursor|raw|subprocess"` | Look for high-risk code patterns | No confirmed unsafe patterns in app code; external sync uses `urlopen` with timeouts |
| `.\.venv\Scripts\python.exe manage.py check` | Django sanity check | Passed, 0 issues |
| `.\.venv\Scripts\python.exe manage.py check --deploy` | Django production security check | 4 warnings: missing HSTS, SSL redirect, secure session cookie, secure CSRF cookie |
| `.\.venv\Scripts\python.exe -m pytest` | Regression suite | 173 passed |
| `.\.venv\Scripts\python.exe -m pip check` | Dependency compatibility | No broken requirements |
| `.\.venv\Scripts\python.exe -m pip_audit` | Dependency vulnerability audit | Not run: `pip_audit` module is not installed |
| `docker compose config` | Validate rendered Compose configuration | Valid config, but local `.env` values for `SECRET_KEY`/DB credentials are expanded into output; values redacted in this report |
| `.dockerignore` | Build context review | `.env`, `.git`, `.venv`, caches, staticfiles are excluded |

## Findings

### SEC-001: Business CRUD And Sync Views Lack Explicit Authentication

- Severity: critical
- Confidence: high
- Component: `property`, `bank`, `mortgage`
- Category: authorization
- Status: open
- Evidence:
  - `property/views.py:75` defines `BaseCatalogView(TemplateView)` with no auth mixin; it handles generic catalog create/update/delete operations.
  - `property/views.py:765`, `property/views.py:778`, `property/views.py:791`, `property/views.py:1124`, `property/views.py:1134`, `property/views.py:1168`, `property/views.py:1523`, `property/views.py:1549`, `property/views.py:1584` define property/developer/complex create/update/delete views without `LoginRequiredMixin` or permission mixins.
  - `bank/views.py:30`, `bank/views.py:482`, `bank/views.py:486`, `bank/views.py:523` define bank catalog, create/update, and key-rate sync views without auth mixins.
  - `mortgage/views.py:542`, `mortgage/views.py:1009`, `mortgage/views.py:1081`, `mortgage/views.py:1088`, `mortgage/views.py:1211`, `mortgage/views.py:1227`, `mortgage/views.py:1234` define calculator/list/detail/delete views without `@login_required`.
  - Contrast: `customer/views.py:28`, `customer/views.py:110`, `customer/views.py:305` use `LoginRequiredMixin`.
- Affected assets:
  - Property catalog, bank catalog, key-rate sync, mortgage calculations, generated reports.
- Attacker preconditions:
  - Anonymous HTTP access and valid CSRF token from the public site for unsafe POST forms.
- Impact:
  - Anonymous users can potentially create, edit, delete, or trigger synchronization of business data.
- Root cause:
  - Private/admin workflows are implemented as regular class/function views without a shared access-control base.
- Recommended fix:
  - Add `LoginRequiredMixin` to all private class-based views and `@login_required` to private function views.
  - Add stronger role checks (`PermissionRequiredMixin`, `UserPassesTestMixin`, or Django permissions) for admin/catalog/sync/delete operations.
  - Split public read-only pages from private write/admin pages.
- Validation plan:
  - Add tests asserting anonymous users receive 302/403 for every private GET/POST endpoint.
  - Add tests asserting non-staff users cannot run catalog delete/sync actions.
- Residual risk:
  - Access-control policy needs product confirmation for which catalog/list pages are intentionally public.

### SEC-002: Saved Mortgage Calculations Are Not Owner Scoped

- Severity: critical
- Confidence: high
- Component: `mortgage`, `trench_mortgage`, `customer`
- Category: authorization
- Status: open
- Evidence:
  - `mortgage/models.py:15` defines `MortgageCalculation` without a `user`/owner field.
  - `trench_mortgage/models.py:10` defines `TrenchMortgageCalculation` without a `user`/owner field.
  - `mortgage/views.py:1032` loads all `MortgageCalculation` rows for the list.
  - `mortgage/views.py:1083` deletes `MortgageCalculation` by `pk` only.
  - `mortgage/views.py:1090` opens calculation detail by `pk` only.
  - `mortgage/views.py:1015` attaches selected calculation IDs to a customer using `MortgageCalculation.objects.filter(pk__in=selected_ids)` with no owner scope.
  - `mortgage/views.py:1229` and `mortgage/views.py:1236` access trench calculations by `pk` only.
- Affected assets:
  - Saved mortgage calculations, customer calculation links, financial scenario data.
- Attacker preconditions:
  - Anonymous or authenticated user can guess or enumerate calculation IDs.
- Impact:
  - Cross-user read/delete/link of saved calculations; possible leakage of financial scenario data.
- Root cause:
  - Calculation models are global records and views do not filter by `request.user`.
- Recommended fix:
  - Add `user = ForeignKey(settings.AUTH_USER_MODEL, ...)` to calculation models.
  - Scope list/detail/delete/queryset and customer attach flows by `user=request.user`.
  - Decide migration strategy for existing rows, preferably assigning legacy rows to an admin or marking them unowned and staff-only.
- Validation plan:
  - Add tests for user A not seeing, exporting, deleting, or linking user B calculations.
  - Add migration tests or data migration review for legacy records.
- Residual risk:
  - Existing unowned data needs a deliberate cleanup/ownership policy.

### SEC-003: Public JSON APIs Expose Internal Property Hierarchy And Objects

- Severity: high
- Confidence: high
- Component: `property.api_urls`, `mortgage`
- Category: data-exposure
- Status: open
- Evidence:
  - `real_estate_investing/urls.py:19` mounts `path('api/', include('property.api_urls'))`.
  - `property/api_urls.py:9`, `property/api_urls.py:25`, `property/api_urls.py:41`, `property/api_urls.py:81` define bare JSON function views.
  - `property/api_urls.py:22`, `property/api_urls.py:38`, `property/api_urls.py:78`, `property/api_urls.py:104` return lists through `JsonResponse`.
  - `mortgage/views.py:984` defines `property_cost_api`; `mortgage/views.py:1006` returns property payload by `pk`.
- Affected assets:
  - City/district/complex/building hierarchy, property payload, pricing-related fields.
- Attacker preconditions:
  - Anonymous access to API routes.
- Impact:
  - Bulk enumeration of catalog and property metadata; supports scraping and later IDOR attempts.
- Root cause:
  - Internal cascade selector APIs are mounted publicly without access control or rate limiting.
- Recommended fix:
  - Add `@login_required` or DRF permission classes.
  - If any endpoint must stay public, document it, minimize fields, add cache/rate limits, and use explicit allowlists.
- Validation plan:
  - Add anonymous-access tests for each API endpoint.
  - Add field-level tests to ensure private fields are never serialized.
- Residual risk:
  - Business decision needed on whether property catalog data is public marketing data or private operator data.

### SEC-004: Production Security Settings And Secret Handling Are Weak

- Severity: high
- Confidence: high
- Component: Django settings, Docker Compose, nginx
- Category: configuration
- Status: open
- Evidence:
  - `real_estate_investing/settings.py:30` sets `SECRET_KEY = os.getenv('SECRET_KEY', '')`.
  - `real_estate_investing/settings.py` has no `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, or `SECURE_PROXY_SSL_HEADER`.
  - `manage.py check --deploy` reports `security.W004`, `security.W008`, `security.W012`, `security.W016`.
  - `compose.yaml:8`, `compose.yaml:27`, `compose.yaml:32` contain unsafe fallback values for DB password and `SECRET_KEY`.
  - `docker compose config` expands local `SECRET_KEY`, `DB_USER`, and `DB_PASSWORD` values from `.env`; values are redacted here.
  - `docker/nginx/default.conf:29` forwards `X-Forwarded-Proto`, but Django does not set `SECURE_PROXY_SSL_HEADER`.
- Affected assets:
  - Sessions, CSRF tokens, password-reset tokens, deployment secrets, transport confidentiality.
- Attacker preconditions:
  - Misconfigured production deployment or leaked Compose output/logs.
- Impact:
  - Weak or missing signing key, cookies over HTTP, missing HSTS, accidental secret disclosure in generated config/logs.
- Root cause:
  - Development-friendly defaults are not separated from production-required settings.
- Recommended fix:
  - Fail fast when `SECRET_KEY` is empty in non-debug environments.
  - Remove unsafe secret fallbacks from Compose; require `.env`/secrets for production.
  - Add production security settings gated by `DEBUG`.
  - Set `SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')` when behind nginx/proxy.
  - Treat any shared local secret values as compromised and rotate them.
- Validation plan:
  - Run `manage.py check --deploy` and expect no security warnings.
  - Run `docker compose config` and confirm no unsafe defaults are used when required env vars are absent.
- Residual risk:
  - TLS termination and production domain/origin configuration require deployment-specific validation.

### SEC-005: Password And Abuse Controls Are Missing

- Severity: high
- Confidence: high
- Component: `users`, Django settings
- Category: authentication
- Status: open
- Evidence:
  - `real_estate_investing/settings.py` has no `AUTH_PASSWORD_VALIDATORS`.
  - `users/views.py:10` registration and `users/views.py:39` login use standard views with no rate limiting.
  - `users/urls.py:37` and `users/urls.py:54` expose password-reset and confirm views.
  - `requirements.txt` has no `django-axes`, `django-ratelimit`, or equivalent throttling package.
- Affected assets:
  - User accounts and password-reset email flow.
- Attacker preconditions:
  - Anonymous access to login/register/reset endpoints.
- Impact:
  - Weak passwords, login brute force, account enumeration pressure, reset-email flooding.
- Root cause:
  - Django password validators and rate-limit/lockout controls are not configured.
- Recommended fix:
  - Add Django's standard password validators.
  - Add `django-axes` or equivalent rate limiting for login/password reset/registration.
  - Consider CAPTCHA or progressive challenges after repeated failures.
- Validation plan:
  - Add tests for weak password rejection.
  - Add tests or integration checks for throttled login/reset attempts.
- Residual risk:
  - Abuse thresholds should be tuned to real traffic.

### SEC-006: Authentication Backend Resolves Ambiguous Identifier Collisions Unsafe

- Severity: high
- Confidence: medium
- Component: `users.backends.EmailOrPhoneBackend`
- Category: authentication
- Status: open
- Evidence:
  - `users/backends.py:39` builds `Q(email__iexact=login_value)`.
  - `users/backends.py:47` calls `.get(query)`.
  - `users/backends.py:51` handles `MultipleObjectsReturned`.
  - `users/backends.py:52-56` selects `.order_by('id').first()` and continues password checking.
- Affected assets:
  - User sessions and account authentication.
- Attacker preconditions:
  - A crafted login identifier that can match more than one user through email/phone OR conditions.
- Impact:
  - Ambiguous identity resolution; possible wrong-account login attempt handling and unnecessary second query.
- Root cause:
  - Collision branch chooses a user instead of rejecting ambiguous identifiers.
- Recommended fix:
  - Return `None` on `MultipleObjectsReturned` and log a redacted warning.
  - Normalize and store email/phone canonically; use exact indexed lookups where possible.
- Validation plan:
  - Add a test with two matching users and assert authentication fails.
- Residual risk:
  - Existing data should be checked for email/phone normalization drift.

### SEC-007: Upload And Request Body Limits Are Incomplete

- Severity: medium
- Confidence: high
- Component: `property`, settings, nginx
- Category: file-upload
- Status: open
- Evidence:
  - `property/models.py:117`, `property/models.py:471`, `property/models.py:477`, `property/models.py:483` define image fields.
  - `property/forms.py:103`, `property/forms.py:104`, `property/forms.py:107`, `property/forms.py:262` use file inputs without visible size/type validators.
  - `real_estate_investing/settings.py:110` sets `DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000`.
  - `real_estate_investing/settings.py` has no `FILE_UPLOAD_MAX_MEMORY_SIZE` or `DATA_UPLOAD_MAX_MEMORY_SIZE`.
  - `docker/nginx/default.conf:9` sets `client_max_body_size 20m`.
- Affected assets:
  - Media storage, memory, request workers, image processing.
- Attacker preconditions:
  - Access to property/complex image upload forms.
- Impact:
  - Oversized or unexpected image uploads can consume resources; high field-count limit widens DoS surface.
- Root cause:
  - Validation and upload limits are split across nginx/Django and not fully enforced at form/model level.
- Recommended fix:
  - Add reusable validators for extension, MIME/content type, and max size.
  - Set Django upload/body size limits consistently with nginx.
  - Lower or justify `DATA_UPLOAD_MAX_NUMBER_FIELDS`.
- Validation plan:
  - Add tests for rejected oversized and wrong-type uploads.
  - Verify Django and nginx limits agree.
- Residual risk:
  - Image decoding vulnerabilities depend on Pillow/security updates; automate dependency scans.

### SEC-008: Email Reset Defaults Allow Plain SMTP

- Severity: medium
- Confidence: high
- Component: Django settings, password reset
- Category: configuration
- Status: open
- Evidence:
  - `real_estate_investing/settings.py:130` defaults `EMAIL_HOST` to localhost.
  - `real_estate_investing/settings.py:131` defaults `EMAIL_PORT` to 25.
  - `real_estate_investing/settings.py:134-145` default both `EMAIL_USE_TLS` and `EMAIL_USE_SSL` to false.
  - `users/urls.py:37-58` wires Django password-reset views.
- Affected assets:
  - Password-reset links and email credentials.
- Attacker preconditions:
  - Production SMTP configured without TLS/SSL or traffic visible to an attacker.
- Impact:
  - Password-reset links can traverse SMTP plaintext.
- Root cause:
  - Secure email transport is optional and not guarded for production.
- Recommended fix:
  - Require TLS or SSL for non-debug SMTP configuration.
  - Add an `ImproperlyConfigured` guard if both TLS and SSL are true, or both are false in production.
- Validation plan:
  - Add settings tests for production email transport requirements.
- Residual risk:
  - SMTP provider certificate policy must be validated outside the app.

### SEC-009: Dependency Vulnerability Scanning Is Not Available Locally

- Severity: low
- Confidence: high
- Component: dependencies/CI
- Category: dependencies
- Status: needs-data
- Evidence:
  - `requirements.txt` pins direct dependencies, including Django, gunicorn, Pillow, openpyxl, psycopg2-binary.
  - `.\.venv\Scripts\python.exe -m pip check` passed.
  - `.\.venv\Scripts\python.exe -m pip_audit` failed because `pip_audit` is not installed.
  - `requirements.txt` has no `pip-audit`, `bandit`, or similar security tooling.
- Affected assets:
  - Application supply chain.
- Attacker preconditions:
  - Vulnerable dependency version or compromised package path.
- Impact:
  - Known vulnerable packages may go unnoticed.
- Root cause:
  - Compatibility checks exist, but vulnerability scanning is not part of local/CI workflow.
- Recommended fix:
  - Add `pip-audit` or an equivalent dependency scanner to development/CI tooling.
  - Add `bandit` or a Django-aware SAST step for security-sensitive changes.
  - Consider hash-locked dependency management for production builds.
- Validation plan:
  - Run `python -m pip_audit -r requirements.txt` in CI and fail on actionable vulnerabilities.
- Residual risk:
  - Vulnerability data changes over time and must be checked continuously.

## Remediation Plan

| Priority | Finding | Action | Expected risk reduction | Validation |
| --- | --- | --- | --- | --- |
| P0 | SEC-001 | Add auth/permission controls to property, bank, mortgage, API write/private endpoints | Prevent anonymous business-data mutation | Anonymous GET/POST tests return 302/403 |
| P0 | SEC-002 | Add owner field and user-scoped querysets for saved calculations | Prevent cross-user read/delete/link | User A cannot access user B calculations |
| P1 | SEC-003 | Protect or minimize JSON APIs | Reduce enumeration/data exposure | Anonymous API tests and field allowlist tests |
| P1 | SEC-004 | Harden production settings and remove unsafe Compose fallbacks | Reduce deployment compromise risk | `manage.py check --deploy` clean |
| P1 | SEC-005 | Add password validators and rate limiting | Reduce account abuse | Weak password and throttle tests |
| P2 | SEC-006 | Reject ambiguous auth backend matches | Remove wrong-identity ambiguity | Collision regression test |
| P2 | SEC-007 | Add upload validators and size limits | Reduce upload DoS and unsafe media risk | Upload validation tests |
| P2 | SEC-008 | Require secure SMTP in production | Protect reset links in transit | Settings guard tests |
| P3 | SEC-009 | Add dependency/SAST scans to CI | Detect known vulnerabilities earlier | CI `pip-audit`/SAST job |

## AI Handoff

```yaml
security_review:
  review_id: "SEC-20260616-full-project"
  scope: "Django application, auth, APIs, settings, Docker/nginx, dependencies"
  status: "complete"
  authorization: "local defensive review only; no live external scanning"
  findings:
    - id: "SEC-001"
      severity: "critical"
      confidence: "high"
      component: "property/bank/mortgage views"
      category: "authorization"
      status: "open"
      evidence:
        - "No login_required/LoginRequiredMixin in property, bank, mortgage, property/api_urls.py"
        - "property/views.py:75,765,778,791,1124,1134,1168,1523,1549,1584"
        - "bank/views.py:30,482,486,523"
        - "mortgage/views.py:542,1009,1081,1088,1211,1227,1234"
      affected_assets:
        - "business catalog data"
        - "mortgage calculations"
      attacker_preconditions:
        - "anonymous HTTP access"
      recommended_fix:
        - "Add authentication and permission checks to private/admin endpoints"
      validation:
        - "Add anonymous-access denial tests"
      residual_risk:
        - "Needs product decision on public vs private catalog pages"
    - id: "SEC-002"
      severity: "critical"
      confidence: "high"
      component: "mortgage/trench_mortgage/customer"
      category: "authorization"
      status: "open"
      evidence:
        - "MortgageCalculation and TrenchMortgageCalculation have no owner field"
        - "mortgage/views.py:1032,1083,1090,1015,1229,1236"
      affected_assets:
        - "saved calculations"
      attacker_preconditions:
        - "known or guessed calculation pk"
      recommended_fix:
        - "Add owner field and scope querysets by request.user"
      validation:
        - "Cross-user access tests"
      residual_risk:
        - "Legacy row ownership migration"
    - id: "SEC-004"
      severity: "high"
      confidence: "high"
      component: "settings/compose/nginx"
      category: "configuration"
      status: "open"
      evidence:
        - "manage.py check --deploy reports W004, W008, W012, W016"
        - "settings.py:30 empty SECRET_KEY fallback"
        - "compose.yaml:8,27,32 unsafe secret fallbacks"
      affected_assets:
        - "sessions"
        - "deployment secrets"
      attacker_preconditions:
        - "production misconfiguration or leaked config"
      recommended_fix:
        - "Fail fast for missing secrets and add production security settings"
      validation:
        - "manage.py check --deploy"
      residual_risk:
        - "Deployment-specific TLS validation"
  next_actions:
    - "Implement SEC-001 and SEC-002 before feature work."
    - "Run deployment hardening from SEC-004."
    - "Add dependency vulnerability scanning to CI."
```

## Open Questions

- Which catalog/list/detail pages are intended to be public marketing pages versus staff-only operational tools?
- How should existing saved mortgage and trench calculations be assigned during owner-field migration?
- Which deployment terminates TLS and owns production email configuration?

## Appendix

- Confirmed clean areas: no `csrf_exempt` found, `CsrfViewMiddleware` enabled, no confirmed `mark_safe`, `eval`, `exec`, raw SQL, or unparameterized cursor usage in reviewed app code.
- `.env` is not tracked by Git (`git ls-files .env .env.example .dockerignore` returned `.env.example` and `.dockerignore`, not `.env`).
- Values from local `.env` observed through `docker compose config` are intentionally redacted from this report.
