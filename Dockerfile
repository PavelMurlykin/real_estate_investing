FROM node:22-alpine AS frontend_builder

WORKDIR /build/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

RUN groupadd --system django \
    && useradd --system --gid django --home-dir /app django

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY docker/django/entrypoint.sh /entrypoint.sh
COPY . .
COPY --from=frontend_builder /build/static/react /app/static/react

RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/staticfiles \
    && mkdir -p /app/media \
    && chown -R django:django /app /entrypoint.sh

USER django

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "real_estate_investing.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
