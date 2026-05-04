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
