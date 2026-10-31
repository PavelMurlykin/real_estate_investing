# User manual

## Starting the application

Configure `.env` using `.env.example`, then run `docker compose up -d --build` from the repository root. Open the nginx address configured in `compose.yaml`. For local development use `.venv\Scripts\python.exe manage.py runserver` and Vite from `frontend` (`npm ci`, `npm run dev`). React is available at `/app/`; Django pages remain accessible when `REACT_FRONTEND_LEGACY_REDIRECTS_ENABLED` is disabled.

## Main sections

The catalog contains properties, developers, company groups and residential complexes. Property details show attributes, images and a link to the mortgage calculator. Catalog moderators manage property and location dictionaries. Banks, mortgage programs, developer programs and the key rate have separate sections. Imports and external updates require the appropriate permissions.

The customer section requires authentication. A customer profile contains contacts, preferences, budget and linked market/tranche calculations. Financial capacity is an initial estimate. Select linked calculations for a combined Word report or unlink them; deleting a customer does not delete the calculations themselves.

## Mortgage calculations

Select a property and enter its price, discount/markup, down payment, date, term and rate. Percentages and rubles synchronize using the most recently edited value. Market mortgages support a grace period; tranche mortgages support one to five tranches, with the last receiving the remaining amount. A button expands the schedule beyond the first 12 payments.

Authenticated users can save calculations for a selected property. Changing the property or conditions after calculating requires recalculation before saving: the previous result remains available for comparison and is marked as outdated. Saved histories provide details, Excel/Word exports, a new calculation based on a sample and deletion with confirmation.

When legacy URLs redirect to React, property/customer context is translated from `property_id`/`customer` to `propertyId`/`customerId`. Legacy filter and sorting names are translated to the new interface parameters; functionality of filters not yet available is restored in subsequent stages.

## Developer programs and credit limits

Selecting a property and bank program applies active developer conditions: a specific complex takes priority over group-wide conditions. The adjustment, down payment, term, rate and grace period are populated; changing the program restores the base conditions. Zero rates are supported, including during the grace period. Exceeding the regional limit (or the federal fallback) shows the required/additional down payment and combined rate; apply your chosen option by editing the form fields. This is guidance, not an automatic calculation prohibition. A developer program's maximum loan amount is also considered when provided.

## Current migration limitations

Parity restoration is tracked in `.audit/REACT_PARITY_IMPLEMENTATION_PLAN.md`. Manual property data cannot yet be saved and unsaved exports are unavailable. Large dictionaries, result fields, money formatting, filters, table sorting and the homepage still have limitations. Use Django with legacy redirects disabled for the previous workflows. Unfinished stages must not be treated as available features.

For roles and operation see `role_model.md`, `application_initial_setup.md` and `manual_deployment.md`.
