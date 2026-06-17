# Application Security Review

## Metadata

- Review ID: SEC-20260617-full-project-refresh
- Date: 2026-06-17
- Reviewer: Codex
- Repository/branch: real_estate_investing / main
- Scope: Django application, auth flows, role model, business CRUD, JSON APIs, settings, dependencies, Docker Compose, nginx, local test coverage
- Review type: static + safe dynamic-local + dependency/SAST/configuration
- Environment: local Windows workspace, project virtualenv, local `.env` loaded by Django/Docker Compose
- Authorization: local defensive review only; no live external exploitation. Network access was used only for `pip-audit` against public vulnerability metadata.
- Status: complete

## Executive Summary

The previous critical authorization findings are now remediated: global catalog writes are role-gated, external synchronization is administrator-only, private customer/calculation data is scoped by owner, saved mortgage and trench calculations have an owner field, public JSON APIs are bounded and field-allowlisted, and image upload limits are enforced.

The current highest-risk items are dependency and production-hardening related. `pip-audit` reports known vulnerabilities in `Django==6.0.4` with fixes available in `6.0.6`; production security settings are still not enabled; password/abuse controls are still absent; and external sync code uses `urlopen` without an explicit scheme/host allowlist. These do not block local offline testing, but they should be handled before any internet-facing deployment.

## Scope And Threat Model

- Assets reviewed: user accounts, roles, customers, saved calculations, property/catalog data, bank programs, uploads/media, public selector APIs, external sync jobs, secrets/configuration, deployment stack.
- Primary attacker model: anonymous internet user, authenticated low-privilege user, application moderator, application administrator, supply-chain/deployment mistake.
- Out of scope: destructive payloads, live production scans, real credential validation, production SMTP testing.
- Product policy assumption: anonymous users are intentionally allowed read-only access to the homepage and `bank`, `location`, `property` data, and may use `/mortgage/` without saving to DB.

## Commands And Evidence

| Command or source | Purpose | Result |
| --- | --- | --- |
| `git status --short` | Confirm working tree before review | Clean before audit edits |
| `.\.venv\Scripts\python.exe manage.py check` | Django sanity check | Passed, 0 issues |
| `.\.venv\Scripts\python.exe manage.py check --deploy` | Django production security check | 4 warnings: `security.W004`, `security.W008`, `security.W012`, `security.W016` |
| `.\.venv\Scripts\python.exe -m pytest` | Regression suite | 197 passed |
| `.\.venv\Scripts\python.exe -m pip check` | Dependency compatibility | No broken requirements |
| `.\.venv\Scripts\python.exe -m pip_audit -r requirements.txt --no-deps --disable-pip ...` | Dependency vulnerability audit | 11 known vulnerabilities in `django==6.0.4`; fixed by `6.0.6` |
| `.\.venv\Scripts\python.exe -m bandit -r ... -x "*/migrations/*,*/tests.py" -q` | Static security scan | 3 medium B310 issues for `urlopen` in sync code |
| `docker compose config` | Validate rendered Compose configuration | Valid config; local secrets are expanded by Compose and are redacted from this report |
| `rg -n "csrf_exempt|mark_safe|eval\(|exec\(|raw\(|cursor\(|subprocess"` | High-risk pattern scan | No confirmed `csrf_exempt`, `mark_safe`, `eval`, `exec`, raw SQL cursor, or subprocess use in app code |
| `.dockerignore` / `git ls-files` review | Secret/build context review | `.env`, `.git`, `.venv`, caches, staticfiles are excluded; `.env` is not tracked |

## Findings

### SEC-001: Business CRUD And Sync Views Lack Explicit Authentication

- Severity: critical
- Confidence: high
- Component: `property`, `bank`, `location`
- Category: authorization
- Status: closed
- Evidence:
  - Role helpers exist in `users/roles.py:41`, `users/roles.py:46`, `users/roles.py:51`, `users/roles.py:56`.
  - Global catalog writes require `CatalogManagementRequiredMixin` or `can_manage_catalogs` in `property/views.py:573`, `property/views.py:614`, `property/views.py:874`, `property/views.py:1221`, `property/views.py:1603`.
  - Bank catalog writes and sync actions enforce role checks in `bank/views.py:117`, `bank/views.py:124`, `bank/views.py:127`, `bank/views.py:497`, `bank/views.py:549`.
  - Sync is administrator-only by `can_sync_external_data` in `users/roles.py:46`.
  - Regression coverage includes anonymous read-only and moderator sync-denial tests in `bank/tests.py:796`, `bank/tests.py:818`, `bank/tests.py:1547`, `property/tests.py:786`, `property/tests.py:1365`.
- Validation:
  - Full test suite passed: 197 tests.
- Residual risk:
  - Public read access is a product decision, documented in `.documentation/role_model.md`.

### SEC-002: Saved Mortgage Calculations Are Not Owner Scoped

- Severity: critical
- Confidence: high
- Component: `mortgage`, `trench_mortgage`, `customer`
- Category: authorization / IDOR
- Status: closed
- Evidence:
  - `MortgageCalculation.user` exists in `mortgage/models.py:25`.
  - `TrenchMortgageCalculation.user` exists in `trench_mortgage/models.py:21`.
  - Private querysets are scoped by `_filter_private_queryset_for_user` in `mortgage/views.py:87`.
  - Saved calculation list/detail/delete flows are login-protected and user-scoped in `mortgage/views.py:1128`, `mortgage/views.py:1209`, `mortgage/views.py:1223`, `mortgage/views.py:1351`, `mortgage/views.py:1374`, `mortgage/views.py:1385`.
  - Customer querysets are scoped in `customer/views.py:29`, with administrator override through `can_view_all_private_records`.
  - Regression coverage includes anonymous denial, cross-user denial, and admin-all access tests in `mortgage/tests.py:387`, `mortgage/tests.py:728`, `mortgage/tests.py:951`, `customer/tests.py:345`.
- Validation:
  - Full test suite passed: 197 tests.
- Residual risk:
  - Legacy rows may remain `user=NULL` if ownership cannot be inferred during migration; verify and assign/retire such rows before production data migration.

### SEC-003: Public JSON APIs Expose Internal Property Hierarchy And Objects

- Severity: medium
- Confidence: high
- Component: `property.api_urls`, `mortgage`
- Category: data exposure / scraping resistance
- Status: partially mitigated
- Evidence:
  - Public read access to `property/location/bank` is allowed by the role model, so anonymous API reads are intentional where they support UI selectors.
  - `property/api_urls.py:10` defines explicit field allowlists.
  - `property/api_urls.py:28` validates positive integer query parameters and returns `400` for invalid IDs.
  - `property/api_urls.py:51` bounds selector API result size through `PUBLIC_CATALOG_API_MAX_RESULTS`.
  - `property/api_urls.py:133` prevents `/api/complexes/` from returning a full unfiltered dump.
  - `mortgage/views.py:1102` makes `property_cost_api` GET-only, and `_get_property_payload` returns an explicit property payload.
  - Regression coverage for allowlisted fields, invalid filters, empty broad requests, and GET-only behavior exists in `property/tests.py:1294`, `property/tests.py:1311`, `mortgage/tests.py:1830`.
- Remaining risk:
  - APIs are still public and do not have request throttling, IP/user rate limits, or anti-scraping controls.
  - Public property price and hierarchy data may still be bulk-enumerable through filtered requests.
- Recommended fix:
  - Keep API field allowlists under test.
  - Add a lightweight throttle/rate-limit layer before internet exposure.
  - Define acceptable anonymous API volume in `.documentation/role_model.md` or an API contract document.
- Validation plan:
  - Add throttle tests when rate limiting is introduced.

### SEC-004: Production Security Settings And Secret Handling Are Weak

- Severity: high
- Confidence: high
- Component: Django settings, Docker Compose, nginx
- Category: configuration
- Status: open
- Evidence:
  - `real_estate_investing/settings.py:30` still allows `SECRET_KEY = os.getenv('SECRET_KEY', '')`.
  - `compose.yaml:27` still has an unsafe development fallback for `SECRET_KEY`.
  - `manage.py check --deploy` reports `security.W004`, `security.W008`, `security.W012`, `security.W016`.
  - No `SECURE_HSTS_SECONDS`, `SECURE_SSL_REDIRECT`, `SESSION_COOKIE_SECURE`, `CSRF_COOKIE_SECURE`, or `SECURE_PROXY_SSL_HEADER` settings were found.
  - `docker compose config` expands local `.env` values, including secrets; values are redacted here.
- Affected assets:
  - Sessions, CSRF tokens, password-reset tokens, production deployment secrets, transport confidentiality.
- Attacker preconditions:
  - Internet-facing deployment with local/dev defaults, HTTP-only transport, or leaked rendered Compose config/logs.
- Impact:
  - Weak/empty signing key, session/CSRF cookies over HTTP, missing HSTS, accidental secret disclosure in generated config/logs.
- Recommended fix:
  - Add production-only env switch, for example `ENABLE_HTTPS_SECURITY=True`, that sets `SECURE_SSL_REDIRECT`, secure cookies, HSTS, and `SECURE_PROXY_SSL_HEADER`.
  - Fail fast when `SECRET_KEY` is empty in non-debug/non-local mode.
  - Remove unsafe Compose secret fallbacks for production or split dev/prod Compose profiles.
  - Rotate any local secrets that were ever shared outside the machine.
- Validation plan:
  - Run `manage.py check --deploy` under production env and expect no warnings.
  - Run `docker compose config` with production env and verify no unsafe defaults are used.

### SEC-005: Password And Abuse Controls Are Missing

- Severity: high
- Confidence: high
- Component: `users`, Django settings
- Category: authentication / abuse prevention
- Status: open
- Evidence:
  - No `AUTH_PASSWORD_VALIDATORS` setting was found in `real_estate_investing/settings.py`.
  - Login/register/password-reset routes are exposed in `users/urls.py:14`, `users/urls.py:15`, `users/urls.py:37`, `users/urls.py:54`.
  - `requirements.txt` has no runtime throttling package such as `django-axes` or `django-ratelimit`.
- Affected assets:
  - User accounts, login form, registration form, password-reset flow.
- Attacker preconditions:
  - Anonymous access to auth endpoints after internet exposure.
- Impact:
  - Weak passwords, login brute force, reset-email flooding, account enumeration pressure.
- Recommended fix:
  - Add Django standard password validators behind a local-testing-friendly flag if needed.
  - Add rate limiting/lockout for login, registration, and password reset before public deployment.
  - Add tests for weak password rejection and throttled repeated attempts.
- Residual risk:
  - Thresholds require tuning against real traffic.

### SEC-006: Authentication Backend Resolves Ambiguous Identifier Collisions Unsafe

- Severity: high
- Confidence: medium
- Component: `users.backends.EmailOrPhoneBackend`
- Category: authentication
- Status: closed
- Evidence:
  - `users/backends.py:55` catches `MultipleObjectsReturned`, logs a redacted warning, and returns `None`.
  - The previous branch that selected `.order_by('id').first()` is gone.
- Validation:
  - Covered by full test suite and static inspection.
- Residual risk:
  - Existing data should still be checked for email/phone normalization drift before production import.

### SEC-007: Upload And Request Body Limits Are Incomplete

- Severity: medium
- Confidence: high
- Component: `property`, settings, nginx
- Category: file upload / DoS
- Status: closed
- Evidence:
  - Reusable image validator exists in `property/validators.py:31`.
  - Property image fields use the validator in `property/models.py:123`, `property/models.py:481`, `property/models.py:488`, `property/models.py:495`.
  - Django limits are configured in `real_estate_investing/settings.py:111`, `real_estate_investing/settings.py:115`, `real_estate_investing/settings.py:119`, `real_estate_investing/settings.py:123`.
  - nginx request limit remains explicit at `docker/nginx/default.conf:9`.
  - Regression coverage rejects oversized/wrong-type uploads in `property/tests.py:447` and neighboring upload tests.
- Validation:
  - Full test suite passed: 197 tests.
- Residual risk:
  - Image decoder risk depends on Pillow updates; keep dependency scanning active.

### SEC-008: Email Reset Defaults Allow Plain SMTP

- Severity: medium
- Confidence: high
- Component: Django settings, password reset
- Category: configuration
- Status: open
- Evidence:
  - `EMAIL_BACKEND` defaults to console in debug and SMTP otherwise in `real_estate_investing/settings.py:155`.
  - `EMAIL_USE_TLS` and `EMAIL_USE_SSL` default to false in `real_estate_investing/settings.py:167` and `real_estate_investing/settings.py:173`.
  - Password reset routes are wired in `users/urls.py:37` and `users/urls.py:54`.
- Affected assets:
  - Password-reset links and email credentials.
- Attacker preconditions:
  - Production SMTP configured without TLS/SSL or traffic visible to a network observer.
- Impact:
  - Password-reset links may traverse SMTP plaintext.
- Recommended fix:
  - Add a production/email env guard requiring exactly one of TLS/SSL when SMTP is enabled outside local testing.
  - Keep console email backend for local testing.
- Validation plan:
  - Add settings tests for TLS/SSL guard behavior.

### SEC-009: Django Dependency Has Known Vulnerabilities

- Severity: high
- Confidence: high
- Component: dependencies
- Category: supply chain
- Status: open
- Evidence:
  - `requirements.txt` pins `Django==6.0.4`.
  - `pip-audit` reported 11 known vulnerabilities for `django==6.0.4`.
  - Reported advisory IDs: `PYSEC-2026-50`, `PYSEC-2026-55`, `PYSEC-2026-54`, `PYSEC-2026-199`, `PYSEC-2026-197`, `PYSEC-2026-200`, `PYSEC-2026-198`, `PYSEC-2026-201`.
  - Fix versions reported by `pip-audit`: `6.0.5` and `6.0.6`; effective target should be `Django==6.0.6` or newer compatible patch release.
  - `requirements-dev.txt` now contains `pip-audit` and `bandit`, but no CI workflow exists to run them automatically.
- Affected assets:
  - Entire Django application surface.
- Attacker preconditions:
  - Depends on each advisory; because framework vulnerabilities are known publicly, patching should be prioritized before exposure.
- Impact:
  - Potential framework-level vulnerabilities in request handling, forms, auth, or ORM depending on advisory details.
- Recommended fix:
  - Upgrade Django to `6.0.6` or the latest compatible security patch.
  - Run `python -m pytest`, `python manage.py check`, and `python -m pip_audit -r requirements.txt` after upgrade.
  - Add CI to run Django checks, migrations check, pytest, pip-audit, and bandit.
- Validation plan:
  - `pip-audit` returns no actionable Django vulnerabilities.
  - Full test suite remains green.

### SEC-010: External Sync Downloads Lack URL Scheme And Host Allowlist

- Severity: medium
- Confidence: high
- Component: `bank.key_rate_sync`, `bank.mortgage_offer_sync`
- Category: SSRF / unsafe URL handling / SAST
- Status: open
- Evidence:
  - `bandit` reported 3 medium B310 issues.
  - `bank/key_rate_sync.py:81` calls `urlopen(request, timeout=CBR_TIMEOUT_SECONDS)`.
  - `bank/mortgage_offer_sync.py:789` and `bank/mortgage_offer_sync.py:818` call `urlopen(...)`.
  - Source URLs can be resolved from settings or sync source records at `bank/mortgage_offer_sync.py:1248`, `bank/mortgage_offer_sync.py:1254`, `bank/mortgage_offer_sync.py:1288`.
  - Sync actions are administrator-only, reducing exploitability, but compromised/mistaken admin config could still target unexpected schemes/hosts.
- Affected assets:
  - Internal network metadata/services reachable from the web container, worker availability, sync data integrity.
- Attacker preconditions:
  - Admin-level access, compromised settings/source configuration, or future code path that accepts external source URLs from lower-privilege users.
- Impact:
  - Unexpected `file:`/custom scheme access, SSRF-like internal network requests, slow/hanging external downloads.
- Recommended fix:
  - Add a shared URL validator for sync sources.
  - Allow only `https` and explicit host allowlist such as `www.cbr.ru`, `www.banki.ru`, trusted Google Sheets host(s), and the selected DOMRF source host.
  - Keep timeouts and add tests for rejected `file://`, localhost, private IP, and unapproved host URLs.
- Validation plan:
  - Bandit no longer reports B310 for approved guarded calls, or guarded calls are documented with precise `# nosec` and tests.

## Remediation Plan

| Priority | Finding | Action | Expected risk reduction | Validation |
| --- | --- | --- | --- | --- |
| P0 | SEC-009 | Upgrade Django from `6.0.4` to `6.0.6` or newer compatible patch | Remove known framework vulnerabilities | `pip-audit` clean, full tests pass |
| P1 | SEC-004 | Add production security settings and remove production-secret fallbacks | Prevent insecure internet deployment | `manage.py check --deploy` clean |
| P1 | SEC-005 | Add password validators and auth/reset throttling | Reduce account abuse | Weak-password and throttle tests |
| P1 | SEC-010 | Add external sync URL allowlist | Reduce SSRF/unsafe URL risk | URL rejection tests + Bandit review |
| P2 | SEC-003 | Add public API throttling/contract | Reduce scraping/data harvesting | Throttle tests |
| P2 | SEC-008 | Require secure SMTP when production email is enabled | Protect reset links in transit | Settings guard tests |
| P3 | SEC-009 | Add CI security jobs | Keep dependency/SAST checks continuous | CI workflow green |

## AI Handoff

```yaml
security_review:
  review_id: "SEC-20260617-full-project-refresh"
  status: "complete"
  summary:
    closed:
      - "SEC-001 role-gated catalog/sync mutations"
      - "SEC-002 owner-scoped saved calculations"
      - "SEC-006 ambiguous login collision rejection"
      - "SEC-007 upload validators and request limits"
    open_high:
      - "SEC-004 production security settings/secrets"
      - "SEC-005 password and abuse controls"
      - "SEC-009 Django 6.0.4 known vulnerabilities"
    open_medium:
      - "SEC-003 public API throttling/data exposure residual risk"
      - "SEC-008 SMTP TLS/SSL guard"
      - "SEC-010 external sync URL allowlist"
  commands:
    django_check: "passed"
    django_deploy_check: "4 warnings: W004,W008,W012,W016"
    pytest: "197 passed"
    pip_check: "No broken requirements found"
    pip_audit: "11 vulnerabilities in django==6.0.4; fix to 6.0.6"
    bandit: "3 medium B310 findings in bank sync download code"
  next_actions:
    - "Upgrade Django and rerun pip-audit/test suite."
    - "Add production security env switch and deploy-check test/procedure."
    - "Add auth endpoint throttling and password validators."
    - "Guard external sync URLs by scheme and host allowlist."
```

## Open Questions

- Which exact domains should be allowed for bank/key-rate/mortgage-program synchronization?
- Should public selector APIs get anonymous throttling before or only at the first internet-facing deployment?
- Should local testing keep password validators disabled by default, or should tests move to strong passwords now?
- Which CI system should own `pytest`, `makemigrations --check`, `pip-audit`, and `bandit` gates?

## Appendix

- Positive controls confirmed: CSRF middleware enabled, no `csrf_exempt` found, no confirmed unsafe `mark_safe`, `eval`, `exec`, raw SQL cursor usage, or subprocess usage in reviewed app code.
- `.env` values observed through `docker compose config` are intentionally not quoted here.
