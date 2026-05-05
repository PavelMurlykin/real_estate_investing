# Accessibility and UX

Use this reference for forms, navigation, modals, filters, tables, dashboards, maps, and any user-facing React interface.

## Accessibility

- Use semantic HTML before ARIA.
- Every control needs an accessible name.
- Labels must be programmatically associated with fields.
- Error messages should be connected to fields with `aria-describedby` when needed.
- Focus must move deliberately when opening and closing modals, drawers, and dialogs.
- Keyboard users must be able to reach, operate, and leave every interactive element.
- Do not rely only on color to communicate state.
- Dynamic async updates should be announced when they affect task progress or errors.

## Responsive UI

- Define stable dimensions for fixed-format controls, grids, cards, counters, maps, and toolbars.
- Avoid text overlap at mobile and desktop sizes.
- Do not scale font size directly with viewport width.
- Make dense operational screens scannable: clear hierarchy, predictable alignment, restrained decoration.
- Preserve useful information density for repeated workflows.

## Forms and Tables

- Show validation errors near the relevant field.
- Preserve entered data after validation failures.
- Disable or guard duplicate submissions.
- For tables and lists, provide clear empty states and stable sorting/filtering behavior.
- For destructive actions, require clear intent and show the resulting state after completion.
