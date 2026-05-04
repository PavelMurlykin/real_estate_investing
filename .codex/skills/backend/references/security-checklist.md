# Django Security Checklist

Use this checklist for auth, authorization, request handling, file/email/external integrations, redirects, admin, and sensitive data changes.

## Access Control

- Protect private views with authentication decorators, mixins, or explicit checks.
- Filter objects by owner, tenant, role, or allowed scope before lookup.
- Treat object IDs in URLs as untrusted. Confirm permission before read, update, delete, or side effects.
- Test both allowed and denied users.

## Request Safety

- Preserve CSRF for unsafe methods.
- Accept writes only through POST, PUT, PATCH, or DELETE semantics used by the project.
- Validate all request data through forms, serializers, or explicit validators.
- Use `require_POST` or method checks for destructive actions.
- Constrain redirects with Django safe URL helpers or known route names.

## Data Protection

- Keep secrets in environment variables.
- Do not log passwords, tokens, reset links, raw email contents with secrets, or sensitive personal data.
- Keep error messages useful but not revealing.
- Avoid exposing existence checks for private records where that leaks information.

## Output and Files

- Let Django templates escape user content by default.
- Use `format_html()` instead of `mark_safe()` unless the HTML source is fully trusted.
- Validate uploaded file type, extension, size, and storage path before processing.
- Avoid constructing filesystem paths directly from user input.

## Admin and Staff Tools

- Keep admin querysets scoped where necessary.
- Do not expose sensitive fields in list displays, search fields, readonly fields, or exports unless explicitly required.
- Audit admin actions for bulk side effects and permissions.
