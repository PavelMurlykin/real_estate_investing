# mortgage/apps.py
from django.apps import AppConfig


class CalculatorConfig(AppConfig):
    """Описание класса CalculatorConfig.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mortgage'
    verbose_name = 'Ипотека'
