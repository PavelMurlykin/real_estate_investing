# Normalization

Use this reference before transforming raw source values into project records.

## Typed Intermediate Records

- Normalize raw data into explicit typed structures before writing models.
- Keep parsing and database writes separate.
- Preserve source metadata: URL, source ID, fetched timestamp, row number, or checksum when useful.
- Track whether a value was provided, inferred, defaulted, or missing.

## Common Real Estate Fields

- Normalize names by trimming whitespace and collapsing repeated spaces.
- Normalize addresses consistently, but avoid over-merging distinct addresses.
- Normalize phone numbers and URLs before deduplication.
- Use `Decimal` for money, rates, areas, and percentages where precision matters.
- Parse dates with explicit locale and timezone assumptions.
- Keep units explicit: square meters, floors, rooms, rates, terms, and currency.

## Validation

- Define required fields per target model or import action.
- Reject records that would violate core invariants.
- Skip or quarantine records with recoverable source defects.
- Keep clear error messages with source location.
- Avoid silently coercing unknown enum/category values; map them explicitly or flag them.

## Deduplication

- Define natural keys before loading.
- Prefer stable source IDs when available.
- Use canonicalized names or addresses only with additional context to avoid false merges.
- Define conflict resolution: source wins, local wins, newest wins, or manual review.
- Test reruns with identical and changed source data.
