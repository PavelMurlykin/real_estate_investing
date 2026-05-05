# Infrastructure Security and Operations

Use this reference for production-like infrastructure, deployment, secrets, networking, hardening, backups, observability, and rollback behavior.

## Secrets and Config

- Keep real secrets out of git.
- Keep `.env.example` complete but non-sensitive.
- Separate development, CI, staging, and production values.
- Use GitHub Actions secrets or environment secrets for CI/CD.
- Avoid printing environment dumps in CI logs.

## Container Hardening

- Use non-root users where practical.
- Keep images small and dependency layers clear.
- Expose only necessary ports.
- Avoid installing compilers and package managers in final production images unless needed.
- Rebuild images from dependency changes rather than patching running containers manually.

## Django Production Concerns

- `DEBUG` must be false in production.
- `SECRET_KEY`, `ALLOWED_HOSTS`, CSRF trusted origins, email settings, and database settings must be explicit.
- Static files and media files need a deliberate serving/storage strategy.
- Database migrations need an auditable execution point.

## Database Operations

- Use durable storage for PostgreSQL.
- Define backup and restore expectations before production data matters.
- Avoid destructive migration or reset commands in automation.
- Plan for migration rollback or forward-fix strategy.

## Observability

- Log to stdout/stderr in containers.
- Avoid logging sensitive data.
- Add health checks for app and database services.
- Keep error reporting and alerting configuration environment-specific.
