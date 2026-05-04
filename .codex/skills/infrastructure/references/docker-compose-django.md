# Docker and Compose for Django/PostgreSQL

Use this reference when adding Dockerfiles, Compose files, entrypoints, local development containers, or service configuration.

## Image Design

- Use a slim Python base image unless the project needs system packages that justify another base.
- Pin Python and major system dependencies deliberately.
- Install dependencies before copying the whole source tree to preserve build cache.
- Do not bake secrets into images.
- Run as a non-root user where practical.
- Keep development-only tools out of production images unless the project explicitly accepts that tradeoff.

## Django Runtime

- Set `DJANGO_SETTINGS_MODULE=real_estate_investing.settings` when needed.
- Make environment variables explicit: `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, database settings, email settings.
- Run `python manage.py check` in CI and before trusting a new runtime configuration.
- Decide whether migrations run manually, in CI/CD, or in an entrypoint. Avoid hidden migration behavior for production unless the deployment model is explicit.
- Handle static files deliberately: development mounts vs production collection and serving.

## PostgreSQL Service

- Use the official PostgreSQL image for local Compose unless there is a specific reason not to.
- Store data in a named volume.
- Add a PostgreSQL health check and make app startup wait for readiness where needed.
- Keep local database credentials in `.env` or Compose defaults suitable only for development.
- Avoid using SQLite in containers for behavior that must match production.

## Compose Files

- Use `compose.yaml` or `docker-compose.yml` consistently.
- Keep development bind mounts separate from production image behavior.
- Expose only needed ports.
- Use service names for inter-container hosts, for example `DB_HOST=db`.
- Keep one clear command per service and avoid fragile shell-heavy entrypoints unless needed.

## Verification

Typical local checks:

```powershell
docker compose config
docker compose build
docker compose up
docker compose exec web python manage.py check
docker compose exec web python -m pytest
```
