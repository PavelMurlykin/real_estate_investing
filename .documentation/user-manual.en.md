# User manual

Verified on November 1, 2026. Restored React features and page comparison results, including tables and calculation forms: [report](../.audit/REACT_DJANGO_PARITY_REPORT.md). Permanent regression tests compare the financial matrix against the Django form.

## Starting the application

Configure `.env` using `.env.example`, then run `docker compose up -d --build` from the repository root. Open the nginx address configured in `compose.yaml`. For local development use `.venv\Scripts\python.exe manage.py runserver` and Vite from `frontend` (`npm ci`, `npm run dev`). React is available at `/app/`; Django pages remain accessible when `REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED` is disabled.

After updating the Docker build, reload the browser page to load the updated interface. Its asset version updates automatically.

## Main sections

The catalog contains properties, developers, company groups and residential complexes. Property details show attributes, images and a link to the mortgage calculator. Catalog moderators manage property and location dictionaries. Banks, mortgage programs, developer programs and the key rate have separate sections. Imports and external updates require the appropriate permissions.

The customer section requires authentication. A customer profile contains contacts, preferences, budget and linked market/tranche calculations. Financial capacity is an initial estimate. Select linked calculations for a combined Word report or unlink them; deleting a customer does not delete the calculations themselves.

## Mortgage calculations

Select a property and enter its price, discount/markup, down payment, date, term and rate. Percentages and rubles synchronize using the most recently edited value. Market mortgages support a grace period; tranche mortgages support one to five tranches, with the last receiving the remaining amount. A button expands the schedule beyond the first 12 payments.

Authenticated users can save calculations for a selected or manually entered property. “Заполнить объект вручную” opens city, district, developer, complex, building, layout and decoration selectors, plus apartment number, area and floor fields. Dictionaries support search while typing and loading more choices; selecting a complex fills its location and developer. Existing apartments are identified by building and apartment number; creating a new apartment when saving requires catalog moderator permissions. Changing the property or conditions after calculating requires recalculation before saving: the previous result remains available for comparison and is marked as outdated. Saved histories provide details, Excel/Word exports, a new calculation based on a sample and deletion with confirmation.

Property search covers the entire catalog; previous/next buttons navigate choice pages. The selected property remains available while searching for alternatives. Excel and Word buttons beside the result export the current market or tranche calculation without saving or signing in, including manual properties or financial parameters alone. Exports create no catalog or history records.

Money values display two decimal places, including kopecks in payments and balances. Both calculators show the down payment percentage/date, base price and adjustment, exact term in months, rate and payment count. Market results also show the grace term/rate, separate grace/main payment counts and debt after the grace period. The tranche table includes overpayment per tranche; “Остаток к выдаче” means the amount yet to be disbursed. Saved details include the apartment layout when an image is uploaded; click it to open the full-size image.

When legacy URLs redirect to React, property/customer context is translated from `property_id`/`customer` to `propertyId`/`customerId`. Legacy filter and sorting names also translate to the new interface parameters and preserve the selected context.

## Developer programs and credit limits

The developer program list updates as you type the name of a company group, residential complex, bank or program. The same options are available in separate filters. The “Сбросить” button sits to the right of the final program filter on the same row and restores the full list.

Selecting a property and bank program applies active developer conditions: a specific complex takes priority over group-wide conditions. The adjustment, down payment, term, rate and grace period are populated; changing the program restores the base conditions. Zero rates are supported, including during the grace period. Exceeding the regional limit (or the federal fallback) shows the required/additional down payment and combined rate; apply your chosen option by editing the form fields. This is guidance, not an automatic calculation prohibition. A developer program's maximum loan amount is also considered when provided.

## Current migration limitations

Implementation and verification results are tracked in `.audit/REACT_PARITY_IMPLEMENTATION_PLAN.md`. “Django-форма”/“Прежняя версия” fallback links open the legacy screen directly even when redirects are enabled. The map depends on the mapping provider.

## Homepage and complex map

In “Жилые комплексы по городам”, select an active city; typing in the dictionary search finds it. The default is active Saint Petersburg, or the first active city by name. Cards show active complexes in active districts of that city, with a photo, developer, district, class, type and description. Links open complex details, its properties, and the map or presentation when available.

“Списком” and “На карте” switch views; the city and view remain in the URL. The first 50 complexes load immediately; “Показать ещё ЖК” loads more. The counter shows total and loaded counts; the map contains loaded complexes. Coordinates come from the map link or are resolved by complex name and city. When the map provider is unavailable or coordinates cannot be found, cards and direct links remain available; use “Повторить загрузку карты” to retry.

## Bank list

The bank list updates as you type a name in the search field. The “Программы” filter lets you select banks with or without mortgage programs. The “Сбросить” button sits to the right of that filter on the same row and restores the full list. On narrow screens, the table fits the available width and long bank names wrap onto multiple lines.

## Updating bank data

Expand “Ипотечные программы” under the bank name to see its programs, rates, minimum down payment, and published maximum term directly in the table.

Administrators can expand “Импорт банков из JSON” on the Banks tab or “Импорт ипотечных программ из JSON” on the Mortgage Programs tab. Select a UTF-8 JSON file of up to 1 MB and click “Импортировать”. The result shows how many rows were created, updated, or left unchanged. Validation errors prevent any changes for the selected section.

To populate the catalogs, use the [Russian bank snapshot](../data/bank-catalog-ru-2026-11.json). Upload the same file on the Banks tab first, then on the Mortgage Programs tab. The first upload adds banks by canonical name and updates logo URLs. The second updates the program directory and offer terms for existing banks. Existing links absent from the file are preserved. The file's `metadata` field lists its sources and coverage.

Version 1 uses `version`, `banks`, `programs`, and `offers`. A bank has `name` and `logo_url`. A program has `name`, `condition`, `is_preferential`, and an optional `credit_limit`. An offer uses canonical names in `bank` and `program` and contains `interest_rate`, `minimum_initial_payment_percent`, and `maximum_loan_term_years`. Specify rate and down payment in percent and term in years or `null`.

## Bank of Russia key rate

The line chart of the full key-rate history spans the available page width. Straight segments connect consecutive points. Horizontal axis labels are spaced at least one year apart. The interval increases on narrower screens to prevent labels from overlapping. Hover over a point to enlarge it and see its date and rate. The minimum, maximum and latest entry are highlighted. The table below the chart can be sorted by date, rate or change in percentage points.

Administrators can click “Обновить из ЦБ РФ” to refresh the data. When the rate changes, the table uses the effective date. When the Bank of Russia retains the rate, the table uses the date of the published decision and shows a change of 0 percentage points. New entries appear in the chart and table after a refresh. Repeated updates do not create duplicates.

## Mortgage programs

The list updates as you type a name or description in the search field. The program type filter is to the left of search and moves above it on narrow screens. Select preferential or market programs. The “Сбросить” button sits beside the search field and restores the full list. The table has separate name and description columns, and long descriptions wrap onto multiple lines.

## Working with tables

Click a column header to sort ascending, then click again to sort descending. An arrow shows the direction; headers also work with the keyboard. Paginated lists sort the entire server selection, retain filters and reset pagination. On phones, the table scrolls horizontally inside its card and headers remain sortable. There is no separate “Сортировка” selector.

Text search applies while typing with a 250 ms delay. Some lists also offer a “Найти” button. Nested bank, limit, building, metro, tranche and schedule tables have their own “Поиск в таблице” field; sorting and search cover all loaded rows. Schedule search covers the full calculation even with the twelve-payment preview. Displayed dates and comma-separated money values are searchable. Wide nested tables scroll inside their cards on phones.

Tables at every screen size hide technical IDs, creation/update timestamps, internal activity flags and matching keys. Calculation, payment and key-rate history dates remain as business data. Linked customer calculations also show the down payment separately.

Description fields in forms beside tables use the same fonts, background, borders and focus indicator as other site controls, in both light and dark themes. Multiline fields can be resized vertically. An empty dictionary shows a no-records message; row sorting becomes available once data exists.

## Catalog and calculation filters

Dictionary filters across all table sections combine selection and search in one control. Choices load automatically; open the field and type part of a name. Scrolling loads more choices. “Все” clears only that filter. Selecting a different city, region or group resets dependent fields when the previous choice no longer fits. Arrow keys and Enter select a choice; Escape closes the list without changing the selection.

“Сбросить” is always available in the panel, including empty results: it clears filters, pagination and ordering. Customer context is preserved when choosing properties/calculations; on a customer profile, only linked calculation filters reset. The property catalog uses individual fields instead of a general “Поиск по каталогу” input. Name, description or contact search remains in lists where other fields do not replace it. Search supplied by a legacy URL appears as a notice with an “Убрать” action; the common reset clears it too.

The property catalog combines city, developer, complex, building and layout selectors with apartment number, exact area and price fields. Both histories and linked customer calculations provide city and ranges for price, down payment, payment amount, term in years and rate. The payment range uses the market mortgage's main payment or the tranche mortgage's last payment. Tranche history shows maximum and last payments separately.

Numeric filters apply while typing with a 250 ms delay and reset pagination. Boundaries are inclusive; money boundaries use the displayed kopeck precision. For example, a term from `2.08` to `2.09` years selects 25 months. Filters and sorting remain in the URL, preserving customer selection context. Legacy range URLs translate to the corresponding React parameters.

## Large form dictionaries

In property, complex, customer, developer, bank/developer program, regional limit and location forms, use “Поиск: …” above a selector. Typing searches the entire relevant dictionary within the selected parent; “Показать ещё варианты” loads additional choices. Selected values load separately and remain available outside the first page. This also covers multiple developer regions, customer layouts and preferential programs, and property window views. Changing a region, city or complex clears dependent fields; review them before saving. If loading fails, use “Повторить загрузку справочника”.

For roles and operation see `role_model.md`, `application_initial_setup.md` and `manual_deployment.md`.

## Residential complex catalog and photos

The Residential Complexes page searches while typing. Filters cover developer, city, class and property type, with a reset control. The project name opens its detail page. The main information block lists metro stations, lines and travel times. The walking icon indicates access on foot, the vehicle icon indicates transport, and the train icon indicates suburban rail.

Catalog moderators can upload several images in the “Фотографии ЖК” section, with up to 30 photos per gallery. Select “Главное фото” under an image to use it on the complex card and homepage. Uploading the same file again reuses the existing photo.

Administrators can expand “Импорт жилых комплексов из JSON” on the catalog page and select a UTF-8 JSON file of up to 16 MB. Use the [prepared selection](../data/complexes-moscow-spb-2026-11.json). Images are embedded, and each record links to its source materials.

Version 1 contains a complexes list. Each record includes a stable key, name, region, city, district, developer, class, property type, description, buildings, metro, and one to three photos. Each photo has a filename and base64 data. The zero-based primary_photo index selects the main image. Use match_name to normalize an existing project name, and match_city when correcting its city.

The import resolves a stable source key or normalized name within a city and rejects ambiguous matches. Buildings and metro rows are merged by natural keys, preserving rows omitted from the file. Correcting a city replaces metro access with entries for the new city. A failed import rolls back all database changes and removes files created by that attempt. Repeated imports update data without duplicating complexes, buildings or photos. Sources and coverage for dates and travel times are recorded in sources, notes, and metadata.

The selection's building schedules were checked on 7 November 2026. The [verification log](complex-schedule-audit-2026-11-07.md) lists previous and corrected values, evidence, and unresolved cases; structured evidence is stored in metadata.schedule_verification. A commissioning permit date represents actual commissioning; apartment handover remains a planned deadline. Quarter precision is retained as year and quarter. Unverified or conflicting periods use explicit null values: importing them clears previous dates while retaining the building and property links. A field omitted from a building record retains its previous value. Some official registry cards are accessible only through the search index; freshness limitations are recorded in the log.
