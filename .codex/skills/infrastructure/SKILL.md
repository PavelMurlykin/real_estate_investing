---
name: infrastructure
description: Infrastructure workflow for this real_estate_investing project. Use when adding or changing Dockerfiles, Docker Compose, environment configuration, PostgreSQL service setup, local development containers, production container concerns, GitHub Actions workflows, CI checks, CD deployment steps, secrets handling, caching, build reproducibility, or release automation. Enforce secure, reproducible, least-privilege, testable infrastructure for Django/PostgreSQL and future React frontend work.
---

# Infrastructure

## Core Workflow

Use this skill for Docker, Docker Compose, and GitHub Actions CI/CD work.

1. Inspect existing project commands, dependencies, environment variables, and runtime assumptions.
2. Keep local development, CI, and production concerns explicit and separate.
3. Make containers reproducible, minimal, non-root where practical, and friendly to Django/PostgreSQL workflows.
4. Store secrets only in environment variables, `.env` files excluded from git, or GitHub Actions secrets.
5. Add health checks and readiness behavior where service ordering matters.
6. Add CI checks that mirror the commands developers should trust locally.
7. Document required variables in `.env.example` or workflow comments when needed.

## Project Context

- Backend: Django.
- Database: PostgreSQL.
- Settings module: `real_estate_investing.settings`.
- Future frontend: React.
- Current dependency file: `requirements.txt`.
- Existing `.env` is local-only; do not commit real secrets.

## Project Architecture Decision

The default container runtime is a three-service Docker Compose stack:

- `nginx` is the only public HTTP entrypoint. It serves collected static files
  from a shared named volume and proxies dynamic requests to Django.
- `web` runs Django through Gunicorn using
  `real_estate_investing.wsgi:application`. It waits for PostgreSQL readiness,
  runs `collectstatic --noinput`, applies migrations, and then starts Gunicorn.
- `db` uses the official PostgreSQL image with durable data in the named
  `postgres_data` volume. For PostgreSQL 18 and newer, mount the volume at
  `/var/lib/postgresql` so the official image can use its version-specific data
  directory layout.

Compose-specific configuration must remain environment-driven through `.env`
and `.env.example`. The application service talks to PostgreSQL through the
Compose service name `db`; nginx talks to Django through the service name
`web`. Do not expose PostgreSQL to the host unless a task explicitly requires
local database access from host tools.

## Docker and Compose

Read `references/docker-compose-django.md` before adding or changing Dockerfiles, Compose files, entrypoints, service health checks, volumes, static files, or PostgreSQL service definitions.

Always decide:

- Which image runs Django commands.
- How migrations, static files, and startup commands are handled.
- How the app waits for PostgreSQL readiness.
- Which files are copied into the image and which are mounted only in development.
- Which environment variables are required and where examples are documented.

## GitHub Actions CI/CD

Read `references/github-actions-ci-cd.md` before adding or changing `.github/workflows/*`.

Always check:

- CI installs dependencies reproducibly.
- Django tests run against PostgreSQL, not only SQLite.
- Secrets are read from GitHub Secrets and never echoed.
- Workflow permissions are least-privilege.
- Caching does not hide dependency or migration failures.
- Deployment jobs are gated by branch, environment, and test success.

## Security and Operations

Read `references/infrastructure-security-ops.md` for deployment, secrets, networking, container hardening, backups, observability, and rollback behavior.

Always check:

- No credentials in Dockerfiles, Compose files, workflow logs, or committed config.
- Production images do not run with development debug settings.
- Services expose only necessary ports.
- Database data uses named volumes or managed storage.
- Backup and restore expectations are explicit before production data matters.

## Verification

Use commands appropriate to the touched files. Typical commands:

```powershell
docker compose config
docker compose build
docker compose up
python manage.py check
python -m pytest
```

For GitHub Actions, validate YAML structure locally when possible and keep workflow steps small enough to debug from logs.
