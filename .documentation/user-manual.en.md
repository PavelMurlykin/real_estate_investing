# User manual

Verified on November 1, 2026. Restored React features and page comparison results, including tables and calculation forms: [report](../.audit/REACT_DJANGO_PARITY_REPORT.md). Permanent regression tests compare the financial matrix against the Django form.

## Starting the application

Configure `.env` using `.env.example`, then run `docker compose up -d --build` from the repository root. Open the nginx address configured in `compose.yaml`. For local development use `.venv\Scripts\python.exe manage.py runserver` and Vite from `frontend` (`npm ci`, `npm run dev`). React is available at `/app/`; Django pages remain accessible when `REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED` is disabled.

After updating the Docker build, reload the browser page to load the updated interface. Its asset version updates automatically.

## Verifying the installation

Run the complete backend suite with `./scripts/run-backend-tests.ps1` from the project root while Docker is running. The script builds the application, starts separate PostgreSQL and Django services without publishing ports, and removes its temporary stack afterward. For one file, use `./scripts/run-backend-tests.ps1 -TestPath api_v1/test_catalog_case_insensitivity.py`. Startup or test failures make the script fail.

Test PostgreSQL 18 uses the `C.UTF-8` Unicode locale with the `builtin` provider. This supports case-insensitive search and duplicate checks for Russian names. When initializing a new test cluster yourself, pass `--encoding=UTF8 --locale-provider=builtin --builtin-locale=C.UTF-8` to `initdb`. Using `--no-locale` alone selects the `C` locale, which does not map Cyrillic case.

## Main sections

The catalog contains properties, developers, company groups and residential complexes. Property details show attributes, images and a link to the mortgage calculator. Catalog moderators manage property and location dictionaries. Banks, mortgage programs, developer programs and the key rate have separate sections. Imports and external updates require the appropriate permissions.

When adding or editing a city, district or metro station, type directly in the region, city or line field and choose a match from its dropdown. Changing the region clears dependent city and line fields. Changing the city in the station form clears the line. The Metro dictionary lists each station, its city and its line. The list can be filtered by region.

The customer section requires authentication. A customer profile contains contacts, preferences, budget and linked market/tranche calculations. Financial capacity is an initial estimate. Select linked calculations for a combined Word report or unlink them; deleting a customer does not delete the calculations themselves.

## Mortgage calculations

Select a property and enter its price, discount/markup, down payment, date, term and rate. Percentages and rubles synchronize using the most recently edited value. Market mortgages support a grace period; tranche mortgages support one to five tranches, with the last receiving the remaining amount. A button expands the schedule beyond the first 12 payments.

The “Объект недвижимости” field combines search and selection: start typing a city, complex, building or apartment and select a result with the mouse or arrow keys and Enter. Scrolling loads more choices. Selecting a property fills its details and price. Open calculation history with the button in the calculator header. These controls work the same way in market and tranche modes.

Bank and mortgage program fields also support searching by name. Programs become available after selecting a bank and belong to that bank. Changing the bank resets the program; “Без выбора” clears the bank, and “Ручные параметры” clears the program. Selecting a program fills its rate, down payment and term, including applicable developer conditions.

The tranche calculator starts with one residual tranche and a populated date, so a quick calculation is available after entering the financial parameters. When adding tranches, enter the dates of the new releases.

The years field uses whole years, matching the Django form. For example, entering 12.5 years sets 144 months. Use months for an exact term. Entering 25 months displays 2 in the years field while the calculation uses all 25 months. The grace period follows the same rule.

Market mortgage schedule rows are rounded to kopecks. Each payment equals interest plus principal repaid, total overpayment is the sum of interest across the rows, and the final balance is zero. The down payment date is validated together with the term so that the maturity date fits within the supported calendar.

When you open the calculator from a property link, calculation becomes available after the property loads. If loading fails, use “Повторить загрузку объекта”, select another property, or fill the fields already available below.

Property details are available immediately in the common form of both calculators. Region, city, district, developer, complex, building, layout and decoration use unified searchable fields with more choices loaded as needed. Selecting an existing apartment fills these fields, its number, area and floor; every detail remains editable. Selecting a complex fills its location and developer. Changing a region or city clears the dependent district, complex and building; changing the developer clears the complex and building. “Очистить поля” resets property details.

Quick financial calculations and exports work with empty or partial property details. To save after signing in, select an existing apartment or fill every detail except the region. Editing a selected property uses the entered details and requires recalculation before saving. Existing apartments are identified by building and apartment number; creating a new apartment requires catalog moderator permissions. Saved histories provide details, Excel/Word exports, a new calculation based on a sample and deletion with confirmation.

Property search covers the entire catalog; scrolling loads more choices. The selected property remains available while searching for alternatives. Excel and Word buttons beside the result export the current market or tranche calculation without saving or signing in, including entered properties or financial parameters alone. Exports create no catalog or history records.

Money values display two decimal places, including kopecks in payments and balances. Both calculators show the down payment percentage/date, base price and adjustment, exact term in months, rate and payment count. Market results also show the grace term/rate, separate grace/main payment counts and debt after the grace period. The tranche table includes overpayment per tranche; “Остаток к выдаче” means the amount yet to be disbursed. Saved details include the apartment layout when an image is uploaded; click it to open the full-size image.

When legacy URLs redirect to React, property/customer context is translated from `property_id`/`customer` to `propertyId`/`customerId`. Legacy filter and sorting names also translate to the new interface parameters and preserve the selected context.

## Developer programs and credit limits

The developer program list updates as you type the name of a company group, residential complex, bank or program. The same options are available in separate filters. The “Сбросить” button sits to the right of the final program filter on the same row and restores the full list.

Selecting a property and bank program applies active developer conditions: a specific complex takes priority over group-wide conditions. The adjustment, down payment, term, rate and grace period are populated; changing the program restores the base conditions. Zero rates are supported, including during the grace period. Exceeding the regional limit (or the federal fallback) shows the required/additional down payment and combined rate; apply your chosen option by editing the form fields. This is guidance, not an automatic calculation prohibition. A developer program's maximum loan amount is also considered when provided.

## Current migration limitations

Implementation and verification results are tracked in `.audit/REACT_PARITY_IMPLEMENTATION_PLAN.md`. All actions on React pages use the current interface. Links to Django forms and previous versions have been removed from lists, cards, forms and account pages. Use the corresponding current-interface buttons for editing, cancelling, signing in and password recovery. The map depends on the mapping provider.

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

If an editable dropdown fails to load its choices, press Tab from the field to reach “Повторить загрузку справочника”, then press Enter. Focus returns to the search field when the retry starts.

All React property, complex, customer, developer, bank, mortgage/developer program, regional limit and location forms combine dictionary search and selection in one field. The homepage city selector works the same way. Type a name and select a match with the mouse or arrow keys and Enter. Escape or leaving the field cancels unfinished search and retains the previous selection. Choose “Не выбрано” to clear a single value, or “Все” in filters. Search respects the selected parent. Reselecting the same parent preserves dependent values; changing the region, city, developer, complex or company group clears dependent fields.

For multiple developer regions, customer layouts and preferential programs, and property window views, add choices one by one through search without Ctrl/Cmd. Selected values appear above the field. “Убрать” removes one value; “Очистить выбор” clears all selections. Searching and adding another choice preserve the other selected values. Removal buttons are keyboard accessible.

Large dictionaries search on the server and load more results when scrolling. “Показать ещё варианты” inside the dropdown is also accessible with Tab and Enter. Saved values load separately even when absent from the first page. Use “Повторить загрузку справочника” if loading fails.

For roles and operation see `role_model.md`, `application_initial_setup.md` and `manual_deployment.md`.

## Residential complex catalog and photos

On the complex create and edit forms, each section's title and description sit above a field grid that spans the section's full width. Dictionaries and quarters use a single editable dropdown: type to filter, then choose with the mouse or arrow keys and Enter. Escape cancels the search and restores the selected value. Scrolling loads more choices for large dictionaries. Required fields have an asterisk, and errors appear below the field. Changing the region clears the city, district and metro stations; changing the city clears the district and stations. Choose the new dependent values before saving.

The Residential Complexes page searches while typing. Filters cover developer, city, class and property type, with a reset control. The project name opens its detail page. The main information block lists metro stations and travel times. A stripe before each station name uses its line's color. The line name is available by hovering over the stripe and to screen readers. The walking icon indicates access on foot, the vehicle icon indicates transport, and the train icon indicates suburban rail.

The lower metro accessibility table also shows a line-colored stripe before each station and has no separate Line column. Its search matches both station and line names.

When confirming deletion of a residential complex, focus starts on “Отмена”. Tab and Shift+Tab move between the buttons inside the dialog. Escape or “Отмена” closes the dialog and returns focus to “Удалить” on the detail page.

All photos on the complex detail page appear in one carousel in the main block. Its height is fixed at 400 pixels on wide screens and 300 on narrow screens. Images fit fully inside the frame without cropping or distorting their proportions; unused space retains the frame background. Use the previous and next photo buttons or the arrow keys while focus is inside the carousel. Clicking a photo opens the full image in an enlarged frame of constant height with the same navigation; Escape closes it.

Catalog moderators upload multiple images in the “Фотографии ЖК” section on the create or edit page. New files have previews, and “Главное фото” selects either a new or an existing image as the main photo. The main photo appears first on the detail page and on the homepage. Photos and the main selection are saved with the form using “Создать ЖК” or “Сохранить изменения”; an error leaves no partial changes. Each gallery supports up to 30 photos. Uploading the same file again reuses the existing photo.

On the edit page, each saved image has an “Удалить фото” button. It marks the photo for deletion, which can be undone before saving. Removing the main image automatically selects the next remaining photo in gallery order, including newly selected files. If all images are removed, the detail page shows a placeholder. Deletions take effect with “Сохранить изменения”; cancelling the form keeps the photos. A failed save retains all photos in the database.

Administrators can expand “Импорт жилых комплексов из JSON” on the catalog page and select a UTF-8 JSON file of up to 16 MB. Use the [prepared selection](../data/complexes-moscow-spb-2026-11.json). Images are embedded, and each record links to its source materials.

Version 1 contains a complexes list. Each record includes a stable key, name, region, city, district, developer, class, property type, description, buildings, metro, and one to three photos. Each photo has a filename and base64 data. The zero-based primary_photo index selects the main image. Use match_name to normalize an existing project name, and match_city when correcting its city.

The import resolves a stable source key or normalized name within a city and rejects ambiguous matches. Buildings and metro rows are merged by natural keys, preserving rows omitted from the file. Correcting a city replaces metro access with entries for the new city. A failed import rolls back all database changes and removes files created by that attempt. Repeated imports update data without duplicating complexes, buildings or photos. Sources and coverage for dates and travel times are recorded in sources, notes, and metadata.

The selection's building schedules were checked on 7 November 2026. The [verification log](complex-schedule-audit-2026-11-07.md) lists previous and corrected values, evidence, and unresolved cases; structured evidence is stored in metadata.schedule_verification. A commissioning permit date represents actual commissioning; apartment handover remains a planned deadline. Quarter precision is retained as year and quarter. Unverified or conflicting periods use explicit null values: importing them clears previous dates while retaining the building and property links. A field omitted from a building record retains its previous value. Some official registry cards are accessible only through the search index; freshness limitations are recorded in the log.

The [8 November follow-up](complex-schedule-followup-2026-11-08.md) clarifies the remaining four records using declarations. Placeholder rows were replaced with specific buildings: Vitebskiy Park — 3, Galaktika — 9.3. To rename a building, provide its new number and previous match_number, for example `{"number":"3","match_number":"1"}`. The import retains the building ID and its properties. Repeated imports resolve the new number; an empty catalog creates the new number directly. If the old and new numbers refer to different buildings, the mapping is ambiguous, or neither number exists in an existing complex, the import is rejected without partial updates. match_number does not create a separate alias dictionary.
