# Frontend Testing

Use this reference before adding or changing React tests.

## Test Strategy

- Prefer tests that exercise user behavior through accessible queries.
- Use component tests for focused rendering and interaction.
- Use integration tests for API-backed forms, filters, and workflows.
- Use end-to-end tests only for critical cross-page flows or where browser behavior is the point.
- Mock network boundaries deliberately and keep mock payloads realistic.

## Coverage Expectations

- Render states: loading, empty, success, and error.
- Form behavior: validation, submission, duplicate-submit prevention, server errors, and success.
- Access control: hidden/disabled actions where permissions affect UI.
- Regression cases for bug fixes.
- Query-sensitive UI: pagination, filtering, sorting, and stale request handling.

## Preferred Tooling

When no project standard exists, prefer:

- Vitest for unit/component tests.
- React Testing Library for user-facing component tests.
- MSW for API mocking when workflows depend on HTTP behavior.
- Playwright for critical browser flows when needed.

## Commands

Use the scripts defined by the project. Typical scripts:

```powershell
npm test
npm run test:watch
npm run lint
npm run typecheck
npm run build
```
