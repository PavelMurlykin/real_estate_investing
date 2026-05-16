# Ручной деплой после изменений в Git

Документ описывает регулярный ручной деплой уже настроенного проекта
`real_estate_investing` на сервере. Разовая настройка сервера описана в
`.documentation/server_setup.md`, первичная настройка приложения - в
`.documentation/application_initial_setup.md`.

## Короткий сценарий обновления

```bash
cd ~/apps/real_estate_investing
git status
git branch --show-current
git pull
docker compose up -d --build
docker compose ps
docker compose logs --tail 100 web
```

Проверить Django:

```bash
docker compose exec web python manage.py check
```

## Перед обновлением

Убедиться, что на сервере нет локальных незакоммиченных изменений:

```bash
cd ~/apps/real_estate_investing
git status
```

Проверить текущий коммит:

```bash
git log --oneline -1
```

Если обновление содержит миграции, изменения моделей или потенциально опасные
правки, сначала сделать backup базы.

Перед production-обновлением удобно пройти checklist из
`.documentation/production_update_checklist.md`.

## Backup базы перед крупным обновлением

```bash
cd ~/apps/real_estate_investing
mkdir -p ~/backups
docker compose exec db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" > /tmp/backup.dump'
docker compose cp db:/tmp/backup.dump ~/backups/real_estate_investing-$(date +%Y-%m-%d-%H%M).dump
ls -lh ~/backups
```

Подробности backup/restore описаны в `.documentation/backup_restore.md`.

## Получение изменений из Git

```bash
git pull
git log --oneline -1
```

Если сервер находится не на нужной ветке:

```bash
git branch --show-current
git checkout main
git pull
```

## Пересборка и запуск контейнеров

Стандартная команда:

```bash
docker compose up -d --build
```

Если менялись только значения в `.env`, image пересобирать не нужно:

```bash
docker compose up -d --force-recreate
```

Если есть сомнения, что Docker использовал старый cache:

```bash
docker compose build --no-cache web
docker compose up -d --force-recreate
```

Если менялся `compose.yaml`, сначала проверить итоговую конфигурацию:

```bash
docker compose config
docker compose up -d --force-recreate
```

## Проверка после деплоя

Проверить контейнеры:

```bash
docker compose ps
```

Посмотреть последние логи приложения:

```bash
docker compose logs --tail 100 web
```

Проверить Django:

```bash
docker compose exec web python manage.py check
```

Проверить, что контейнер создан после деплоя:

```bash
docker inspect real_estate_investing-web-1 --format '{{.Created}}'
```

Проверить, что внутри контейнера свежий код:

```bash
docker compose exec web grep -n "DJANGO_SETTINGS_MODULE" /app/real_estate_investing/settings.py
```

Посмотреть images, которые использует Compose:

```bash
docker compose images
```

## Если контейнеры не обновились

Проверить, что команда выполнялась в правильной папке:

```bash
pwd
docker compose config --services
```

Проверить, что код действительно обновился:

```bash
git log --oneline -1
```

Принудительно пересобрать и пересоздать `web`:

```bash
docker compose build --no-cache web
docker compose up -d --force-recreate web nginx
```

## Откат при неудачном обновлении

Посмотреть последние коммиты:

```bash
git log --oneline -5
```

Перейти на предыдущий рабочий коммит:

```bash
git checkout <commit_hash>
docker compose up -d --build
docker compose ps
docker compose logs --tail 100 web
```

После исправления вернуться на основную ветку:

```bash
git checkout main
git pull
```

Если неудачное обновление включало миграции базы данных, перед откатом
проверить совместимость схемы или восстановить backup.

## Полезные команды диагностики

Больше типовых ошибок и решений собрано в `.documentation/troubleshooting.md`.

Логи web-контейнера:

```bash
docker compose logs -f web
```

Логи PostgreSQL:

```bash
docker compose logs -f db
```

Перезапуск web:

```bash
docker compose restart web
```

Остановка всего проекта:

```bash
docker compose stop
```

Полная остановка с удалением контейнеров и сети, но без удаления volumes:

```bash
docker compose down
```

Опасная команда, удаляет PostgreSQL volume и все локальные данные базы:

```bash
docker compose down -v
```

Использовать `down -v` только если есть актуальный backup и точно нужно начать с
чистой базы.
