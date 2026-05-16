# Backup и восстановление PostgreSQL

Документ описывает создание, проверку и восстановление backup базы данных для
Docker Compose проекта `real_estate_investing`.

## Где хранятся данные

PostgreSQL работает в сервисе `db` и хранит данные в Docker volume:

```text
real_estate_investing_postgres_data
```

Данные не нужно копировать напрямую из volume. Backup и restore выполняются
через PostgreSQL-инструменты внутри контейнера.

## Создание backup

Команды выполняются на сервере:

```bash
cd ~/apps/real_estate_investing
mkdir -p ~/backups
```

Создать custom-format dump:

```bash
docker compose exec db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" > /tmp/backup.dump'
```

Скопировать backup из контейнера на сервер:

```bash
docker compose cp db:/tmp/backup.dump ~/backups/real_estate_investing-$(date +%Y-%m-%d-%H%M).dump
```

Проверить файл:

```bash
ls -lh ~/backups
```

## Проверка backup

Проверить, что файл читается `pg_restore`:

```bash
BACKUP_FILE=~/backups/real_estate_investing-YYYY-MM-DD-HHMM.dump
docker compose cp "$BACKUP_FILE" db:/tmp/check_backup.dump
docker compose exec db sh -c 'pg_restore -l /tmp/check_backup.dump | head -n 30'
```

Если команда выводит список объектов, backup читается.

## Копирование backup с Windows на сервер

Команда выполняется на Windows в PowerShell:

```powershell
scp -C "C:\Development\pg_backup\real_estate_investing.sql" pavelmurlykin@192.168.1.95:~/backups/real_estate_investing.dump
```

На сервере проверить файл:

```bash
ls -lh ~/backups/real_estate_investing.dump
```

Даже если файл называется `.sql`, сначала проверить формат:

```bash
cd ~/apps/real_estate_investing
docker compose cp ~/backups/real_estate_investing.dump db:/tmp/real_estate_investing.dump
docker compose exec db sh -c 'head -c 5 /tmp/real_estate_investing.dump'
```

Если вывод начинается с `PGDMP`, это custom-format dump. Его нужно
восстанавливать через `pg_restore`, а не через `psql -f`.

## Восстановление custom-format backup

Остановить приложение, оставив PostgreSQL:

```bash
cd ~/apps/real_estate_investing
docker compose stop web nginx
docker compose up -d db
```

Скопировать backup в контейнер:

```bash
docker compose cp ~/backups/real_estate_investing.dump db:/tmp/real_estate_investing.dump
```

Пересоздать базу:

```bash
docker compose exec db sh -c 'dropdb -U "$POSTGRES_USER" --if-exists --maintenance-db=postgres "$POSTGRES_DB" && createdb -U "$POSTGRES_USER" --maintenance-db=postgres "$POSTGRES_DB"'
```

Восстановить backup:

```bash
docker compose exec db sh -c 'pg_restore --verbose --no-owner --no-privileges -U "$POSTGRES_USER" -d "$POSTGRES_DB" /tmp/real_estate_investing.dump'
```

Проверить таблицы:

```bash
docker compose exec db psql -U real_estate_investing -d real_estate_investing -c "\dt"
```

Запустить приложение:

```bash
docker compose up -d
docker compose ps
```

## Восстановление plain SQL backup

Если backup является обычным текстовым SQL-файлом, восстановить его можно через
`psql`:

```bash
docker compose cp ~/backups/real_estate_investing.sql db:/tmp/real_estate_investing.sql
docker compose exec db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/real_estate_investing.sql'
```

Не использовать `psql -f` для custom-format dump `PGDMP`.

## Если версии PostgreSQL не совпадают

Если `pg_restore` выводит ошибку вида:

```text
unsupported version in file header
```

значит backup создан более новой версией `pg_dump`, чем `pg_restore` в
контейнере. Варианты решения:

- поднять PostgreSQL container той же или более новой major-версии;
- пересоздать backup на источнике через `pg_dump` версии, совместимой с
  сервером;
- сделать plain SQL dump на источнике и восстановить его через `psql`.

Для PostgreSQL 18 volume должен монтироваться в `/var/lib/postgresql`, как в
текущем `compose.yaml`.

## Опасные команды

Команда удаляет контейнеры и volume с PostgreSQL-данными:

```bash
docker compose down -v
```

Использовать ее только если есть актуальный backup и точно нужно начать с чистой
базы.

## Минимальная политика backup

Рекомендуемый минимум для ручной эксплуатации:

- делать backup перед каждым обновлением с миграциями;
- хранить несколько последних backup-файлов;
- периодически проверять backup через `pg_restore -l`;
- копировать важные backup-файлы с Raspberry Pi на другую машину или внешний
  диск.
