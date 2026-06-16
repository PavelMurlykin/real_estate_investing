"""Template context helpers for application roles."""

from .roles import (
    can_manage_catalogs,
    can_sync_external_data,
    can_view_all_private_records,
    can_view_private_records,
    is_application_administrator,
    is_moderator,
)


def application_roles(request):
    """Expose application role flags to templates."""
    user = request.user
    return {
        'is_moderator': is_moderator(user),
        'is_application_administrator': is_application_administrator(user),
        'can_manage_catalogs': can_manage_catalogs(user),
        'can_sync_external_data': can_sync_external_data(user),
        'can_view_private_records': can_view_private_records(user),
        'can_view_all_private_records': can_view_all_private_records(user),
    }
