from django.contrib.auth.base_user import BaseUserManager

from .utils import normalize_phone_number


class UserManager(BaseUserManager):
    """Описание класса UserManager.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        """Описание метода _create_user.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            email: Входной параметр, влияющий на работу метода.
            password: Входной параметр, влияющий на работу метода.
            **extra_fields: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        if not email:
            raise ValueError('The email must be set.')
        if not password:
            raise ValueError('The password must be set.')

        normalized_email = self.normalize_email(email).lower()
        phone_number = normalize_phone_number(extra_fields.get('phone_number'))
        if not phone_number:
            raise ValueError('The phone number must be set.')

        extra_fields['phone_number'] = phone_number
        user = self.model(email=normalized_email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        """Описание метода create_user.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            email: Входной параметр, влияющий на работу метода.
            password: Входной параметр, влияющий на работу метода.
            **extra_fields: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        """Описание метода create_superuser.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            email: Входной параметр, влияющий на работу метода.
            password: Входной параметр, влияющий на работу метода.
            **extra_fields: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError('Superuser must have is_staff=True.')
        if extra_fields.get('is_superuser') is not True:
            raise ValueError('Superuser must have is_superuser=True.')

        return self._create_user(email, password, **extra_fields)
