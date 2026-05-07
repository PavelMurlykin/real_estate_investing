#!/bin/sh
set -eu

python - <<'PY'
import os
import socket
import time

database_host = os.environ.get('DB_HOST', 'db')
database_port = int(os.environ.get('DB_PORT', '5432'))
deadline = time.monotonic() + 60

while True:
    try:
        with socket.create_connection((database_host, database_port), timeout=3):
            break
    except OSError:
        if time.monotonic() >= deadline:
            raise SystemExit(
                f'PostgreSQL is not reachable at {database_host}:{database_port}'
            )
        time.sleep(1)
PY

python manage.py collectstatic --noinput
python manage.py migrate --noinput

exec "$@"
