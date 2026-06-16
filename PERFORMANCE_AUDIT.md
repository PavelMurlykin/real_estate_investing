# Performance Audit — `real_estate_investing`

**Дата аудита:** 2026-06-16
**Стек:** Django 6.0.4, PostgreSQL 18, Gunicorn + nginx, Docker Compose, Python 3.13.

> Каждая находка содержит: серьёзность, расположение (файл:строка), описание проблемы и план исправления. Серьёзность: 🔴 High · 🟠 Medium · 🟡 Low.

---

## Сводка находок

| #  | Серьёзность | Кратко |
|----|-------------|--------|
| P1 | 🔴 High | Списки расчётов без пагинации грузят всю таблицу |
| P2 | 🔴 High | Каскадные справочники сериализуются в JSON на каждый запрос калькулятора |
| P3 | 🟠 Medium | N+1 и двойное вычисление querysets (homepage, auth backend, attach-цикл) |
| P4 | 🟠 Medium | Отсутствуют индексы на часто фильтруемых/сортируемых полях |
| P5 | 🟠 Medium | Синхронная генерация Word/Excel в request-цикле |
| P6 | 🟡 Low | Дополнительные полнотабличные querysets для фильтров на каждой странице списка |
| P7 | 🟡 Low | `email__iexact` в auth backend не использует unique index |

---

## Детальное описание проблем

### P1. 🔴 High — Списки без пагинации грузят всю таблицу

**Расположение:**
- `mortgage/views.py:1031-1041` — `calculation_list`
- `mortgage/views.py:1211-1223` — `trench_calculation_list`
- `property/views.py:75, 337-368` — `BaseCatalogView` / `DictionaryCatalogView`

**Описание:**
- `calculation_list` (`:1040`): `MortgageCalculation.objects...all()` без `.count()`/slice/пагинации, целиком передаётся в шаблон (`:1064`). Шаблон `templates/mortgage/mortgage_list.html:63` итерирует полный набор + рендерит вложенную таблицу-детайл на каждой строке (`:106-114`). Grep подтвердил: нигде под `templates/mortgage` нет `paginate`/`page_obj`/`is_paginated`.
- `trench_calculation_list` (`:1211-1223`): `_get_trench_calculation_queryset()` (`:1139-1151`) возвращает все строки `.prefetch_related('trenches')` без лимита; целиком в шаблон (`:1221`).
- `BaseCatalogView`/`DictionaryCatalogView` — это `TemplateView` (не `ListView`), `build_rows` (`:337-368`) итерирует `for obj in queryset:` (`:351`) всю таблицу без пагинации и без ограничения строк.
- Контраст: `DeveloperListView`, `RealEstateComplexListView`, `PropertyListView` имеют `paginate_by = 20`; `CustomerListView` — `paginate_by = 20` (`customer/views.py:73`). Несогласованность по проекту.

**План исправления:**
1. Перевести `calculation_list` / `trench_calculation_list` на `ListView` + `paginate_by=20`, в шаблоны добавить `paginate` block / include.
2. `BaseCatalogView`/`DictionaryCatalogView` — добавить пагинацию (либо унаследоваться от `ListView`, либо вручную через `Paginator`).
3. Для вложенной таблицы-детайл в `mortgage_list.html` рассмотреть lazy-loading (AJAX/HTMX) вместо рендера всех строк сразу.

---

### P2. 🔴 High — Каскадные справочники сериализуются в JSON на каждый запрос

**Расположение:**
- `mortgage/views.py:283-396` — `_get_property_form_data()`, `_get_mortgage_program_form_data()`
- `property/views.py:1056-1090` — `RealEstateComplexFormsetMixin.get_context_data`
- `property/views.py:1430-1481` — `PropertyFormContextMixin.get_location_context`

**Описание:**
- `_get_property_form_data()` (`:283-322`) и `_get_mortgage_program_form_data()` (`:343-396`) вызываются на **каждом** запросе к калькулятору (`:612-613`). Грузят ВСЕ `Property` (с `select_related`, без `.only()`, без пагинации) в Python-список (`:293-322`), плюс полные `cities`/`districts`/`complexes`/`buildings` (`:302-317`), плюс все банки/программы с вложенным циклом по `regional_credit_limits` (`:387-392`). Результат сериализуется в JSON для фронтенд-каскада. Без кэширования.
- `RealEstateComplexFormsetMixin.get_context_data` (`:1056-1090`): `list(City.objects...)`, `list(District.objects...)`, `list(Metro.objects...)`, `list(existing_complexes...)` — целиком в память на каждый GET формы комплекса.
- `PropertyFormContextMixin.get_location_context` (`:1430-1481`): то же для `cities`/`districts`/`complexes`/`buildings`. Дополнительно: сырые querysets передаются в контекст (`:1447-1452`) И материализуются через `list(values(...))` — двойное вычисление.

**План исправления:**
1. Кэшировать справочники через `cache.get_or_set('property_form_data', builder, timeout=600)` (TTL ~10 мин), инвалидировать при изменении соответствующих моделей (сигналы `post_save`/`post_delete`).
2. Не материализовать `list(...)` целиком — передавать queryset или использовать `.values()` лениво. Для форм достаточно данных, отфильтрованных по выбранному родителю (фронтенд уже делает каскад).
3. Убрать двойное вычисление: вычислить queryset один раз, сохранить в переменную, переиспользовать.

---

### P3. 🟠 Medium — N+1 и двойное вычисление querysets

**Расположение:**
- `homepage/views.py:42-71`
- `homepage/views.py:24-38`
- `users/backends.py:47-56`
- `mortgage/views.py:1013-1018`

**Описание:**
- `homepage/views.py:42-64`: `complexes` вычисляется дважды — в list-comprehension (`:58`) и повторно при итерации в шаблоне (`'complexes': complexes`, `:71`). Две полных выборки + две конструкции объектов для одних и тех же строк.
- `homepage/views.py:24-38`: до 4 запросов на определение `selected_city` — `cities` (`:24`, запрос #1), `cities.filter(pk=...)` (`:33`, #2), `cities.filter(name='Санкт-Петербург').first() or cities.first()` (`:36-38`, #3 и #4). `name` без индекса.
- `users/backends.py:47-56`: при `MultipleObjectsReturned` (`:51`) бэкенд выполняет **второй** запрос (`.filter(query).order_by('id').first()`) после того как `.get()` уже выбрал-отбросил строку.
- `mortgage/views.py:1013-1018`: цикл `for calculation in calculations: _attach_calculation_to_customer(...)` где каждый вызов (`:74-83`) делает `get_or_create` → по одному запросу на каждый выбранный расчёт (N запросов вместо bulk).

**План исправления:**
1. `homepage/views.py` — вычислить `complexes` один раз, сохранить в список (`complexes = list(...)`), переиспользовать в comprehension и контексте.
2. Определить `selected_city` одним запросом по PK или одной фильтрацией, не перефильтровать один и тот же queryset многократно.
3. Auth backend — см. Security B8 (убрать коллизию-ветку целиком).
4. Bulk-операция: собрать существующие PK через один запрос, `bulk_create` недостающие `CustomerCalculation`.

---

### P4. 🟠 Medium — Отсутствуют индексы на часто фильтруемыхых/сортируемых полях

**Расположение:** `property/models.py`, `core/models.py`

**Описание:** Поля, используемые в `filter()`/`order_by()`, без `db_index=True`:
- `property/models.py:258` `RealEstateComplexBuilding.number` — `order_by` (Meta `:297`; views `:705, 879, 1280`). Составной `UniqueConstraint(['number', 'real_estate_complex'])` (`:299`) создаёт индекс, но он не покрывает глобальную сортировку по `number`.
- `property/models.py:450` `Property.apartment_number` — `order_by` (Meta `:505`; views `:1273, 1281`) и `filter(apartment_number__icontains=...)` (`:1253`). Нет индекса → full scan на дефолтной сортировке.
- `core/models.py:11-21` `BaseModel.is_active`, `created_at` — `created_at` в `list_filter`/`ordering` всех моделей; `is_active` фильтруется во всех view. Оба без `db_index`. Влияет на **каждую** модель-наследник.

**План исправления:**
1. Добавить `db_index=True` на `RealEstateComplexBuilding.number`, `Property.apartment_number`, `BaseModel.is_active`, `BaseModel.created_at`.
2. Создать миграцию (`makemigrations` + `migrate`).
3. Для `icontains`-поиска по имени рассмотреть `icontains`-friendly index (functional или триграммный `pg_trgm`), либо полнотекстовый поиск для больших таблиц.

---

### P5. 🟠 Medium — Синхронная генерация Word/Excel в request-цикле

**Расположение:** `mortgage/views.py:978-979, 939, 942, 1116, 1240`; `mortgage/word.py`; `mortgage/excel.py`

**Описание:**
- `export_mortgage_word(report_data)` (`:978`), `export_mortgage_excel(report_data)` (`:979`), `export_trench_mortgage_word(...)` (`:939`), экспорт в detail-views (`:1116, 1240`) — всё строит документы синхронно внутри request/response цикла. Celery/фоновых задач нет.
- `mortgage/excel.py:459-469` `_apply_column_widths`: `for column in worksheet.columns:` обходит **все** ячейки для вычисления max длины строки — O(rows×cols). Для ипотеки на 30 лет — до 360 строк × колонки.
- `mortgage/word.py` строит полный `.docx` из шаблона, встраивает изображения (`_replace_cell_image:698-709`), сериализует через `BytesIO`.
- Пачка запросов на экспорт заблокирует воркеры Gunicorn.

**План исправления:**
1. Вынести генерацию документов в фоновую задачу (Celery + Redis/RQ, или `django-q2` для лёгкого старта).
2. Пользователь запрашивает экспорт → создаётся задача, возвращается страница «генерируется» с опросом статуса → по готовности отдаётся файл (или ссылка).
3. В `excel.py` `_apply_column_widths` кэшировать максимальную длину в один проход при записи строк, а не отдельным обходом всех ячеек.

---

### P6. 🟡 Low — Дополнительные полнотабличные querysets для фильтров на каждой странице списка

**Расположение:** `property/views.py:943-948, 1360-1370`; `property/views.py:843-872`

**Описание:**
- `PropertyListView.get_context_data` (`:1360-1370`): на каждый рендер списка выполняются 5 querysets для выпадающих фильтров — `cities_for_filter`, `developers_for_filter`, `complexes_for_filter`, `buildings_for_filter`, `layouts_for_filter`. `buildings_for_filter` и `complexes_for_filter` растут без ограничений.
- `RealEstateComplexListView.get_context_data` (`:943-948`): то же — `developers_for_filter`, `cities_for_filter`, `classes_for_filter`, `types_for_filter`.
- `RealEstateComplexListView.get_queryset` (`:843-872`): `annotate(buildings_count=Count('realestatecomplexbuilding'))` (`:843`) + опциональный `filter(buildings_count=...)` (`:870`). Аннотация (group-by/join) выполняется на **каждом** запросе, даже когда фильтр не задан; фильтр по вычисляемому значению не использует индекс.

**План исправления:**
1. Кэшировать списки для фильтров (`cache.get_or_set`, TTL ~10-30 мин, инвалидация по сигналам).
2. `buildings_count` аннотацию выполнять только если в запросе есть соответствующий фильтр (условный `annotate`/`filter`).

---

### P7. 🟡 Low — `email__iexact` в auth backend не использует unique index

**Расположение:** `users/backends.py:39`; `users/models.py:20`

**Описание:** Поле `email` — `unique=True` (миграция создаёт case-sensitive btree-индекс). `Q(email__iexact=...)` компилируется в `LOWER(users.email) = LOWER(...)`, что **не может** использовать обычный unique index → каждая попытка логина = потенциальный seq/index scan по `users`. То же касается admin-поиска (`users/admin.py:36-42`).

**План исправления:**
1. Хранить email в нижнем регистре (уже делается в `clean_email`) и использовать `email=` вместо `email__iexact`.
2. Либо добавить functional index `Lower('email')` через `Index(Lower('email'), name='...')` в `Meta.indexes`.

---

## ✅ Что проверено и чисто (производительность)
- Основные list-view `Property`/`RealEstateComplex` используют `select_related`/`prefetch_related` корректно — N+1 там нет.
- `CustomerOwnedQuerysetMixin.get_queryset` (`customer/views.py:51-59`) делает nested `Prefetch` для `regional_credit_limits` — N+1 в customer-деталях нет.
- `annotate_calculation_table_values` (`mortgage/utils.py:36-44`) — вычисление DB-side, корректно.
- Нет `read()`/полной загрузки файлов в память в `property/forms.py` (`delete_saved_images` только удаляет).
- Списки customer (`CustomerListView`) — `paginate_by=20`, корректно.

---

## План действий по приоритетам

### Этап 4 — Производительность (реализуется в спринт)

| # | Действие | Файлы | Оценка |
|---|----------|-------|--------|
| 4.1 | Пагинация (`ListView` + `paginate_by=20`) в `calculation_list`, `trench_calculation_list`, `BaseCatalogView` | `mortgage/views.py`, `property/views.py`, шаблоны | 3-4 ч |
| 4.2 | Кэшировать справочники для калькулятора (`cache.get_or_set`, TTL ~10 мин, инвалидация по сигналам) | `mortgage/views.py:283-396` | 2 ч |
| 4.3 | Не материализовать `list(...)` целиком в `get_context_data`; убрать двойное вычисление querysets | `property/views.py:1056-1090, 1430-1481` | 2 ч |
| 4.4 | Починить двойное вычисление в `homepage/views.py:42-71` (вычислить `complexes` один раз) | `homepage/views.py` | 30 мин |
| 4.5 | `db_index=True` на `RealEstateComplexBuilding.number`, `Property.apartment_number`, `BaseModel.is_active`, `BaseModel.created_at` + миграция | `property/models.py`, `core/models.py` | 1 ч + миграция |
| 4.6 | Bulk-операция вместо цикла `get_or_create` в `calculation_list` POST | `mortgage/views.py:1013-1018` | 1 ч |
| 4.7 | Вынести генерацию Word/Excel в фоновую задачу (Celery + Redis / django-q2) | `mortgage/views.py`, `mortgage/word.py`, `mortgage/excel.py` | 1-2 дня |

### Дополнительно (низкий приоритет)
- Кэшировать querysets для выпадающих фильтров в list-view (`property/views.py:943-948, 1360-1370`).
- Условная `buildings_count` аннотация — только при наличии фильтра (`property/views.py:843-872`).
- Functional index `Lower('email')` или переход на `email=` в auth backend (`users/backends.py:39`).
- Оптимизация `_apply_column_widths` в `excel.py:459-469`.

---

**Наибольший эффект:** P1 (пагинация списков) и P2 (кэширование справочников калькулятора) — оба убирают O(вся таблица) на горячих путях. P5 (фон для экспортов) защищает воркеры от блокировок под нагрузкой.
