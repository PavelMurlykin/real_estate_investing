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

Metro uses separate Systems (“Системы метро”), Lines (“Линии метро”) and Stations (“Метро”) tabs. A system has a canonical center locality; a line belongs to a system and has a color. A station has a primary line, all line memberships and an optional locality. The primary line is always included; all station lines must belong to the same system. A station may be in a different locality or region from the network center. Moving a line with stations to another system is rejected. A line used by stations cannot be deleted, including additional line memberships. Station filters support system, line and locality. Migrated station territories are marked as approximate, inferred from the network. Select a confirmed station locality and clear the approximate flag to refine it. New lines require no legacy city. The complex nearest-metro search covers all Russian networks, including stations outside the complex locality. The fallback Django catalog and administrative editors follow the same rules.

In the React Developers section, “Регионы” and the “Регион” filter use Russian subjects from Location, with server search and paginated options. Pushkin and Strelna belong to Saint Petersburg; a city or settlement cannot replace a working region. Lists and sorting show canonical regions. An unmapped legacy association is marked as needing clarification and retained when other details are edited. Old regionId links remain supported; selecting a new region removes the old filter. The ERZ registry importer resolves codes and names to canonical subjects, adds missing associations and retains manual assignments. Repeating an import does not create duplicates. Ambiguous regions are reported without assigning a new association automatically. The old regionIds API remains supported; new requests use regionLocationIds. Sending both lists together is rejected.

Filtering by a legacy region ID uses the `LegacyLocationMapping` table. If an association still stores only its legacy ID and a mapping is available, the developer also appears in the Location filter. Saving through the legacy API retains regions assigned only through Location. The fallback Django list shows current subject names and the names of associations that still need clarification.

### Importing Russian locations

On Regions, Localities, Administrative districts and Metro, application administrators (`application_administrators`) and superusers see “Обновить данные” (Update data). Regular users, staff with only `is_staff`, and moderators cannot import. Moderators retain manual dictionary editing rights. The server checks permissions, the session and CSRF protection.

In React, the button sits at the right of the tab row. Use “Закрыть уведомление” (Dismiss notification) to close the result or error for the current run. Reloading clears the result. If the national import is still running, the button stays disabled until it finishes.

On any of the three geographic tabs, “Обновить данные” starts one background import of regions, administrative districts and all current cities, towns, settlements and villages from the official FNS GAR. The free metadata API `https://fias.nalog.ru/WebServices/Public/GetLastDownloadFileInfo` requires no key or registration. One source version is pinned per run. HTTPS ZIP ranges retrieve address objects and administrative hierarchy. Section 99 (Baikonur outside Russia) is excluded. Filters do not restrict the run. The initial download can take tens of minutes. The button is disabled while the job runs and the summary appears after completion.

Closing the tab or reloading does not interrupt the import. Repeated clicks reuse an active job. After failure, “Обновить данные” resumes after the last completely committed region of the same version. A checksum failure or incomplete hierarchy rejects the entire current region. A restarted worker resumes unfinished jobs. After completion the button starts a fresh update. Repeating the same version uses verified cached extracts and creates no duplicates. Retired objects are retained as inactive and manual deactivation is preserved. Historic regional sections without current objects do not create empty subjects.

The full locality catalog is at `/app/locations/localities`: search matches names and aliases, with region, administrative district, type and activity filters. Homonyms remain distinct by type, parent territory, region and FIAS identifier. Pushkin is imported as a city in Pushkinsky District and Strelna as a settlement in Petrodvortsovy District of Saint Petersburg.

The complex card’s “Территории ЖК” section lets moderators and administrators choose a precise locality, attach multiple territories and select exactly one primary territory. Buildings inherit the primary territory unless another of their complex's territories is selected. Removing a referenced binding requires reassignment first. Changing the primary territory retains the former one as “Историческая привязка”; that link alone no longer includes the complex in search results. A moderator can clear this flag if the complex actually spans multiple territories. The primary territory cannot be historical. An explicit building override remains effective even when its complex territory becomes historical.

The homepage, complex and property lists, and customer property selection provide “Регион”, “Административный район” and “Населённый пункт” filters from the complete catalog. They include descendants: Saint Petersburg includes Pushkin and Strelna, Petrodvortsovy district includes Strelna, and Pushkinsky district includes Pushkin. A locality can be selected without choosing a region first. Changing the region clears district and locality; changing the district clears locality. Both also clear selected complex and building filters. All supplied filters must match the same territory. Homonymous localities keep distinct IDs. Property filtering uses the building's explicit territory, otherwise the complex primary. Complex filtering also includes current secondary territories and explicit building territories. URLs retain filters; old city links are converted through the compatibility mapping. With no filters, the homepage lists complexes across Russia.

This transition retains a compatibility layer: legacy subject, city, district, complex, building, property and metro IDs stay unchanged. Mortgage regional limits retain their original subject references. Developer working regions use Location while keeping legacy associations for API compatibility. The initial migration attaches complexes to their previous administrative districts and never guesses a locality. Refine it explicitly in the card. The React complex create/edit forms use Location and the complete GAR catalog for “Регион”, “Административный район” and “Населённый пункт”, including cities, settlements and villages such as Pushkin and Strelna. Region and district are optional when starting a search. Selecting a locality fills them from its administrative ancestry; changing the region clears district and locality, while changing the district clears locality. After changing the territory, choose a locality before saving. Buildings, apartments and metro availability rows are retained. Metro can be searched outside the complex locality. The server rejects inconsistent territories without saving. The legacy district is optional: creating a complex does not fabricate legacy city or district entries. Existing complexes whose localities are not yet known can retain their former administrative district while other fields are edited. Selecting a precise locality changes the primary territory and preserves other territories, building overrides, apartments, photographs and metro links. Legacy catalogs remain for compatibility; metro uses canonical locations and systems. The separate municipal hierarchy model is prepared; metro systems and multiple station lines are used by the catalogs; the national GAR import updates geography, while metro has a separate import.

Compose stores the GAR cache in the shared `location_import_cache` volume. Locally, `GAR_CACHE_DIRECTORY` overrides the default `outputs/gar-cache`. Open-data terms: [FNS](https://www.nalog.gov.ru/opendata/7707329152-fias/). Keep the PostgreSQL volume and back up the database before migration. Migrations add tables and bindings without deleting legacy fields.

Search updates results while typing; a separate “Найти” button is unnecessary. On phones, filters use one column.

Use the national GAR import to refresh canonical regions, localities and administrative districts. Selected-parent imports remain in the old API for compatibility and do not replace loading the new catalog.

The background GAR import updates Location by FIAS and GAR identifiers and federal subject codes. The worker continues independently of the open page. JSON version 1 and developer registry imports use canonical locations together with retained codes and names. Legacy links, request formats and existing associations are preserved.

The legacy dictionary and selector endpoints retain their URLs, IDs, status, parent filters and response formats. They read the historical geography through `LegacyLocationMapping`. Existing integrations can still edit the legacy entries with their current catalog permissions. The old rows are synchronized while other sections still reference them. Historical aliases retain their scope, while precise settlements such as Pushkin, Strelna and Likino are available in the Location catalog.

On Metro, select a system and click “Обновить данные”. The network center must have a confirmed FIAS identifier. Lines and stations are loaded together. Existing entries retain their IDs, precise geography, line memberships, active states and complex links. The lines list shows a color swatch beside each name. To pick a color, use “Цвет линии” in the editor. A station card shows the station's locality.

The `systemId` filter selects the network. The station locality filter uses the station's own location. Legacy `cityId` and `regionId` filters use the original line association. With `canonicalLocations=true`, they apply to the network center through `LegacyLocationMapping`. A legacy import request with a region and city updates the same network as a request with `systemId`. Select a system explicitly when a city matches multiple networks.

Free sources for legacy selected-parent dictionaries and metro, without API keys or registration: [HFLabs/city](https://github.com/hflabs/city) (CSV over HTTPS, Russian regions and cities, CC BY-SA 4.0), [Wikidata API](https://www.wikidata.org/wiki/Wikidata:Data_access) (urban districts, lines and operating regional metro stations, CC0), and [Wikipedia API](https://ru.wikipedia.org/w/api.php) (open JSON metro schemes for the two capitals and station catalogs for the other cities, CC BY-SA). Overpass is no longer used. Attribution to [OpenStreetMap, ODbL](https://www.openstreetmap.org/copyright) is retained for older records.

Coverage of legacy selected-parent imports follows these open sources; the complete locality catalog uses official GAR. Metro is supported for Moscow, Saint Petersburg, Kazan, Yekaterinburg, Nizhny Novgorod, Novosibirsk and Samara. Future stations and municipal units that are not urban districts are excluded. Unsupported networks reject metro import without saving data; missing districts in Wikidata also produce an empty result. Cities are checked by country, name, type and coordinates. Ambiguous matches reject the import.

Repeating an import adds new entries and refreshes names, relationships and line colors by stable identifiers: KLADR for regions, FIAS for cities, Wikidata for districts and Wikipedia page IDs for stations. Matching manual and legacy OSM entries are linked to the new source while preserving primary keys and dependencies. Existing region codes and manually chosen active status are retained; new regions receive a two-digit KLADR code. Entries missing from the source are not deleted. Ambiguous matches fail without partial writes. Results report created, updated, unchanged and skipped entries; metro results also report lines separately.

Imports are serialized across all application users. An unavailable API, partial response or conflict saves no changes from the current import; resolve conflicts or retry later. The button is disabled while a request runs. Containerized Gunicorn allows up to 60 seconds per request; extraction is limited to 45 seconds and each network operation to 8 seconds. A transient network failure is retried once after a pause. After updating, run `docker compose up -d --build --wait`: the migration changes the source field label without deleting data.

The fallback Django Regions, Localities and Administrative districts pages offer the same national background import with the same permissions. Reload to update its progress. To refresh metro, open its tab and select a system.

`docker compose up -d --build --wait` also starts `location-import-worker`, using the same PostgreSQL database. No separate Redis/Celery service is needed. It processes queued jobs and recovers after restart. When running without Compose, start the worker with `.venv\Scripts\python.exe manage.py process_location_imports`; `--once` processes one available job and exits. Verify the new interface with `./scripts/run-react-browser-acceptance.ps1 -TestPath browser-tests/national-location-import.test.mjs`.

To verify in a separate PostgreSQL database and browser, run `./scripts/run-react-browser-acceptance.ps1 -TestPath browser-tests/location-import.test.mjs -LiveLocationImport`. `-LiveLocationImport` enables external API calls; without it, permissions and import controls are tested. The stack uses port `18081` and does not connect to working data.

The live scenario checks Saint Petersburg by default. To check Moscow, set `$env:BROWSER_TEST_LOCATION_CITY = 'Москва'` before running it. An external API failure fails this scenario and is not treated as a successful check.

For a regional city also set its region: for example, `$env:BROWSER_TEST_LOCATION_CITY = 'Казань'` and `$env:BROWSER_TEST_LOCATION_REGION = 'Республика Татарстан'`.

The worker with `--once` returns a nonzero exit code if its job fails due to a source or data error. Progress remains saved; the normal background worker continues serving the queue.

### Creating and editing apartments

Apartment forms use the complete Russian catalog for “Регион”, “Административный район” and “Населённый пункт”, including Pushkin, Strelna and villages. A locality can be searched without first choosing a region. These fields filter complexes and buildings; apartments do not store a separate territory. Changing the region clears district, locality, complex and building; changing the district clears locality, complex and building; changing the locality clears complex and building. The developer and other apartment details are retained.

Selecting a building fills its effective location: an explicit building territory, otherwise the complex primary. Selecting a complex alone does not automatically restrict buildings to its primary territory. If an old building's locality is still unknown, other apartment details can be saved while retaining the current building. Refine its territory in the complex card. Editing retains existing links, images, window views and other values unless explicitly changed. Mortgage limit region IDs remain unchanged.

The fallback Django form uses the same territories and server-side checks that the building belongs to the selected complex, developer and territory. Large catalogs support remote search; initial choices are bounded to 50 records plus the current selection. The complete GAR is not embedded in HTML.

### Customers and forms

Residence is selected in “Населённый пункт проживания” from the complete Russian catalog, including Pushkin, Strelna and villages. Purchase preferences use “Регион покупки”, “Административный район покупки” and “Населённый пункт покупки”. Select a region or district alone, or search for a locality directly. The region is inferred from the selected territory if omitted. Choice and profile labels include type, parent and region to distinguish homonyms. Changing the region clears district and locality; changing the district clears locality. “Рассчитать ипотеку” opens property selection with the saved territory and customer context.

Migration preserves original cities, districts, owners, calculations, associations and each customer's financial region, including an empty region. Changing the purchase territory sets the financial region to its federal subject in Location. The profile displays it under “Регион лимита”. Existing associations without an unambiguous Location limit retain the amount keyed by the exact legacy region ID. Saving unrelated profile fields preserves the financial association.

The profile displays confirmed names from the unified catalog and retained names where a mapping is still needed. Editing other fields keeps the former locations and limits. Select territories in the form to refine them. Clearing a canonical field persists an empty selection. Profiles and linked calculations remain available only to their owner and appropriately authorized users.

The customer section requires authentication. A customer profile contains contacts, preferences, budget and linked market/tranche calculations. Financial capacity is an initial estimate. Select linked calculations for a combined Word report or unlink them; deleting a customer does not delete the calculations themselves.

Forms use consistent single-line field and primary button dimensions, typography and spacing. Section headings sit above their fields; hints and errors appear beside the relevant field. On narrow screens, fields and actions stack in one column. Tab and Shift+Tab move focus between available controls; the active control has a contrasting outline in both light and dark themes.

### Territory dictionaries

The Regions (“Регионы”), Localities (“Населённые пункты”) and Administrative districts (“Административные районы”) pages use the unified location dictionary. The former Cities link also opens localities, including Russian cities, towns, villages and rural settlements. Pushkin belongs to Pushkinsky District and Strelna to Petrodvortsovy District of Saint Petersburg. Municipal entities remain separate from administrative districts.

Odintsovo, Pushkino, Klin and other verified cities in Moscow Oblast, as well as Nizhny Novgorod, are available under Localities. They may report directly to the federal subject in the hierarchy. For districts absent from the loaded GAR administrative hierarchy, verification uses city records and the parent's FIAS ID. The Mys complex is in Likino village. Its former association with Odintsovsky Urban District is kept in its history. Find the complex with the Likino filter or under Odintsovo, the village's parent city in GAR.

Location catalog editors appear beside the list on wide screens and above it on phones. The pencil and delete icons in each row open the editor and the deletion confirmation.

The Locations tabs display active entries. Search matches current and former names. Filters update the list automatically. Click a column header to sort entries and click it again to reverse the direction. For a locality or district, enter its name, type and parent territory. Parent choices are searched on the server. The parent region narrows the list. Names may repeat in different territories. Each name must be unique within its type and parent territory.

Renaming preserves the former name for search, source identifiers and every association. Moving a territory changes its administrative affiliation together with its descendants; cycles are rejected. Official imports may update the name and hierarchy again while retaining IDs and links. Manual deactivation survives repeated imports. Imported or referenced records cannot be deleted: clear “Активно” to hide them. Unused manual records can be deleted.

Reading is public, editing requires a moderator or administrator, and national imports require an application administrator or superuser. The fallback Django page follows the same rules. Old edit links resolve through explicit mappings. Legacy dictionaries and financial region associations remain intact: creating a new territory does not automatically create regional mortgage limits or developer operating regions.

## Navigation

The top panel, sidebar and section links share consistent sizing, spacing and current-page indicators. The current section is underlined and has a highlighted background; detail and edit pages highlight their parent section. On phones, primary links occupy a second header row and retain readable text.

Tab and Shift+Tab move through links. In the top panel and section links, Left/Right arrows, Home and End move focus; Enter opens the focused section. Long section rows scroll horizontally. The current link remains visible when opening a page, going Back/Forward or resizing the window.

On narrow screens, “Открыть меню разделов” opens the sidebar. Its current item is visible within the scrollable area. Tab stays inside the menu; Escape and the close button return focus to the opener. Ordinary navigation closes the menu and focuses page content. Ctrl/Cmd+click opens a link separately and retains the menu. Customer and calculation-history links require the corresponding permissions.

## Mortgage calculations

In the fallback Django calculator (`/mortgage/?legacy=1`), both modes use “Регион”, “Административный район” and “Населённый пункт” from the shared `Location` directory. Select a territory, developer, complex and building; localities can be searched by name, including Pushkin and Strelna. Selecting a building fills all three fields from its effective territory. Changing territory clears dependent complexes, buildings and apartments. Apartment numbers are searched on the server within the selected building; “Показать ещё квартиры” loads more options. You can enter a new apartment manually; saving still requires catalog permissions. The old district is optional. Regional mortgage limits resolve through an explicit region mapping instead of matching numeric IDs. Opening an apartment or a sample calculation retains its geography, price and relationships; opening a form does not overwrite saved calculations, customer associations or limits.

Select a property and enter its price, discount/markup, down payment, date, term and rate. Percentages and rubles synchronize using the most recently edited value. Market mortgages support a grace period; tranche mortgages support one to five tranches, with the last receiving the remaining amount. A button expands the schedule beyond the first 12 payments.

The “Объект недвижимости” field combines search and selection: start typing a city, complex, building or apartment and select a result with the mouse or arrow keys and Enter. Scrolling loads more choices. Selecting a property fills its details and price. Open calculation history with the button in the calculator header. These controls work the same way in market and tranche modes.

Saved mortgage and tranche histories, their detail pages and the customer's calculation table display the apartment's locality, administrative district and region. A building's explicit territory takes priority over the complex's primary location. For example, Pushkin appears in Pushkinsky District and Strelna in Petrodvortsovy District of Saint Petersburg. Search matches location names and aliases, complex names, buildings and apartment numbers. The “Регион”, “Административный район” and “Населённый пункт” filters search options on the server, intersect their scopes and update results automatically. Changing the region clears the dependent district and locality; changing the district clears the locality. Old city-filter links remain supported through explicit mappings. Amounts, rates, schedules, tranches, customer associations and regional mortgage limits are preserved. The fallback Django pages follow the same rules.

Next to calculation history, “Настройки” opens the modifier settings dialog. The large amount increment defaults to 100,000 ₽ and applies to the property price, down payment and tranche amounts. A separate small amount increment defaults to 10,000 ₽ and applies to discounts and markups in rubles. All percentage fields share an increment of 1, 0.1 or 0.01 percentage points (default: 0.1). Enter positive whole amount increments up to 1,000,000,000 ₽ and click “Сохранить”. Settings are shared by both modes and saved in this browser; existing large amount and percentage settings survive the update, while the new small amount increment defaults to 10,000 ₽. “Отмена” or Escape closes the dialog without changes. If browser storage is unavailable, a notice explains that the settings apply until the page reloads.

Numeric fields always show −/+ buttons on the right. A press changes the value by one configured increment; holding with a mouse, touch, Enter or Space repeats the change after a short delay. Repeating stops on release, leaving the button, cancelling a touch or losing focus. The ↑/↓ keys in the input use the same increment. Term and floor fields change by 1, area by 0.01 m². The minimum area is 0.01 m² and the minimum floor is 0; buttons, keys and manual entry prevent negative values. Residual tranche amounts remain read-only. In the loan conditions section, the down payment date and annual rate appear side by side on wider screens and stack on narrow screens.

Bank and mortgage program fields also support searching by name. Programs become available after selecting a bank and belong to that bank. Changing the bank resets the program; “Без выбора” clears the bank, and “Ручные параметры” clears the program. Selecting a program fills its rate, down payment and term, including applicable developer conditions.

The tranche calculator starts with one residual tranche and a populated date, so a quick calculation is available after entering the financial parameters. When adding tranches, enter the dates of the new releases.

The years field uses whole years, matching the Django form. For example, entering 12.5 years sets 144 months. Use months for an exact term. Entering 25 months displays 2 in the years field while the calculation uses all 25 months. The grace period follows the same rule.

Market mortgage schedule rows are rounded to kopecks. Each payment equals interest plus principal repaid, total overpayment is the sum of interest across the rows, and the final balance is zero. The down payment date is validated together with the term so that the maturity date fits within the supported calendar.

When you open the calculator from a property link, calculation becomes available after the property loads. If loading fails, use “Повторить загрузку объекта”, select another property, or fill the fields already available below.

Property details are available immediately in the common form of both calculators. Region, locality and administrative district come from the complete catalog and narrow the search for existing apartments, complexes and buildings. Developer, complex, building, layout and decoration also use unified searchable fields with more choices loaded as needed. Selecting an existing apartment fills these fields, its number, area and floor; every detail remains editable. Selecting a complex fills its location and developer; selecting a building respects its explicit territory. Changing a region or locality clears the dependent district, complex and building; changing the developer clears the complex and building. The legacy district is optional for complexes with a canonical territory. Both React calculators resolve mortgage limits using the property's federal subject in Location. Apartments in Pushkin and Strelna use the Saint Petersburg limit. “Очистить поля” resets property details.

Quick financial calculations and exports work with empty or partial property details. To save after signing in, select an existing apartment or fill the property details; complexes without a legacy district do not require legacy city or district choices. Editing a selected property uses the entered details and requires recalculation before saving. Existing apartments are identified by building and apartment number; creating a new apartment requires catalog moderator permissions. Saved histories provide details, Excel/Word exports, a new calculation based on a sample and deletion with confirmation.

Property search covers the entire catalog; scrolling loads more choices. The selected property remains available while searching for alternatives. Excel and Word buttons beside the result export the current market or tranche calculation without saving or signing in, including entered properties or financial parameters alone. Exports create no catalog or history records.

Money values display two decimal places, including kopecks in payments and balances. Both calculators show the down payment percentage/date, base price and adjustment, exact term in months, rate and payment count. Market results also show the grace term/rate, separate grace/main payment counts and debt after the grace period. The tranche table includes overpayment per tranche; “Остаток к выдаче” means the amount yet to be disbursed. Saved details include the apartment layout when an image is uploaded; click it to open the full-size image.

When legacy URLs redirect to React, property/customer context is translated from `property_id`/`customer` to `propertyId`/`customerId`. Legacy filter and sorting names also translate to the new interface parameters and preserve the selected context.

## Developer programs and credit limits

The developer program list updates as you type the name of a company group, residential complex, bank or program. The same options are available in separate filters. The “Сбросить” button sits to the right of the final program filter on the same row and restores the full list.

Selecting a property and bank program applies active developer conditions: a specific complex takes priority over group-wide conditions. The adjustment, down payment, term, rate and grace period are populated; changing the program restores the base conditions. Zero rates are supported, including during the grace period. Exceeding the regional limit (or the federal fallback) shows the required/additional down payment and combined rate; apply your chosen option by editing the form fields. This is guidance, not an automatic calculation prohibition. A developer program's maximum loan amount is also considered when provided.

React and the fallback Django calculator use the federal subject of the property's effective territory in Location. Pushkin and Strelna use Saint Petersburg, and Likino uses Moscow Oblast. A limit can be set for a subject that only has a Location ID. When legacy records are ambiguous and the subject has no active Location limit, selecting the subject uses the program's general limit. The legacy API still accepts and returns legacy region IDs.

## Current migration limitations

Implementation and verification results are tracked in `.audit/REACT_PARITY_IMPLEMENTATION_PLAN.md`. All actions on React pages use the current interface. Links to Django forms and previous versions have been removed from lists, cards, forms and account pages. Use the corresponding current-interface buttons for editing, cancelling, signing in and password recovery. The map depends on the mapping provider.

## Homepage and complex map

In “Жилые комплексы по территориям”, select a region, administrative district or locality. With no filters, active complexes across Russia are listed. Cards show the complex's territory, photo, developer, class, type and description. Links open complex details, its properties, and the map or presentation when available. The “Населённые пункты” statistic in “Портфель платформы” counts active localities in Location, including villages.

“Списком” and “На карте” switch views. The territory and view stay in the URL, and old city links still open. The first 50 complexes load immediately. Use “Показать ещё ЖК” to load more. The map shows loaded complexes. Coordinates come from the map link or are resolved by complex name and territory. When the map provider is unavailable or coordinates cannot be found, cards and direct links remain available. Use “Повторить загрузку карты” to retry.

## Bank list

The bank list updates as you type a name in the search field. The “Программы” filter lets you select banks with or without mortgage programs. The “Сбросить” button sits to the right of that filter on the same row and restores the full list. On narrow screens, the table scrolls within its card and long bank names wrap onto multiple lines.

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

In the program editor, enter the federal limit and select “Добавить регион” to set a regional override. Search for the federal subject in Location, enter the amount and keep the override active for calculators to apply it. If a legacy region still has no unambiguous mapping, the editor shows the existing association. You can retain it or select a federal subject to resolve it. Existing API requests using `regionId` continue to work for regions with a legacy ID.

## Loading, errors and empty data

Pages and nested sections share consistent loading, error and empty states. An indicator appears while data loads; reduced-motion preferences disable its rotation. Navigation remains available. A failed session check offers a retry and is not presented as a sign-out.

The keyboard-accessible “Повторить” button reloads the section and its failed dependencies. It is disabled during the request. Another failure returns focus to the button; successful recovery focuses the restored section heading or the form’s initial field. If you have moved to another control, focus stays there. Loading dependent dictionaries restores focus to the previous field. Reloading a list retains its address and filters.

Empty results are distinct from failures and suggest the next action. In a nested table, “Сбросить поиск” clears an unsuccessful search while retaining sorting. If a map fails or has no coordinates, “Повторить загрузку карты” offers recovery; the complex list and direct links remain available.

If validating a password-reset link temporarily fails, use “Повторить”. This does not mean the link has expired. Successful validation opens the new-password form without the token in its address. A genuinely invalid link offers “Запросить новую ссылку”.

## Dialogs and notices

Deletion and calculation unlink dialogs use consistent headings, spacing and buttons. “Отмена” receives initial focus. Tab and Shift+Tab move within the dialog; Escape, “Отмена” or a click on the shaded backdrop closes it. Dragging from the content onto the backdrop leaves it open. While a request is pending, dismissal and repeated confirmation are blocked. Closing returns focus to the trigger; after deletion, focus moves to the list heading. Image previews and the mobile menu follow the same dismissal and keyboard rules; arrow keys also change photos.

Errors, guidance and operation results share a consistent appearance. Errors are announced immediately; other messages announce without interrupting work. Appearing notices do not take focus. Success messages for profile saving, password changes and key-rate updates provide a “Закрыть уведомление” button that returns focus to the corresponding operation button. Field validation errors appear beside their fields and cannot be dismissed separately. Notices do not expire automatically. On phones, text wraps and confirmation buttons stack vertically.

## Detail pages

Property, residential complex, customer, bank, mortgage program, developer program and saved calculation detail pages share the same layout: a page title, an action bar below it and consistently spaced sections. On phones, buttons span the available width, facts use one column and long names wrap. Nested tables scroll within their section.

Use Tab and Enter to operate buttons. Deletion dialogs initially focus “Отмена”; Tab and Shift+Tab move within the dialog. Escape or “Отмена” closes it and returns focus to “Удалить”. While a request is pending, dismissal and repeated confirmation are blocked. Enlarged images also close with Escape and return focus to the original image.

## Working with tables

Tables use consistent headers, rows, action buttons, filters and pagination. Dictionary, status and type filters combine search and selection in one field: typing narrows the choices, Enter applies the selected choice and Escape cancels the search. Changing a filter or sorting returns its list to the first page while retaining other filters and customer context.

Wide tables scroll within their own area. Reach the area with Tab and use the arrow keys to scroll; sorting headers and “Назад”/“Далее” buttons are also keyboard accessible. The active header shows the sorting direction and pagination announces the current page. On narrow screens, the page counter sits above the buttons; lists retain cards where a mobile representation is provided.

Click a column header to sort ascending, then click again to sort descending. An arrow shows the direction; headers also work with the keyboard. Paginated lists sort the entire server selection, retain filters and reset pagination. On phones, the table scrolls horizontally inside its card and headers remain sortable. There is no separate “Сортировка” selector.

Text search applies while typing with a 250 ms delay. Some lists also offer a “Найти” button. Nested bank, limit, building, metro, tranche and schedule tables have their own “Поиск в таблице” field; sorting and search cover all loaded rows. Schedule search covers the full calculation even with the twelve-payment preview. Displayed dates and comma-separated money values are searchable. Wide nested tables scroll inside their cards on phones.

Tables at every screen size hide technical IDs, creation/update timestamps, internal activity flags and matching keys. Calculation, payment and key-rate history dates remain as business data. Linked customer calculations also show the down payment separately.

Description fields in forms beside tables use the same fonts, background, borders and focus indicator as other site controls, in both light and dark themes. Multiline fields can be resized vertically. An empty dictionary shows a no-records message; row sorting becomes available once data exists.

## Catalog and calculation filters

Residential complex and apartment catalogs display the canonical locality with its administrative district and region. The “Населённый пункт” column sorts by the displayed locality before pagination; it includes towns, settlements and villages. Region, administrative district and locality filters intersect. A complex can match any current territory it covers or an explicit building territory; its displayed and sorted locality comes from its primary territory. An apartment uses its building's explicit territory, otherwise the complex's primary territory. Unused historical complex territories do not produce matches.

The same rules apply to the fallback Django lists. Search matches location names and aliases, complex and developer names, building numbers and apartment numbers as appropriate. Project and building choices load on the server within the selected territory. Changing a geographic parent clears dependent choices and the previous city filter. Existing city links and API identifiers resolve through the mapping table. A complex with a district-level territory shows current location names and retains its original API identifiers. If a complex has no territory records yet, it uses its former district's mapping. Updating the district through the legacy API updates a district-level territory and keeps its history. For a complex with a confirmed locality, the same request updates only the legacy district identifier.

Dictionary filters across all table sections combine selection and search in one control. Choices load automatically; open the field and type part of a name. Scrolling loads more choices. “Все” clears only that filter. Selecting a different city, region or group resets dependent fields when the previous choice no longer fits. Arrow keys and Enter select a choice; Escape closes the list without changing the selection.

“Сбросить” is always available in the panel, including empty results: it clears filters, pagination and ordering. Customer context is preserved when choosing properties/calculations; on a customer profile, only linked calculation filters reset. The property catalog uses individual fields instead of a general “Поиск по каталогу” input. Name, description or contact search remains in lists where other fields do not replace it. Search supplied by a legacy URL appears as a notice with an “Убрать” action; the common reset clears it too.

The property catalog combines city, developer, complex, building and layout selectors with apartment number, exact area and price fields. Both histories and linked customer calculations provide city and ranges for price, down payment, payment amount, term in years and rate. The payment range uses the market mortgage's main payment or the tranche mortgage's last payment. Tranche history shows maximum and last payments separately.

Numeric filters apply while typing with a 250 ms delay and reset pagination. Boundaries are inclusive; money boundaries use the displayed kopeck precision. For example, a term from `2.08` to `2.09` years selects 25 months. Filters and sorting remain in the URL, preserving customer selection context. Legacy range URLs translate to the corresponding React parameters.

## Large form dictionaries

If an editable dropdown fails to load its choices, press Tab from the field to reach “Повторить загрузку справочника”, then press Enter. Focus returns to the search field when the retry starts.

During loading or after an error, pressing Enter alone retains the previous selection, including multiple values. The error appears beside the field and is announced to screen readers. An active retry cannot be restarted. To clear explicitly, use an arrow key to reach “Все”, “Не выбрано” or “Очистить выбор” and press Enter; this remains available after a failed request.

When moving with Tab and Shift+Tab, the field remains visible below the top panel. Dropdowns use a reduced height on short screens; their choices and actions scroll internally, including through touch.

All React property, complex, customer, developer, bank, mortgage/developer program, regional limit and location forms combine dictionary search and selection in one field. The homepage uses the same region, district and locality pickers. Type a name and select a match with the mouse or arrow keys and Enter. Escape or leaving the field cancels unfinished search and retains the previous selection. Choose “Не выбрано” to clear a single value, or “Все” in filters. Search respects the selected parent. Reselecting the same parent preserves dependent values; changing the region, locality, developer, complex or company group clears dependent fields.

For multiple developer regions, customer layouts and preferential programs, and property window views, add choices one by one through search without Ctrl/Cmd. Selected values appear above the field. “Убрать” removes one value; “Очистить выбор” clears all selections. Searching and adding another choice preserve the other selected values. Removal buttons are keyboard accessible.

Large dictionaries search on the server and load more results when scrolling. “Показать ещё варианты” inside the dropdown is also accessible with Tab and Enter. Saved values load separately even when absent from the first page. Use “Повторить загрузку справочника” if loading fails.

For roles and operation see `role_model.md`, `application_initial_setup.md` and `manual_deployment.md`.

## Residential complex catalog and photos

On the complex create and edit forms, each section's title and description sit above a field grid that spans the section's full width. Dictionaries and quarters use a single editable dropdown: type to filter, then choose with the mouse or arrow keys and Enter. Escape cancels the search and restores the selected value. Scrolling loads more choices for large dictionaries. Required fields have an asterisk, and errors appear below the field. The region filter clears the locality selection so another locality can be chosen. Metro stations are never removed automatically. The locality, complex fields, buildings and photos save in one transaction. Cards and exports resolve geographic labels from the precise territory while mortgage limits retain their original region IDs.

The Residential Complexes page searches while typing. Filters cover developer, city, class and property type, with a reset control. The project name opens its detail page. The main information block lists metro stations and travel times. A stripe before each station name uses its line's color. The line name is available by hovering over the stripe and to screen readers. The walking icon indicates access on foot, the vehicle icon indicates transport, and the train icon indicates suburban rail.

The lower metro accessibility table also shows a line-colored stripe before each station and has no separate Line column. Its search matches both station and line names.

When confirming deletion of a residential complex, focus starts on “Отмена”. Tab and Shift+Tab move between the buttons inside the dialog. Escape or “Отмена” closes the dialog and returns focus to “Удалить” on the detail page.

All photos on the complex detail page appear in one carousel in the main block. Its height is fixed at 400 pixels on wide screens and 300 on narrow screens. Images fit fully inside the frame without cropping or distorting their proportions; unused space retains the frame background. Use the previous and next photo buttons or the arrow keys while focus is inside the carousel. Clicking a photo opens the full image in an enlarged frame of constant height with the same navigation; Escape closes it.

Catalog moderators upload multiple images in the “Фотографии ЖК” section on the create or edit page. New files have previews, and “Главное фото” selects either a new or an existing image as the main photo. The main photo appears first on the detail page and on the homepage. Photos and the main selection are saved with the form using “Создать ЖК” or “Сохранить изменения”; an error leaves no partial changes. Each gallery supports up to 30 photos. Uploading the same file again reuses the existing photo.

On the edit page, each saved image has an “Удалить фото” button. It marks the photo for deletion, which can be undone before saving. Removing the main image automatically selects the next remaining photo in gallery order, including newly selected files. If all images are removed, the detail page shows a placeholder. Deletions take effect with “Сохранить изменения”; cancelling the form keeps the photos. A failed save retains all photos in the database.

Administrators can expand “Импорт жилых комплексов из JSON” on the catalog page and select a UTF-8 JSON file of up to 16 MB. Use the [prepared selection](../data/complexes-moscow-spb-2026-11.json). Images are embedded, and each record links to its source materials.

The import supports versions 1 and 2. Load GAR geography and the required metro systems first. Complex import creates no legacy region, city or district records. Version 1 retains its existing fields: region, region_code, city and district resolve against canonical geography. Unknown or ambiguous territories reject the entire file. A legacy city/district pair retains that coarse precision; a compatible old file does not replace confirmed Pushkin or Strelna with the general Petersburg territory.

Version 2 replaces the old geographic fields with location containing exactly one of `{"fias_id":"FIAS GUID"}` or `{"id":123}`. The reference must identify a locality or a federal city's locality role. GUIDs are portable; IDs belong to the current database. Pushkin's FIAS GUID is `110d6ad9-0b64-47cf-a2ee-7e935228799c`; Strelna's is `3eece910-1326-4602-aa21-e4ee117275ad`.

```json
{
  "version": 2,
  "complexes": [{
    "key": "example:pushkin",
    "name": "Пример ЖК",
    "location": {"fias_id": "110d6ad9-0b64-47cf-a2ee-7e935228799c"},
    "developer": "Название застройщика",
    "real_estate_class": "Комфорт",
    "real_estate_type": "Квартира",
    "description": "Описание ЖК",
    "buildings": [{"number": "1"}],
    "metro": [],
    "photos": [],
    "sources": ["https://example.com/project"]
  }]
}
```

Replace the example project values; its class must already exist in the catalog. The buildings list contains 1–100 records. Version 2 metro entries use station_id, station_source_identifier, or station and line with system_id or system_location. The latter uses the same id/fias_id reference format for the network center. Creating a line requires color in #RRGGBB format. Each access row requires mode (“Пешком”, “На транспорте”, or “На электричке”) and minutes from 1 to 1440. A station may be outside the complex locality; its own geography and all line memberships are retained. Version 1 station/line names remain supported; an ambiguous network requires an explicit version 2 reference.

Version 2 metro and photos may be omitted or empty: existing access rows and gallery images remain. An image has name and base64 data; one import accepts at most 3 images. The zero-based primary_photo index is supplied only with new photos. Version 1 retains its requirement for at least one station and photo. Source links and notes remain in sources, notes and metadata.

Matching uses the stable key or a normalized name within a specific territory. Use match_name for a rename. To move an existing complex without a source key, version 2 accepts match_location with its previous id/fias_id; version 1 retains match_city. Existing complex, building, apartment, photo and metro-access IDs remain unchanged. The previous district field is not overwritten. Explicit building territories and previous complex territories remain linked; moving a complex does not automatically move apartments whose buildings have their own territory. Financial calculations, customer links and regional limits are unchanged.

Buildings and metro access are merged with existing records; omitted entries remain. Repeating an import creates no duplicate complexes, buildings, stations or images. Any error rolls back the entire file and removes only files created by the failed attempt. The button becomes available again after success or failure; list refresh does not block another import. Application administrators and superusers retain import access, protected by session authentication and CSRF.

The selection's building schedules were checked on 7 November 2026. The [verification log](complex-schedule-audit-2026-11-07.md) lists previous and corrected values, evidence, and unresolved cases; structured evidence is stored in metadata.schedule_verification. A commissioning permit date represents actual commissioning; apartment handover remains a planned deadline. Quarter precision is retained as year and quarter. Unverified or conflicting periods use explicit null values: importing them clears previous dates while retaining the building and property links. A field omitted from a building record retains its previous value. Some official registry cards are accessible only through the search index; freshness limitations are recorded in the log.

The [8 November follow-up](complex-schedule-followup-2026-11-08.md) clarifies the remaining four records using declarations. Placeholder rows were replaced with specific buildings: Vitebskiy Park — 3, Galaktika — 9.3. To rename a building, provide its new number and previous match_number, for example `{"number":"3","match_number":"1"}`. The import retains the building ID and its properties. Repeated imports resolve the new number; an empty catalog creates the new number directly. If the old and new numbers refer to different buildings, the mapping is ambiguous, or neither number exists in an existing complex, the import is rejected without partial updates. match_number does not create a separate alias dictionary.

Further location migration work targets React. Fallback Django forms are no longer being developed; their removal is planned after migration completion and manual verification of the React forms. The old complex API and JSON import format remain supported.
