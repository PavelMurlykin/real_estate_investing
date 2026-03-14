# property/apps.py
from django.apps import AppConfig


class PropertyConfig(AppConfig):
    """Описание класса PropertyConfig.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'property'
    verbose_name = 'Недвижимость'
