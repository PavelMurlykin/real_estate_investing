# ETL Testing and Observability

Use this reference before adding parser tests, import tests, logs, metrics, or job summaries.

## Parser Tests

- Test against saved HTML/JSON/file fixtures.
- Cover missing fields, changed labels, empty pages, blocked pages, and malformed rows.
- Keep fixture files small but representative.
- Assert typed normalized records rather than brittle internal parser details.

## Normalization Tests

- Test locale-specific decimals, dates, currency, whitespace, addresses, phones, and URLs.
- Test unknown enum/category handling.
- Test required-field failures.
- Test deduplication keys and conflict resolution.

## Load Tests

- Use `pytest.mark.django_db`.
- Test first run and rerun idempotency.
- Test changed source data updates the intended fields only.
- Test invalid records do not partially corrupt the database.
- Test transaction rollback for hard failures.
- Add query count or batch behavior tests for import paths expected to handle volume.

## Observability

- Log source name, run ID, counts, and concise failure reasons.
- Avoid logging sensitive personal data.
- Return import summaries from service functions.
- For management commands, print created, updated, skipped, failed, and duration.
- Keep raw failure samples or source metadata sufficient for debugging.
