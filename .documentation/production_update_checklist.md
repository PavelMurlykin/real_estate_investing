# Checklist перед production-обновлением

Короткий список проверок перед ручным деплоем на сервер.

## Перед деплоем

- Убедиться, что изменения закоммичены и отправлены в GitHub.
- Проверить локальные тесты или хотя бы `python manage.py check`.
- Понять, есть ли миграции базы данных.
- Проверить, менялись ли `.env.example`, `compose.yaml`, `Dockerfile` или
  зависимости.
- Сообщить пользователям о коротком окне обновления, если приложение уже
  используется.

## На сервере перед `git pull`

```bash
cd ~/apps/real_estate_investing
git status
git log --oneline -1
docker compose ps
```

Если есть локальные изменения на сервере, не делать `git pull`, пока не понятно,
что это за изменения.

## Backup

Делать backup обязательно, если обновление содержит:

- миграции Django;
- изменения моделей;
- изменение версии PostgreSQL;
- массовую обработку данных;
- рискованные изменения бизнес-логики.

Команда:

```bash
mkdir -p ~/backups
docker compose exec db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" > /tmp/backup.dump'
docker compose cp db:/tmp/backup.dump ~/backups/real_estate_investing-$(date +%Y-%m-%d-%H%M).dump
```

Проверить backup:

```bash
ls -lh ~/backups
BACKUP_FILE=~/backups/real_estate_investing-YYYY-MM-DD-HHMM.dump
docker compose cp "$BACKUP_FILE" db:/tmp/check_backup.dump
docker compose exec db sh -c 'pg_restore -l /tmp/check_backup.dump | head -n 20'
```

## Деплой

```bash
git pull
docker compose up -d --build
```

Если менялся только `.env`:

```bash
docker compose up -d --force-recreate
```

Если есть сомнения в Docker cache:

```bash
docker compose build --no-cache web
docker compose up -d --force-recreate
```

## Проверка после деплоя

```bash
docker compose ps
docker compose logs --tail 100 web
docker compose exec web python manage.py check
```

Проверить health endpoint:

```bash
docker compose port nginx 80
curl -I http://127.0.0.1:8080/health/
```

Если `docker compose port nginx 80` показывает другой host-порт, использовать
его вместо `8080`.

Если используется HTTPS:

```bash
curl -I https://example.com/health/
```

Проверить, что контейнер свежий:

```bash
docker inspect real_estate_investing-web-1 --format '{{.Created}}'
```

## Откат

Если приложение не поднялось:

```bash
git log --oneline -5
git checkout <previous_commit_hash>
docker compose up -d --build
docker compose logs --tail 100 web
```

Если проблема связана с миграциями или данными, восстановить backup по
`.documentation/backup_restore.md`.

После исправления:

```bash
git checkout main
git pull
```

## После успешного деплоя

- Проверить основные страницы в браузере.
- Проверить логи `web` и `db`.
- Убедиться, что backup сохранен, если он создавался.
- Записать коммит, который был развернут.
