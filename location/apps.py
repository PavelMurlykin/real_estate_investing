from django.apps import AppConfig


class LocationConfig(AppConfig):
    """Описание класса LocationConfig.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'location'
    verbose_name = 'Локации'

    def ready(self):
        """Register protection for additional station line memberships."""
        from . import signals  # noqa: F401
