# Loading to PostgreSQL With Django

Use this reference before writing imported records to the database.

## Idempotency

- Rerunning the same input must not create duplicates.
- Enforce uniqueness with database constraints where the domain allows it.
- Use `update_or_create()` for simple low-volume upserts.
- For high-volume upserts, use bulk operations and explicit conflict strategy.
- Keep source IDs or import fingerprints where they make reruns safer.

## Transactions

- Use `transaction.atomic()` around a logical import batch when partial writes would be harmful.
- For very large imports, chunk batches and record per-batch results.
- Make rollback behavior clear in logs and tests.
- Avoid mixing network calls inside long database transactions.

## Performance

- Preload existing lookup records into dictionaries by natural key.
- Use `select_related()` and `prefetch_related()` when resolving related objects repeatedly.
- Use `bulk_create()` and `bulk_update()` for large batches.
- Avoid per-row database queries in normalization loops.
- Use `values_list()` for existence checks and lookup maps.

## Model and Migration Concerns

- Add indexes for import lookup keys.
- Add constraints for invariants and deduplication keys.
- Use `Decimal` fields for financial values.
- Keep migrations generated and reviewable.
- Store import summaries when operators need auditability.

## Management Commands

- Prefer management commands for repeatable imports.
- Support `--dry-run`, `--limit`, and source/path options where useful.
- Print concise summaries: created, updated, skipped, failed.
- Return non-zero or raise `CommandError` for hard failures.
