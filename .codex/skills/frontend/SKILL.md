---
name: frontend
description: React frontend development workflow for the future client side of this real_estate_investing application. Use when creating or changing React components, pages, forms, client routing, API integration, state management, frontend tests, accessibility, browser performance, build tooling, or frontend security. Enforce accessible UI, predictable data flow, secure handling of backend data, responsive behavior, performance awareness, and automated tests.
---

# Frontend

## Core Workflow

Use this skill for React frontend work in the application.

1. Inspect existing frontend conventions before adding tooling, folders, components, or style systems.
2. Keep UI behavior close to the user workflow: forms, validation, loading, empty, error, and success states must be deliberate.
3. Integrate with the Django backend through explicit API contracts and typed/validated response handling.
4. Build accessible, responsive components with predictable keyboard and screen-reader behavior.
5. Keep state local unless shared state is clearly needed.
6. Add or update tests for every new feature, component behavior, form flow, or regression.
7. Run focused frontend checks first, then broader build/test checks.

## Project Context

- Backend is Django with PostgreSQL.
- The current repository is mostly server-rendered Django; React may be introduced later.
- Prefer incremental adoption over a large rewrite unless the user explicitly asks for one.
- Keep backend and frontend contracts documented in code: URL names, API paths, payload shapes, status codes, validation errors, and auth behavior.

## Implementation Rules

- Prefer established project tooling if React already exists. If not, choose a minimal, standard React setup that fits Django integration.
- Use TypeScript for new React code unless the project has already standardized on JavaScript.
- Use semantic HTML first, then ARIA only where native HTML is insufficient.
- Avoid duplicating backend validation logic as the only source of truth. Frontend validation should improve UX; backend validation remains authoritative.
- Treat API data as untrusted. Validate critical shapes before rendering or mutating state.
- Do not store secrets in frontend code, build outputs, local storage, or public environment variables.
- Keep components small enough to test and reason about. Extract only when duplication or complexity is real.
- Keep styling consistent with any existing design system or CSS approach.

## React Architecture

Read `references/react-architecture.md` before adding React tooling, routing, shared state, API clients, or a substantial component tree.

Always decide:

- Where React is mounted inside Django templates or whether a separate client app is warranted.
- How API calls authenticate and handle CSRF/session behavior.
- How loading, empty, error, optimistic, and stale states behave.
- Which data belongs in URL state, local component state, server cache, or shared client state.

## Accessibility and UX

Read `references/accessibility-ux.md` when changing forms, navigation, modals, tables, filters, dashboards, maps, keyboard workflows, or any user-facing page.

Always check:

- Keyboard access and focus order.
- Labels, names, and error messages for form controls.
- Color contrast and non-color cues.
- Responsive layout without overlapping text or controls.
- Screen-reader semantics for dynamic updates.

## Performance and Security

Read `references/frontend-performance-security.md` for data-heavy pages, dashboards, maps, large lists, file handling, external scripts, auth-sensitive views, or build configuration.

Always check:

- Bundle size and code splitting for heavy views.
- Avoiding unnecessary rerenders in repeated rows and interactive tables.
- Safe rendering of user content.
- CSRF, credentials, and same-origin behavior for API calls.
- No secrets or private backend data in client-visible config.

## Testing

Read `references/frontend-testing.md` before adding or changing frontend tests.

New frontend functionality should have tests for:

- User-visible behavior, not implementation details.
- Form validation and error display.
- API success and failure states.
- Permission/auth-sensitive UI states.
- Important regressions and edge cases.

## Verification

Use the narrowest useful commands for the current frontend toolchain. Typical commands once React tooling exists:

```powershell
npm test
npm run lint
npm run typecheck
npm run build
```

If tooling does not exist yet, add only the minimal scripts and dependencies needed for the requested work.
