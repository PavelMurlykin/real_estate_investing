# GitHub Actions CI/CD

Use this reference when adding or changing `.github/workflows/*`.

## CI Baseline

- Trigger CI on pull requests and pushes to protected branches.
- Check out code with `actions/checkout`.
- Set up Python with an explicit version.
- Install dependencies reproducibly from project dependency files.
- Run Django checks, migrations check, and pytest.
- Use a PostgreSQL service container for tests that depend on PostgreSQL behavior.
- Add frontend install/lint/typecheck/test/build steps when React tooling exists.

## Django/PostgreSQL Testing

- Configure database environment variables for the PostgreSQL service.
- Wait for PostgreSQL readiness before running tests if the service health check is not enough.
- Run `python manage.py makemigrations --check --dry-run`.
- Run `python manage.py check`.
- Run `python -m pytest`.

## Workflow Security

- Set minimal `permissions` at workflow or job level.
- Never echo secrets.
- Use GitHub Secrets for deployment credentials, API tokens, and production settings.
- Avoid running deployment steps on untrusted pull request code.
- Pin third-party actions to stable versions; consider SHA pinning for high-security workflows.

## CD Shape

- Deploy only after CI passes.
- Gate production deploys by branch and GitHub Environment protection.
- Keep build, test, publish, migrate, and deploy phases visible in logs.
- Make rollback expectations explicit before production use.
- Use concurrency groups to prevent overlapping deploys to the same environment.

## Caching

- Cache pip/npm dependencies only when cache keys include lockfiles or dependency files.
- Do not cache generated artifacts in a way that can hide failing builds.
- Keep cache restore optional, never required for correctness.
