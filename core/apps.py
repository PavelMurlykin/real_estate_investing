from django.apps import AppConfig


class CoreConfig(AppConfig):
    """Описание класса CoreConfig.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
