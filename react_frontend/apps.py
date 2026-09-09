from django.apps import AppConfig


class ReactFrontendConfig(AppConfig):
    """Configure the React frontend gateway."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'react_frontend'
    verbose_name = 'React frontend'
