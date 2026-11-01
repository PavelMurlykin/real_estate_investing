# User manual

## Starting the application

Configure `.env` using `.env.example`, then run `docker compose up -d --build` from the repository root. Open the nginx address configured in `compose.yaml`. For local development use `.venv\Scripts\python.exe manage.py runserver` and Vite from `frontend` (`npm ci`, `npm run dev`). React is available at `/app/`; Django pages remain accessible when `REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED` is disabled.

## Main sections

The catalog contains properties, developers, company groups and residential complexes. Property details show attributes, images and a link to the mortgage calculator. Catalog moderators manage property and location dictionaries. Banks, mortgage programs, developer programs and the key rate have separate sections. Imports and external updates require the appropriate permissions.

The customer section requires authentication. A customer profile contains contacts, preferences, budget and linked market/tranche calculations. Financial capacity is an initial estimate. Select linked calculations for a combined Word report or unlink them; deleting a customer does not delete the calculations themselves.

## Mortgage calculations

Select a property and enter its price, discount/markup, down payment, date, term and rate. Percentages and rubles synchronize using the most recently edited value. Market mortgages support a grace period; tranche mortgages support one to five tranches, with the last receiving the remaining amount. A button expands the schedule beyond the first 12 payments.

Authenticated users can save calculations for a selected or manually entered property. “Заполнить объект вручную” opens city, district, developer, complex, building, layout and decoration selectors, plus apartment number, area and floor fields. Dictionaries support search while typing and loading more choices; selecting a complex fills its location and developer. Existing apartments are identified by building and apartment number; creating a new apartment when saving requires catalog moderator permissions. Changing the property or conditions after calculating requires recalculation before saving: the previous result remains available for comparison and is marked as outdated. Saved histories provide details, Excel/Word exports, a new calculation based on a sample and deletion with confirmation.

Property search covers the entire catalog; previous/next buttons navigate choice pages. The selected property remains available while searching for alternatives. Excel and Word buttons beside the result export the current market or tranche calculation without saving or signing in, including manual properties or financial parameters alone. Exports create no catalog or history records.

Money values display two decimal places, including kopecks in payments and balances. Both calculators show the down payment percentage/date, base price and adjustment, exact term in months, rate and payment count. Market results also show the grace term/rate, separate grace/main payment counts and debt after the grace period. The tranche table includes overpayment per tranche; “Остаток к выдаче” means the amount yet to be disbursed. Saved details include the apartment layout when an image is uploaded; click it to open the full-size image.

When legacy URLs redirect to React, property/customer context is translated from `property_id`/`customer` to `propertyId`/`customerId`. Legacy filter and sorting names are translated to the new interface parameters; functionality of filters not yet available is restored in subsequent stages.

## Developer programs and credit limits

Selecting a property and bank program applies active developer conditions: a specific complex takes priority over group-wide conditions. The adjustment, down payment, term, rate and grace period are populated; changing the program restores the base conditions. Zero rates are supported, including during the grace period. Exceeding the regional limit (or the federal fallback) shows the required/additional down payment and combined rate; apply your chosen option by editing the form fields. This is guidance, not an automatic calculation prohibition. A developer program's maximum loan amount is also considered when provided.

## Current migration limitations

Parity restoration is tracked in `.audit/REACT_PARITY_IMPLEMENTATION_PLAN.md`. Bank synchronization and the homepage map remain in progress. “Django-форма”/“Прежняя версия” fallback links open the legacy screen directly even when redirects are enabled. Unfinished stages must not be treated as available features.

## Working with tables

Click a column header to sort ascending, then click again to sort descending. An arrow shows the direction; headers also work with the keyboard. Paginated lists sort the entire server selection, retain filters and reset pagination. On phones, the “Сортировка” selector above the cards offers the same fields.

Text search applies while typing with a 250 ms delay; “Найти” remains available. Nested bank, limit, building, metro, tranche and schedule tables have their own “Поиск в таблице” field; sorting and search cover all loaded rows. Schedule search covers the full calculation even with the twelve-payment preview. Displayed dates and comma-separated money values are searchable. Wide nested tables scroll inside their cards on phones.

Tables and their mobile cards hide technical IDs, creation/update timestamps, internal activity flags and matching keys. Calculation, payment and Central Bank decision dates remain as business data. Key rate search preserves the delta against the previous decision in the full history. Linked customer calculations also show the down payment separately.

## Catalog and calculation filters

The property catalog combines city, developer, complex, building and layout selectors with apartment number, exact area and price fields. Both histories and linked customer calculations provide city and ranges for price, down payment, payment amount, term in years and rate. The payment range uses the market mortgage's main payment or the tranche mortgage's last payment. Tranche history shows maximum and last payments separately.

Numeric filters apply while typing with a 250 ms delay and reset pagination. Boundaries are inclusive; money boundaries use the displayed kopeck precision. For example, a term from `2.08` to `2.09` years selects 25 months. Filters and sorting remain in the URL, preserving customer selection context. Legacy range URLs translate to the corresponding React parameters.

## Large form dictionaries

In property, complex, customer, developer, bank/developer program, regional limit and location forms, use “Поиск: …” above a selector. Typing searches the entire relevant dictionary within the selected parent; “Показать ещё варианты” loads additional choices. Selected values load separately and remain available outside the first page. This also covers multiple developer regions, customer layouts and preferential programs, and property window views. Changing a region, city or complex clears dependent fields; review them before saving. If loading fails, use “Повторить загрузку справочника”.

For roles and operation see `role_model.md`, `application_initial_setup.md` and `manual_deployment.md`.
