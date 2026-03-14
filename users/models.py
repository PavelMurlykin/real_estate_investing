from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import models

from .managers import UserManager
from .utils import normalize_phone_number


class User(AbstractUser):
    """Описание класса User.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    username = None

    first_name = models.CharField(max_length=150, verbose_name='First name')
    last_name = models.CharField(max_length=150, verbose_name='Last name')
    email = models.EmailField(unique=True, verbose_name='Email')
    phone_number = models.CharField(
        max_length=20, unique=True, verbose_name='Phone number'
    )
    is_real_estate_agent = models.BooleanField(
        default=False, verbose_name='Real estate agent'
    )
    agency_name = models.CharField(
        max_length=255, blank=True, verbose_name='Agency name'
    )

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['phone_number', 'first_name', 'last_name']

    class Meta:
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def clean(self):
        """Описание метода clean.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        super().clean()

        self.email = self.__class__.objects.normalize_email(self.email).lower()
        self.phone_number = normalize_phone_number(self.phone_number)

        if not self.phone_number:
            raise ValidationError(
                {'phone_number': 'Enter a valid phone number.'}
            )
        if self.is_real_estate_agent and not self.agency_name.strip():
            raise ValidationError(
                {'agency_name': 'Agency name is required for agents.'}
            )

        if not self.is_real_estate_agent:
            self.agency_name = ''

    def save(self, *args, **kwargs):
        """Описание метода save.

        Сохраняет объект и связанные вычисленные значения.

        Аргументы:
            *args: Входной параметр, влияющий на работу метода.
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Результат стандартного механизма сохранения.
        """
        self.email = self.__class__.objects.normalize_email(self.email).lower()
        self.phone_number = normalize_phone_number(self.phone_number)
        if not self.is_real_estate_agent:
            self.agency_name = ''
        return super().save(*args, **kwargs)

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        full_name = self.get_full_name().strip()
        if full_name:
            return full_name
        return self.email
