from django.apps import AppConfig


class CustomerConfig(AppConfig):
    """Описание класса CustomerConfig.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'customer'
    verbose_name = 'Клиенты'
