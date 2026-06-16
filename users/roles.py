"""Application role helpers."""

from django.contrib.auth.mixins import UserPassesTestMixin

MODERATOR_GROUP_NAME = 'moderators'
APPLICATION_ADMINISTRATOR_GROUP_NAME = 'application_administrators'
APPLICATION_ROLE_GROUP_NAMES = (
    MODERATOR_GROUP_NAME,
    APPLICATION_ADMINISTRATOR_GROUP_NAME,
)


def get_user_group_names(user):
    """Return cached group names for a user."""
    if not getattr(user, 'is_authenticated', False):
        return set()

    group_names = getattr(user, '_application_role_group_names', None)
    if group_names is None:
        group_names = set(user.groups.values_list('name', flat=True))
        user._application_role_group_names = group_names
    return group_names


def is_application_administrator(user):
    """Return whether a user has application administrator rights."""
    if not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'is_superuser', False):
        return True
    return APPLICATION_ADMINISTRATOR_GROUP_NAME in get_user_group_names(user)


def is_moderator(user):
    """Return whether a user has moderator rights."""
    if is_application_administrator(user):
        return True
    return MODERATOR_GROUP_NAME in get_user_group_names(user)


def can_manage_catalogs(user):
    """Return whether a user can mutate global catalogs."""
    return is_moderator(user)


def can_sync_external_data(user):
    """Return whether a user can run external data synchronization."""
    return is_application_administrator(user)


def can_view_private_records(user):
    """Return whether a user can view customers and saved calculations."""
    return getattr(user, 'is_authenticated', False)


def can_view_all_private_records(user):
    """Return whether a user can view all private customer records."""
    return is_application_administrator(user)


class CatalogManagementRequiredMixin(UserPassesTestMixin):
    """Require moderator-level access for global catalog writes."""

    raise_exception = True

    def test_func(self):
        """Return whether the request user can manage catalogs."""
        return can_manage_catalogs(self.request.user)


class ExternalDataSyncRequiredMixin(UserPassesTestMixin):
    """Require administrator-level access for external sync actions."""

    raise_exception = True

    def test_func(self):
        """Return whether the request user can run sync actions."""
        return can_sync_external_data(self.request.user)
