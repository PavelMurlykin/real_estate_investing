from django.apps import AppConfig


class ApiV1Config(AppConfig):
    """Configure the versioned application API."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api_v1'
    verbose_name = 'API v1'
