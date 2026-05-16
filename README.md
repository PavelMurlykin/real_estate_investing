# Real Estate Investing

Django-приложение для учета объектов недвижимости, застройщиков, жилых
комплексов, банковских программ, клиентов и ипотечных расчетов. Проект
запускается локально через Django или как Docker Compose stack из трех
контейнеров: `nginx`, `web` и `db`.

## Возможности

- Каталог недвижимости: объекты, ЖК, корпуса, застройщики и справочники.
- Справочники локаций: регионы, города, районы, метро и линии метро.
- Банки, ипотечные программы и ключевая ставка.
- Ипотечный калькулятор с сохранением расчетов.
- Калькулятор траншевой ипотеки.
- Клиенты и сохраненные клиентские расчеты.
- Пользователи с кастомной моделью и входом по email или телефону.
- Экспорт/импорт данных и работа с Excel.
- Healthcheck endpoint: `/health/`.

## Технологический стек

- Python 3.12+
- Django 6.0
- PostgreSQL 18
- Gunicorn
- nginx
- Docker Compose
- django-bootstrap5
- pytest + pytest-django
- OpenPyXL

## Архитектура Docker Compose

Compose запускает три сервиса:

- `nginx` - публичная HTTP-точка входа, проксирует запросы в Django и отдает
  собранную статику.
- `web` - Django + Gunicorn. При старте ждет PostgreSQL, выполняет
  `collectstatic`, применяет миграции и запускает Gunicorn.
- `db` - PostgreSQL 18. Данные хранятся в named volume `postgres_data`.

Статика хранится в named volume `staticfiles`. PostgreSQL не публикуется наружу
и доступен только внутри Docker-сети.

## Быстрый запуск через Docker Compose

Создать `.env`:

```bash
cp .env.example .env
```

Заполнить обязательные значения:

```env
DEBUG=False
SECRET_KEY=replace-with-long-random-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,web
CSRF_TRUSTED_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
DB_NAME=real_estate_investing
DB_USER=real_estate_investing
DB_PASSWORD=replace-with-strong-database-password
DB_HOST=db
DB_PORT=5432
NGINX_PORT=8080
EMAIL_PORT=25
```

Собрать и запустить контейнеры:

```bash
docker compose up -d --build
```

Проверить состояние:

```bash
docker compose ps
docker compose logs --tail 100 web
```

Открыть приложение:

```text
http://localhost:8080/
```

Если порт `8080` занят, указать другой порт в `.env`, например:

```env
NGINX_PORT=8081
CSRF_TRUSTED_ORIGINS=http://localhost:8081,http://127.0.0.1:8081
```

## Локальный запуск без Docker

Для локального запуска нужен PostgreSQL и заполненный `.env`.

Создать виртуальное окружение:

```bash
python -m venv .venv
```

Активировать на Windows:

```powershell
.\.venv\Scripts\Activate.ps1
```

Активировать на Linux/macOS:

```bash
source .venv/bin/activate
```

Установить зависимости:

```bash
pip install -r requirements.txt
```

Пример локального `.env`:

```env
DEBUG=True
SECRET_KEY=local-development-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1
CSRF_TRUSTED_ORIGINS=http://localhost:8000,http://127.0.0.1:8000
DB_NAME=real_estate_investing
DB_USER=real_estate_investing
DB_PASSWORD=replace-with-local-password
DB_HOST=localhost
DB_PORT=5432
EMAIL_PORT=25
```

Применить миграции и запустить сервер:

```bash
python manage.py migrate
python manage.py runserver
```

Открыть:

```text
http://127.0.0.1:8000/
```

## Основные URL

- `/` - главная страница.
- `/admin/` - Django admin.
- `/health/` - healthcheck.
- `/users/` - регистрация, вход и профиль.
- `/property/` - объекты недвижимости.
- `/property/complexes/` - жилые комплексы.
- `/property/developers/` - застройщики.
- `/property/dictionaries/` - справочники недвижимости.
- `/locations/` - справочники локаций.
- `/bank/` - банки и банковские справочники.
- `/bank/key-rate/` - ключевая ставка.
- `/mortgage/` - ипотечный калькулятор.
- `/mortgage/calculations/` - сохраненные ипотечные расчеты.
- `/trench-mortgage/` - калькулятор траншевой ипотеки.
- `/customers/` - клиенты.
- `/api/` - внутренние API для интерфейса.

## Тесты и проверки

Запустить Django check:

```bash
python manage.py check
```

Запустить тесты:

```bash
python -m pytest
```

Через Docker:

```bash
docker compose exec web python manage.py check
docker compose exec web python -m pytest
```

## Backup и восстановление базы

Создать backup PostgreSQL:

```bash
mkdir -p ~/backups
docker compose exec db sh -c 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" > /tmp/backup.dump'
docker compose cp db:/tmp/backup.dump ~/backups/real_estate_investing-$(date +%Y-%m-%d-%H%M).dump
```

Подробная инструкция по backup/restore находится в
`.documentation/backup_restore.md`.

## Документация по эксплуатации

Эксплуатационная документация находится в `.documentation/`:

- `README.md` - карта документации.
- `server_setup.md` - подготовка чистого Ubuntu-сервера.
- `application_initial_setup.md` - первичная настройка приложения на сервере.
- `manual_deployment.md` - ручной деплой после изменений в Git.
- `backup_restore.md` - backup и восстановление PostgreSQL.
- `https_setup.md` - настройка HTTPS через Caddy.
- `production_update_checklist.md` - checklist перед production-обновлением.
- `troubleshooting.md` - типовые ошибки и диагностика.

## Структура проекта

```text
real_estate_investing/
├── bank/                    # Банки, программы и ключевая ставка
├── core/                    # Общие endpoint'ы и healthcheck
├── customer/                # Клиенты и клиентские расчеты
├── homepage/                # Главная страница
├── location/                # Регионы, города, районы, метро
├── mortgage/                # Ипотечный калькулятор
├── property/                # Недвижимость, ЖК, застройщики, справочники
├── trench_mortgage/         # Траншевая ипотека
├── users/                   # Пользователи и аутентификация
├── real_estate_investing/   # Настройки, urls, wsgi/asgi
├── static/                  # CSS, JS, изображения
├── templates/               # Django templates
├── docker/                  # nginx config и Django entrypoint
├── .documentation/          # Документация эксплуатации
├── compose.yaml
├── Dockerfile
└── requirements.txt
```

## Переменные окружения

Полный список переменных описан в `.env.example`.

Ключевые переменные:

- `DEBUG`
- `SECRET_KEY`
- `ALLOWED_HOSTS`
- `CSRF_TRUSTED_ORIGINS`
- `DB_NAME`
- `DB_USER`
- `DB_PASSWORD`
- `DB_HOST`
- `DB_PORT`
- `NGINX_PORT`
- `EMAIL_*`

Не коммитить `.env` и реальные секреты в Git.
