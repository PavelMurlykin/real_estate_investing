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

## Новый React frontend

Новый интерфейс доступен по адресу /app/. Он внедряется поэтапно и работает
рядом с существующими Django-шаблонами: старые URL остаются доступными до
завершения миграции и полного тестирования.

Рабочий срез включает общую React-оболочку, левую навигацию, адаптивную
главную страницу, каталог объектов с серверным поиском и пагинацией,
детальную карточку объекта с галереей изображений, приватный список и
read-only карточку клиента с оценкой финансового потенциала, а также рыночный
ипотечный калькулятор с банковскими программами и графиком платежей, сохранение
расчёта для выбранного объекта, приватную историю и страницу детального расчёта.
Сохранённый сценарий можно повторно открыть как образец, выгрузить в Excel
или Word и удалить после явного подтверждения. React-маршруты доступны по
адресам /app/, /app/properties, /app/properties/:id, /app/customers,
/app/customers/:id, /app/mortgage, /app/mortgage/calculations и
/app/mortgage/calculations/:id.
API имеет версию /api/v1/ и использует текущие Django session authentication,
CSRF-защиту, правила доступа и PostgreSQL. Создание, редактирование и удаление
клиентов, связанные расчёты и Word-отчёты пока явно открываются в сохранённой
Django-версии. Старая форма /mortgage/ также сохранена для траншевых расчётов
и проверки функционального паритета до завершения миграции.

Установить зависимости и запустить frontend для разработки:

```powershell
cd frontend
npm ci
npm run dev
```

Vite проксирует API и переходы к ещё не перенесённым Django-страницам на
локальный сервер http://127.0.0.1:8000. Production-сборка:

```powershell
cd frontend
npm run lint
npm run typecheck
npm test
npm run build
```

Команда docker compose up -d --build собирает React автоматически отдельным
Node-этапом и добавляет результат в общий Django static pipeline.

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

Установить dev-инструменты и запустить локальные security checks:

```bash
pip install -r requirements-dev.txt
python -m pip_audit -r requirements.txt
python -m bandit -r bank core customer homepage location mortgage property real_estate_investing trench_mortgage users -x "*/migrations/*,*/tests.py"
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
- `role_model.md` - ролевая модель, матрица доступа и правила проверки прав.
- `https_setup.md` - настройка HTTPS через Caddy.
- `production_update_checklist.md` - checklist перед production-обновлением.
- `troubleshooting.md` - типовые ошибки и диагностика.

## Структура проекта

```text
real_estate_investing/
├── bank/                    # Банки, программы и ключевая ставка
├── core/                    # Общие endpoint'ы и healthcheck
├── customer/                # Клиенты и клиентские расчеты
├── api_v1/                  # Версионированный API нового frontend
├── frontend/                # React + TypeScript + Vite
├── homepage/                # Главная страница
├── location/                # Регионы, города, районы, метро
├── mortgage/                # Ипотечный калькулятор
├── property/                # Недвижимость, ЖК, застройщики, справочники
├── trench_mortgage/         # Траншевая ипотека
├── users/                   # Пользователи и аутентификация
├── real_estate_investing/   # Настройки, urls, wsgi/asgi
├── react_frontend/          # Django gateway для React routes
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
- `DATA_UPLOAD_MAX_NUMBER_FIELDS`
- `DATA_UPLOAD_MAX_MEMORY_SIZE`
- `FILE_UPLOAD_MAX_MEMORY_SIZE`
- `PROPERTY_IMAGE_MAX_UPLOAD_SIZE`
- `PUBLIC_CATALOG_API_MAX_RESULTS`

Не коммитить `.env` и реальные секреты в Git.
