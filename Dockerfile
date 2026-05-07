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

RUN chmod +x /entrypoint.sh \
    && mkdir -p /app/staticfiles \
    && chown -R django:django /app /entrypoint.sh

USER django

EXPOSE 8000

ENTRYPOINT ["/entrypoint.sh"]
CMD ["gunicorn", "real_estate_investing.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "3"]
