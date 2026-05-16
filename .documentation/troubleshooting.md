# Troubleshooting

Документ собирает типовые ошибки при запуске и ручном деплое проекта
`real_estate_investing`.

## Быстрая диагностика

Начать с этих команд:

```bash
cd ~/apps/real_estate_investing
docker compose ps
docker compose logs --tail 120 web
docker compose logs --tail 120 db
docker compose config
```

Проверить Django:

```bash
docker compose exec web python manage.py check
```

## Порт 80 уже занят

Ошибка:

```text
Bind for 0.0.0.0:80 failed: port is already allocated
```

Решение: поменять порт nginx в `.env`:

```env
NGINX_PORT=8080
```

Перезапустить контейнеры:

```bash
docker compose up -d --force-recreate
```

Открывать приложение по адресу:

```text
http://<server-ip>:8080/
```

## `web` unhealthy

Проверить логи:

```bash
docker compose logs --tail 120 web
```

Посмотреть подробности healthcheck:

```bash
docker inspect real_estate_investing-web-1 --format '{{json .State.Health}}'
```

Частые причины:

- ошибка импорта Django settings;
- пустое или некорректное значение в `.env`;
- `ALLOWED_HOSTS` не содержит `localhost`, `127.0.0.1` или `web`;
- PostgreSQL недоступен;
- миграции завершились с ошибкой.

## `EMAIL_PORT` ломает запуск

Ошибка:

```text
ValueError: invalid literal for int() with base 10: ''
```

Причина: в `.env` указано пустое значение:

```env
EMAIL_PORT=
```

Решение:

```env
EMAIL_PORT=25
```

Перезапустить:

```bash
docker compose up -d --build
```

## Ошибка `DisallowedHost`

Признак в логах:

```text
Invalid HTTP_HOST header
```

Добавить адрес сервера или домен в `.env`:

```env
ALLOWED_HOSTS=localhost,127.0.0.1,web,192.168.1.95,example.com
```

Если используется HTTPS, проверить `CSRF_TRUSTED_ORIGINS`:

```env
CSRF_TRUSTED_ORIGINS=https://example.com
```

Применить изменения:

```bash
docker compose up -d --force-recreate
```

## `db` постоянно перезапускается после смены PostgreSQL image

Проверить логи:

```bash
docker compose logs --tail 120 db
```

Если в логах сказано, что PostgreSQL 18 ожидает другой layout данных, проверить
mount в `compose.yaml`:

```yaml
volumes:
  - postgres_data:/var/lib/postgresql
```

Для PostgreSQL 18 и новее не использовать старый mount
`/var/lib/postgresql/data`.

Если volume уже создан в неверном формате, понадобится backup/restore или
пересоздание volume. Не выполнять `docker compose down -v`, пока не понятно,
что актуальный backup есть и проверен.

## `pg_restore: unsupported version in file header`

Причина: backup создан более новой версией `pg_dump`, чем `pg_restore` в
контейнере.

Решения:

- использовать контейнер PostgreSQL той же или более новой major-версии;
- пересоздать backup совместимой версией `pg_dump`;
- сделать plain SQL dump.

Подробнее: `.documentation/backup_restore.md`.

## Таблицы появились, но данных нет

Частая причина: custom-format dump `PGDMP` восстановили через `psql -f`.

Проверить формат:

```bash
docker compose exec db sh -c 'head -c 5 /tmp/real_estate_investing.dump'
```

Если вывод `PGDMP`, восстановить через `pg_restore` по инструкции из
`.documentation/backup_restore.md`.

## Контейнеры не обновились после `docker compose up -d --build`

Проверить текущую папку и compose project:

```bash
pwd
docker compose config --services
```

Проверить последний коммит:

```bash
git log --oneline -1
```

Принудительная пересборка:

```bash
docker compose build --no-cache web
docker compose up -d --force-recreate web nginx
```

Проверить время создания контейнера:

```bash
docker inspect real_estate_investing-web-1 --format '{{.Created}}'
```

## GitHub SSH не работает

Проверить доступ:

```bash
ssh -T git@github.com
```

Если ключ не добавлен, показать публичный ключ:

```bash
cat ~/.ssh/id_ed25519.pub
```

Добавить его в GitHub:

```text
GitHub -> Settings -> SSH and GPG keys -> New SSH key
```

## Недостаточно места на сервере

Проверить диск:

```bash
df -h
docker system df
```

Удалить неиспользуемые Docker build cache и dangling images:

```bash
docker system prune
```

Не использовать `docker volume prune` без проверки: команда может удалить
volumes с данными.

## Полная остановка и запуск

Остановить контейнеры без удаления volume:

```bash
docker compose down
```

Запустить снова:

```bash
docker compose up -d
```

Удалять volume только при осознанном восстановлении из backup:

```bash
docker compose down -v
```
