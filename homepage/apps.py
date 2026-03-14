from django.apps import AppConfig


class HomepageConfig(AppConfig):
    """Описание класса HomepageConfig.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'homepage'
