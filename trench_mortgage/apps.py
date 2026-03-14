from django.apps import AppConfig


class TrenchMortgageConfig(AppConfig):
    """Описание класса TrenchMortgageConfig.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'trench_mortgage'
