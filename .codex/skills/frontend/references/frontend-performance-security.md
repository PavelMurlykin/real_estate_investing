# Frontend Performance and Security

Use this reference for heavy pages, dashboards, large lists, maps, external scripts, auth-sensitive views, and build configuration.

## Performance

- Split code by route or heavy feature when bundle size starts to matter.
- Lazy-load charts, maps, editors, and other heavy UI only when needed.
- Virtualize long lists only when pagination or server-side filtering is not enough.
- Memoize only after identifying a real rerender or expensive computation.
- Debounce search/filter requests and cancel stale requests.
- Keep images sized, compressed, and lazy-loaded where appropriate.
- Prefer server-side pagination/filtering for large datasets.

## API Safety

- Treat all API data as untrusted.
- Escape or safely render user-provided content. Avoid raw HTML rendering.
- Send credentials only to trusted same-origin APIs unless explicitly required.
- Preserve CSRF behavior for unsafe requests.
- Handle 401, 403, 404, 409, and 422/400 responses intentionally.
- Do not expose private data in client logs, telemetry, query strings, or persisted client storage.

## Build and Config

- Never put secrets in frontend environment variables or built assets.
- Keep public config clearly named and non-sensitive.
- Pin critical tooling versions when reproducibility matters.
- Keep source maps, debug flags, and error overlays appropriate for the environment.
