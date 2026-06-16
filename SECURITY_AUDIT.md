# Security Audit — `real_estate_investing`

**Дата аудита:** 2026-06-16
**Стек:** Django 6.0.4, PostgreSQL 18, Gunicorn + nginx, Docker Compose, Python 3.13.

> Каждая находка содержит: серьёзность, расположение (файл:строка), описание проблемы и план исправления. Серьёзность: 🔴 Critical · 🟠 High · 🟡 Medium · 🟢 Low.

---

## Сводка находок

| #  | Серьёзность | Кратко |
|----|-------------|--------|
| B1 | 🔴 Critical | Вся бизнес-логика в `property/` и `mortgage/` доступна без аутентификации |
| B2 | 🔴 Critical | API `/api/*` отдаёт данные без авторизации |
| B3 | 🔴 Critical | Нет проверки владения объектом (IDOR) в `mortgage/` |
| B4 | 🔴 Critical | Продакшен-секреты в локальном `.env`, небезопасные fallback'и в `settings.py`/`compose.yaml` |
| B5 | 🟠 High | `DEBUG=True` и отсутствие всех `SECURE_*`/cookie/HSTS настроек |
| B6 | 🟠 High | Нет `AUTH_PASSWORD_VALIDATORS` |
| B7 | 🟠 High | Нет brute-force защиты на login/registration/password-reset |
| B8 | 🟠 High | Баг в `EmailOrPhoneBackend` при коллизии email/phone — молча логинит |
| B9 | 🟡 Medium | Загрузка файлов без валидации типа/размера |
| B10 | 🟡 Medium | Инфраструктура: секреты в Docker-слоях, неверный volume Postgres, нет TLS/cap-drop |
| B11 | 🟡 Medium | Email без шифрования по умолчанию (reset-токены в cleartext) |

---

## Детальное описание проблем

### B1. 🔴 Critical — Вся бизнес-логика доступна без аутентификации

**Расположение:** `property/views.py` (все классы), `mortgage/views.py` (все функции)
**Проверка:** `findstr /I "login_required LoginRequiredMixin permission_required"` по обоим файлам → **0 совпадений**.

**Описание:**
- `property/views.py` — полный CRUD (создание/редактирование/удаление) застройщиков, ЖК, объектов недвижимости выполняется **анонимным POST-запросом**. В частности `BaseCatalogView.post()` (`property/views.py:492`) по параметру `action=delete` удаляет строки справочников (типы/классы недвижимости, планировки, отделки, виды из окна, типы транспорта).
- `mortgage/views.py` — `calculation_delete` (`:1080`), `trench_calculation_delete` (`:1226`), `calculation_detail` (`:1088`), списки расчётов — без логина.
- Контраст: в `customer/` все view корректно используют `LoginRequiredMixin` (`customer/views.py:1, 28`). Расхождение по проекту.

**План исправления:**
1. На каждый view-класс в `property/views.py` добавить `LoginRequiredMixin` (в начало MRO). На function-based views в `mortgage/views.py` — декоратор `@login_required`.
2. Для административных операций (создание/редактирование/удаление справочников в `BaseCatalogView`) потребовать `@permission_required` или `UserPassesTestMixin` (is_staff).
3. Покрыть тестами: анонимный запрос к каждому protected endpoint → 302/403.

---

### B2. 🔴 Critical — API `/api/*` отдаёт данные без авторизации

**Расположение:** `property/api_urls.py:9, 25, 41, 81`

**Описание:** Четыре endpoint (`cities/`, `districts/`, `complexes/`, `buildings/`) — bare function views, смонтированы публично в `real_estate_investing/urls.py:19` (`path('api/', include('property.api_urls'))`). Любой анонимный клиент может перечислить всю иерархию локаций/ЖК/корпусов/застройщиков.

**План исправления:**
1. Добавить `@login_required` на каждую функцию (`cities_api`, `districts_api`, `complexes_api`, `buildings_api`).
2. Либо перевести API на DRF с явными permission classes (`IsAuthenticated`).
3. Рассмотреть кэширование ответов (см. Performance P2) — справочные данные меняются редко.

---

### B3. 🔴 Critical — Нет проверки владения объектом (IDOR)

**Расположение:** `mortgage/views.py:1083, 1090, 1211, 1227, 1236`; `mortgage/models.py:15`

**Описание:**
- `calculation_delete` (`:1083`): `get_object_or_404(MortgageCalculation, pk=pk)` — удаление/просмотр только по PK, без проверки владельца.
- `calculation_list` (`:1040`): `MortgageCalculation.objects.all()` — все посетители видят все сохранённые расчёты.
- Корень проблемы: модель `MortgageCalculation` (`mortgage/models.py:15`) **не имеет поля `user`** — изоляция по пользователю структурно невозможна. То же для `TrenchMortgageCalculation`.

**План исправления:**
1. Добавить `user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=CASCADE, related_name='mortgage_calculations')` в `MortgageCalculation` и `TrenchMortgageCalculation`. Создать миграцию (с дефолтом для существующих строк, например, назначить первого админа).
2. В `get_queryset()` списков и в `get_object()` detail/delete добавить фильтр `user=request.user`.
3. В POST-привязке расчётов к клиенту (`:1013-1018`) фильтровать `calculations` по `user=request.user`.

---

### B4. 🔴 Critical — Продакшен-секреты и небезопасные fallback'и

**Расположение:** `.env` (локально), `real_estate_investing/settings.py:30`, `compose.yaml:27, 30-32`

**Описание:**
Локальный `.env` содержит реальные продакшен-данные:
```
DEBUG=True
SECRET_KEY=%-+#vp2)jwz#e_bl#*d92)%c%oh10*ta-e)1tfu-e#vuelqs3=
DB_USER=pavel_murlykin
DB_PASSWORD=Super_Tiger_Son_19
```
`.env` **не в git** (подтверждено `git ls-files` — отслеживается только `.env.example`), но:
- `settings.py:30` — `SECRET_KEY = os.getenv('SECRET_KEY', '')`: пустой fallback. Если переменная не задана, Django стартует с криптографически пустым ключом → подписанные cookies, reset-токены, session-данные подделываются.
- `compose.yaml:27` — `SECRET_KEY: ${SECRET_KEY:-unsafe-compose-development-secret-key-change-me}`: plaintext-fallback в compose.
- `compose.yaml:30-32` — `DB_PASSWORD:-real_estate_investing_password`: слабый guessable дефолт.

**План исправления:**
1. **Ротировать** `SECRET_KEY` и `DB_PASSWORD` (считаем скомпрометированными, т.к. хранились локально в plaintext). Сгенерировать новые (`python -c "import secrets; print(secrets.token_urlsafe(50))"`).
2. `settings.py:30` — убрать пустой fallback, поднимать `ImproperlyConfigured`, если `SECRET_KEY` пуст при не-DEBUG.
3. В `compose.yaml` убрать небезопасные plaintext-дефолты; использовать `env_file` с `required: true` либо обязательную передачу секрета через Docker secrets / vault.
4. Добавить `.env` в `.gitignore` (если ещё нет) и проверить `git log --all -- .env`, что секреты никогда не попадали в историю.

---

### B5. 🟠 High — `DEBUG=True` и отсутствие security-настроек

**Расположение:** `.env:1` (`DEBUG=True`), `real_estate_investing/settings.py`
**Проверка:** `findstr` по `SECURE_ | SESSION_COOKIE | CSRF_COOKIE | X_FRAME | HSTS | REFERRER | PROXY_SSL` → **0 совпадений**.

**Описание:** Отсутствуют все продакшен-настройки безопасности:
- `SECURE_SSL_REDIRECT` — нет редиректа HTTP→HTTPS.
- `SESSION_COOKIE_SECURE` / `CSRF_COOKIE_SECURE` — cookies уходят в cleartext по HTTP.
- `SECURE_HSTS_SECONDS` — нет HSTS.
- `SECURE_CONTENT_TYPE_NOSNIFF`, `SECURE_REFERRER_POLICY`, `X_FRAME_OPTIONS` — не заданы.
- `SECURE_PROXY_SSL_HEADER` — **критично**: nginx терминирует TLS и шлёт `X-Forwarded-Proto`, но без этой настройки `request.is_secure()` всегда `False`, и secure-cookies/HSTS не сработают.
- `DEBUG=True` в `.env` → на любом 500 Django отдаёт полный stack trace (исходники, env, настройки).

**План исправления:**
Добавить в `settings.py` блок, зависящий от `DEBUG`:
```python
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30  # 30 дней
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_CONTENT_TYPE_NOSNIFF = True
    SECURE_REFERRER_POLICY = 'same-origin'
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    X_FRAME_OPTIONS = 'DENY'

# Всегда:
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```
Перевести продакшен-развертывание на `DEBUG=False`.

---

### B6. 🟠 High — Нет `AUTH_PASSWORD_VALIDATORS`

**Расположение:** `real_estate_investing/settings.py`
**Проверка:** `findstr PASSWORD_VALIDATORS` по settings → **0 совпадений**.

**Описание:** Django поставляет 4 валидатора (`UserAttributeSimilarityValidator`, `MinimumLengthValidator`, `CommonPasswordValidator`, `NumericPasswordValidator`); ни один не настроен. В сочетании с `UserCreationForm` (`users/forms.py:15`) пользователи могут зарегистрироваться с паролями `1`, `password`, `12345678`.

**План исправления:**
Добавить в `settings.py`:
```python
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
     'OPTIONS': {'min_length': 8}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]
```

---

### B7. 🟠 High — Нет brute-force защиты

**Расположение:** `users/views.py` (`UserLoginView:39`, `UserRegistrationView:10`), `users/urls.py:35-66` (password-reset flow)
**Проверка:** `findstr ratelimit | django-axes | throttle` → **0 совпадений**, в `requirements.txt` нет rate-limit библиотек.

**Описание:** Логин, регистрация, весь password-reset flow (включая `PasswordResetView`, `PasswordResetConfirmView`) — без ограничений частоты. → брутфорс паролей, массовая регистрация аккаунтов, бомбёжка reset-email.

**План исправления:**
1. Установить `django-axes` (блокировка по IP/username после N неудач) или `django-ratelimit` (декораторы `@ratelimit` на view).
2. Покрыть: login (5 попыток/мин), registration (3/час/IP), password-reset (3/час/email).
3. Настроить капчу (hCaptcha/Turnstile) на login после первых неудач.

---

### B8. 🟠 High — Баг в `EmailOrPhoneBackend` при коллизии email/phone

**Расположение:** `users/backends.py:39-56`

**Описание:** Запрос `Q(email__iexact=login_value) | Q(phone_number=phone_number)` может легально совпасть с двумя разными строками (одна по email, другая по телефону, т.к. `email` и `phone_number` — независимые unique-поля). В ветке `MultipleObjectsReturned` (`:51-56`) берётся `.order_by('id').first()` и **молча логинит** этого пользователя — можно спровоцировать контролируемым идентификатором.
Дополнительно: `email__iexact` (`:39`) компилируется в `LOWER(email)=`, что **не использует** case-sensitive unique index → seq-scan при каждой попытке логина (также проблема производительности — см. Performance P3/P4).

**План исправления:**
1. В `MultipleObjectsReturned` **не логинить**, возвращать `None` + логировать предупреждение.
2. Хранить email в нижнем регистре (уже делается в `clean_email`) и использовать обычный `email=` вместо `email__iexact` — будет использовать unique index. Либо добавить functional index `Lower('email')`.
3. Привести нормализацию телефона к каноническому виду (E.164 через `phonenumbers`), чтобы сравнение было надёжным.

---

### B9. 🟡 Medium — Загрузка файлов без валидации типа/размера

**Расположение:** `property/forms.py:103-109, 262` (`layout_image`, `floor_plan_image`, `window_view_image`, `photo`)

**Описание:** `forms.FileInput` для изображений без проверки MIME/расширения/размера. `ImageField` проверяет только декодируемость файла, не ограничивает размер и не отсекает polyglot/exploit-файлы. В `settings.py` нет `FILE_UPLOAD_MAX_MEMORY_SIZE` / `DATA_UPLOAD_MAX_MEMORY_SIZE`, при этом `DATA_UPLOAD_MAX_NUMBER_FIELDS = 10000` (10× от дефолта Django).

**План исправления:**
1. Добавить валидатор, проверяющий content-type (`image/jpeg`, `image/png`, `image/webp`) и расширение, плюс лимит размера (например, 5 MB).
2. Задать `FILE_UPLOAD_MAX_MEMORY_SIZE` и `DATA_UPLOAD_MAX_MEMORY_SIZE` в `settings.py`.
3. Вернуть `DATA_UPLOAD_MAX_NUMBER_FIELDS` к 1000 (или обосновать 10000).

---

### B10. 🟡 Medium — Инфраструктура

**Расположение:** `Dockerfile`, `compose.yaml`, `docker/nginx/default.conf`, `core/views.py:4`

**Описание:**
- `Dockerfile:15` `COPY . .` копирует весь репо (включая `.env`, если он в build context) в образ — секреты остаются в слоях образа.
- `Dockerfile:1` `python:3.12-slim` — не pinned по digest; нет multi-stage build.
- `compose.yaml:10` — volume монтируется в `/var/lib/postgresql` вместо `/var/lib/postgresql/data` — известная проблема инициализации Postgres.
- `compose.yaml:56-57` — nginx публикует только HTTP (порт 80), TLS не настроен нигде.
- Нет `cap_drop: [ALL]`, `security_opt: ["no-new-privileges:true"]`, `read_only: true`.
- `core/views.py:4` `health_check` открыт наружу на `/health/`.

**План исправления:**
1. Создать `.dockerignore` с `.env`, `.venv`, `.git`, `media/`, `__pycache__`.
2. Multi-stage Dockerfile, pin по digest, `pip install --require-hashes` (или `pip-tools`/`uv` lock).
3. В `compose.yaml` исправить volume на `/var/lib/postgresql/data`.
4. Добавить `cap_drop: [ALL]`, `security_opt: ["no-new-privileges:true"]`, `read_only: true` (с `tmpfs` для `/tmp`).
5. Настроить HTTPS на nginx (Let's Encrypt / Caddy).
6. Healthcheck зарутить под `/internal/health/`, не проксировать наружу.

---

### B11. 🟡 Medium — Email без шифрования по умолчанию

**Расположение:** `real_estate_investing/settings.py:130-145`

**Описание:** `EMAIL_PORT=25`, `EMAIL_USE_TLS=False`, `EMAIL_USE_SSL=False` по умолчанию. Reset-токены (содержат токен сброса пароля, `users/urls.py:36-58`) уходят plaintext по SMTP. `EMAIL_USE_TLS` и `EMAIL_USE_SSL` — взаимоисключающие, без проверки.

**План исправления:**
1. Продакшен-дефолт `EMAIL_USE_TLS=True` (порт 587) или `EMAIL_USE_SSL=True` (порт 465).
2. Добавить guard: если включены оба — поднимать `ImproperlyConfigured`.

---

## ✅ Что проверено и чисто
- Нет `raw()` / `cursor.execute` / `eval` / `exec` / `pickle` / `subprocess` с пользовательским вводом.
- Нет `mark_safe` / `|safe` в шаблонах (XSS через шаблоны не подтверждён).
- Нет `csrf_exempt` нигде; `CsrfViewMiddleware` включён.
- `ModelForm` нигде не используют `fields='__all__'` (явные списки полей).
- `.env` **не в git** (только `.env.example`).
- В `customer/` авторизация и prefetch сделаны корректно.
- Dockerfile использует non-root `django` user.
- `User` в форме регистрации: поле `user` исключено и задаётся сервером — корректный паттерн.

---

## План действий по приоритетам

### Этап 1 — Критично, немедленно (доступ)
1. `LoginRequiredMixin` / `@login_required` на все views в `property/views.py` и `mortgage/views.py`.
2. `@login_required` на `/api/*` (`property/api_urls.py`).
3. Поле `user` FK в `MortgageCalculation`/`TrenchMortgageCalculation` + миграция + фильтр по владельцу в queryset/get_object.
4. Запретить POST-write анонимам в `BaseCatalogView.post`.
5. Регресс: `python manage.py check && pytest`.

### Этап 2 — Секреты и конфигурация (1-2 дня)
1. Ротировать `SECRET_KEY`, `DB_PASSWORD`.
2. `settings.py:30` — убрать пустой fallback, поднимать `ImproperlyConfigured`.
3. `compose.yaml` — убрать plaintext-fallback'и, `env_file required: true`.
4. Добавить `AUTH_PASSWORD_VALIDATORS`.
5. Добавить security-настройки (B5), зависящие от `DEBUG`.
6. Установить rate-limiting (django-axes / django-ratelimit).

### Этап 3 — Баги аутентификации
1. `EmailOrPhoneBackend` — не логинить при коллизии, логировать.
2. `email=` вместо `email__iexact` (+ canonical lowercase).
3. Нормализация телефона к E.164.
4. Валидация загрузки изображений (MIME/размер).
5. `DATA_UPLOAD_MAX_NUMBER_FIELDS` → 1000.

### Этап 5 — Инфраструктура
1. `.dockerignore` (`.env`, `.venv`, `.git`, `media/`).
2. Multi-stage Dockerfile, digest-pin, hashes.
3. `compose.yaml` volume → `/var/lib/postgresql/data`.
4. `cap_drop`, `no-new-privileges`, `read_only`.
5. HTTPS на nginx.
6. `EMAIL_USE_TLS=True`.
7. Healthcheck → `/internal/health/`.

### Этап 6 — Процесс (долгосрочно)
- `bandit` (SAST) + `pip-audit` в CI.
- `python manage.py check --deploy` в CI — он сам flagged бы B4/B5/B6.
- Тесты на permission-чеки (аноним → 302/403).

---

**Самое опасное прямо сейчас — B1-B3:** анонимный пользователь может создать/удалить/просмотреть любые данные через веб и API. Начать с Этапа 1.
