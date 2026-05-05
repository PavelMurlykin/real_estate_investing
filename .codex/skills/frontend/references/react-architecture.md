# React Architecture

Use this reference when adding React tooling, app structure, routing, API clients, shared state, or a substantial component tree.

## Integration With Django

- Prefer incremental React mounts inside Django templates when only part of the app needs richer interactivity.
- Prefer a separate React app only when routing, state, and UI surface justify it.
- Make Django own authentication, permissions, and authoritative validation unless a future API architecture explicitly changes that.
- Keep API paths, request payloads, response payloads, error shapes, and status codes easy to find.
- For session-authenticated requests, preserve CSRF handling and same-origin credentials.

## Structure

- Keep app-level setup separate from domain features.
- Keep domain components near the domain they serve.
- Keep reusable UI primitives small and generic.
- Avoid global state until state is needed across distant components or routes.
- Prefer URL state for filters, search, pagination, and sharable view state.
- Prefer server-state tools only when repeated remote state coordination warrants them.

## Data Flow

- Parse and validate critical API responses before rendering.
- Normalize API values at boundaries: dates, money, percentages, IDs, and nullable fields.
- Keep derived data as derived data; avoid storing duplicate derived state unless profiling proves it necessary.
- Handle loading, empty, error, and retry states explicitly.
- Avoid optimistic updates unless rollback behavior is clear and tested.

## Forms

- Keep backend validation authoritative.
- Mirror obvious frontend validation for speed and clarity.
- Preserve server-side validation errors and field-level messages.
- Prevent duplicate submissions while a mutation is pending.
- Keep form state reset behavior deliberate after success or failure.
