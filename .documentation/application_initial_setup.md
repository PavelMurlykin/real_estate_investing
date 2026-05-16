# Первичная настройка приложения

Документ описывает разовую настройку приложения `real_estate_investing` на уже
подготовленном сервере. Подготовка ОС, Docker и GitHub SSH описана в
`.documentation/server_setup.md`.

## Архитектура запуска

Проект запускается через `docker compose` в трех контейнерах:

- `nginx` - публичная HTTP-точка входа, проксирует запросы в Django и отдает
  статические файлы.
- `web` - Django + Gunicorn.
- `db` - PostgreSQL 18 с данными в Docker volume
  `real_estate_investing_postgres_data`.

PostgreSQL не публикуется наружу. Доступ извне идет только через nginx.

## Клонирование репозитория

```bash
cd ~/apps
git clone git@github.com:PavelMurlykin/real_estate_investing.git
cd ~/apps/real_estate_investing
```

Проверить ветку и последний коммит:

```bash
git branch --show-current
git log --oneline -1
```

## Настройка `.env`

Создать локальный `.env`:

```bash
cp .env.example .env
nano .env
```

Пример значений для сервера по IP:

```env
DEBUG=False
SECRET_KEY=replace-with-long-random-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,web,192.168.1.95
CSRF_TRUSTED_ORIGINS=http://192.168.1.95
DB_NAME=real_estate_investing
DB_USER=real_estate_investing
DB_PASSWORD=replace-with-strong-database-password
DB_HOST=db
DB_PORT=5432
NGINX_PORT=80
EMAIL_BACKEND=
EMAIL_HOST=
EMAIL_PORT=25
EMAIL_HOST_USER=
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=
EMAIL_USE_SSL=
DEFAULT_FROM_EMAIL=
```

Для домена добавить домен:

```env
ALLOWED_HOSTS=localhost,127.0.0.1,web,example.com
CSRF_TRUSTED_ORIGINS=http://example.com,https://example.com
```

Файл `.env` нельзя коммитить в Git.

## Первый запуск контейнеров

```bash
cd ~/apps/real_estate_investing
docker compose up -d --build
```

Проверить состояние:

```bash
docker compose ps
docker compose logs --tail 100 web
docker compose logs --tail 100 db
```

Проверить Django:

```bash
docker compose exec web python manage.py check
```

Открыть приложение:

```text
http://192.168.1.95/
```

Если в `.env` используется `NGINX_PORT=8080`, адрес будет:

```text
http://192.168.1.95:8080/
```

## Восстановление backup базы данных

Если нужно перенести существующую базу, скопировать backup с Windows на сервер.
Команда выполняется на Windows в PowerShell:

```powershell
scp -C "C:\Development\pg_backup\real_estate_investing.sql" pavelmurlykin@192.168.1.95:~/backups/real_estate_investing.dump
```

На сервере проверить файл:

```bash
ls -lh ~/backups/real_estate_investing.dump
```

Остановить приложение, оставив PostgreSQL:

```bash
cd ~/apps/real_estate_investing
docker compose stop web nginx
docker compose up -d db
```

Скопировать backup в контейнер PostgreSQL:

```bash
docker compose cp ~/backups/real_estate_investing.dump db:/tmp/real_estate_investing.dump
```

Если файл является custom-format dump `PGDMP`, восстанавливать его нужно через
`pg_restore`, а не через `psql -f`.

Пересоздать базу и восстановить backup:

```bash
docker compose exec db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists --maintenance-db=postgres "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" --maintenance-db=postgres "$POSTGRES_DB"'
```

```bash
docker compose exec db sh -c 'pg_restore --verbose --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB" /tmp/real_estate_investing.dump'
```

Проверить таблицы:

```bash
docker compose exec db psql -U real_estate_investing -d real_estate_investing -c "\dt"
```

Запустить весь проект:

```bash
docker compose up -d
docker compose ps
```

Подробная инструкция по backup и restore вынесена в
`.documentation/backup_restore.md`.

## Настройка автозапуска приложения

Создать `systemd` service:

```bash
sudo nano /etc/systemd/system/real-estate-investing.service
```

Содержимое:

```ini
[Unit]
Description=Real Estate Investing Docker Compose stack
Requires=docker.service
After=docker.service network-online.target
Wants=network-online.target

[Service]
Type=oneshot
WorkingDirectory=/home/pavelmurlykin/apps/real_estate_investing
ExecStart=/usr/bin/docker compose up -d --remove-orphans
ExecStop=/usr/bin/docker compose stop
RemainAfterExit=yes
TimeoutStartSec=0

[Install]
WantedBy=multi-user.target
```

Включить сервис:

```bash
sudo systemctl daemon-reload
sudo systemctl enable docker
sudo systemctl enable real-estate-investing.service
sudo systemctl start real-estate-investing.service
```

Проверить:

```bash
sudo systemctl status real-estate-investing.service
docker compose ps
```

Проверить после перезагрузки:

```bash
sudo reboot
```

```bash
cd ~/apps/real_estate_investing
docker compose ps
sudo systemctl status real-estate-investing.service
```

После первичной настройки регулярные обновления выполнять по
`.documentation/manual_deployment.md`. Для настройки HTTPS с доменом использовать
`.documentation/https_setup.md`.
