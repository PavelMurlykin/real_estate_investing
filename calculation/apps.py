# calculation/apps.py
from django.apps import AppConfig


class CalculationConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'calculation'
    verbose_name = 'Расчет'
