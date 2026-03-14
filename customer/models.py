from decimal import ROUND_HALF_UP, Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from bank.models import KeyRate, MortgageProgram
from core.models import BaseModel
from location.models import City, District
from property.models import ApartmentLayout


class Customer(BaseModel):
    """Описание класса Customer.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    PURCHASE_GOAL_LIVING = 'living'
    PURCHASE_GOAL_INVESTMENT = 'investment'
    PURCHASE_GOAL_CHOICES = (
        (PURCHASE_GOAL_LIVING, 'Для жизни'),
        (PURCHASE_GOAL_INVESTMENT, 'Для инвестиций'),
    )

    MAX_MORTGAGE_TERM_YEARS = 30
    MAX_AGE_FOR_MORTGAGE = 75
    RATE_MARGIN = Decimal('2')

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='customers',
        verbose_name='Пользователь',
    )

    # Персональные данные
    first_name = models.CharField(max_length=150, verbose_name='Имя')
    last_name = models.CharField(
        max_length=150, blank=True, verbose_name='Фамилия'
    )
    phone = models.CharField(max_length=30, blank=True, verbose_name='Телефон')
    email = models.EmailField(blank=True, verbose_name='Почта')
    age = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Возраст'
    )
    birth_date = models.DateField(
        null=True, blank=True, verbose_name='Дата рождения'
    )
    birth_year = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Год рождения'
    )
    residence_city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='residence_customers',
        verbose_name='Город проживания',
    )

    # Платежеспособность
    initial_payment_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Первый взнос, руб.',
    )
    max_monthly_payment = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Максимальный ежемесячный платёж, руб.',
    )
    preferential_programs = models.ManyToManyField(
        MortgageProgram,
        blank=True,
        related_name='customers_with_preferential_access',
        limit_choices_to={'is_preferential': True},
        verbose_name='Доступные льготные программы',
    )
    has_owned_property = models.BooleanField(
        null=True,
        blank=True,
        choices=((True, 'Да'), (False, 'Нет')),
        verbose_name='Наличие недвижимости в собственности',
    )

    # Параметры для подбора объекта недвижимости
    purchase_goal = models.CharField(
        max_length=20,
        choices=PURCHASE_GOAL_CHOICES,
        blank=True,
        verbose_name='Цель покупки',
    )
    desired_city = models.ForeignKey(
        City,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='desired_city_customers',
        verbose_name='Желаемый город покупки',
    )
    desired_district = models.ForeignKey(
        District,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='desired_district_customers',
        verbose_name='Желаемый район покупки',
    )
    desired_layouts = models.ManyToManyField(
        ApartmentLayout,
        blank=True,
        related_name='customers',
        verbose_name='Планировка',
    )
    area_min = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Площадь квартиры от, м2',
    )
    area_max = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        verbose_name='Площадь квартиры до, м2',
    )
    desired_floor = models.CharField(
        max_length=100, blank=True, verbose_name='Этаж'
    )
    cardinal_directions = models.CharField(
        max_length=255, blank=True, verbose_name='Стороны света'
    )
    comment = models.TextField(blank=True, verbose_name='Комментарий')

    class Meta(BaseModel.Meta):
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        db_table = 'customer'
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'
        ordering = ['-created_at', 'first_name', 'last_name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        full_name = self.full_name
        return full_name if full_name else f'Клиент #{self.pk}'

    @property
    def full_name(self):
        """Описание метода full_name.

        Выполняет прикладную операцию текущего модуля.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        return f'{self.first_name} {self.last_name}'.strip()

    @staticmethod
    def _calculate_age_from_date(birth_date, today):
        """Описание метода _calculate_age_from_date.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            birth_date: Входной параметр, влияющий на работу метода.
            today: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        return (
            today.year
            - birth_date.year
            - ((today.month, today.day) < (birth_date.month, birth_date.day))
        )

    def _sync_age_from_birth_data(self):
        """Описание метода _sync_age_from_birth_data.

        Выполняет прикладную операцию текущего модуля.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        today = timezone.localdate()
        if self.birth_date:
            self.age = self._calculate_age_from_date(self.birth_date, today)
            self.birth_year = self.birth_date.year
            return
        if self.birth_year:
            self.age = today.year - self.birth_year

    def clean(self):
        """Описание метода clean.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        super().clean()

        if not self.first_name or not self.first_name.strip():
            raise ValidationError(
                {'first_name': 'Поле "Имя" обязательно для заполнения.'}
            )

        self.first_name = self.first_name.strip()
        self.last_name = self.last_name.strip()
        self.phone = self.phone.strip()
        self.desired_floor = self.desired_floor.strip()
        self.cardinal_directions = self.cardinal_directions.strip()
        self.comment = self.comment.strip()

        if self.email:
            self.email = self.email.strip().lower()

        today = timezone.localdate()
        if self.birth_date and self.birth_date > today:
            raise ValidationError(
                {'birth_date': 'Дата рождения не может быть в будущем.'}
            )
        if self.birth_year and self.birth_year > today.year:
            raise ValidationError(
                {'birth_year': 'Год рождения не может быть в будущем.'}
            )

        self._sync_age_from_birth_data()

        if self.age is not None and self.age < 0:
            raise ValidationError(
                {'age': 'Возраст не может быть отрицательным.'}
            )

        if (
            self.area_min is not None
            and self.area_max is not None
            and self.area_min > self.area_max
        ):
            raise ValidationError(
                {
                    'area_max': (
                        'Максимальная площадь должна быть не меньше '
                        'минимальной.'
                    )
                }
            )

        if (
            self.desired_city
            and self.desired_district
            and self.desired_district.city_id != self.desired_city_id
        ):
            raise ValidationError(
                {
                    'desired_district': (
                        'Район должен относиться к выбранному городу.'
                    )
                }
            )

    def save(self, *args, **kwargs):
        """Описание метода save.

        Сохраняет объект и связанные вычисленные значения.

        Аргументы:
            *args: Входной параметр, влияющий на работу метода.
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Результат стандартного механизма сохранения.
        """
        self._sync_age_from_birth_data()
        super().save(*args, **kwargs)

    @classmethod
    def get_actual_cbr_key_rate(cls):
        """Описание метода get_actual_cbr_key_rate.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        rate = (
            KeyRate.objects.order_by('-meeting_date')
            .values_list('key_rate', flat=True)
            .first()
        )
        return rate if rate is not None else Decimal('0')

    def get_effective_annual_rate(self):
        """Описание метода get_effective_annual_rate.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return self.get_actual_cbr_key_rate() + self.RATE_MARGIN

    def get_max_mortgage_term_years(self):
        """Описание метода get_max_mortgage_term_years.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        if self.age is None:
            return self.MAX_MORTGAGE_TERM_YEARS

        remaining_years = self.MAX_AGE_FOR_MORTGAGE - int(self.age)
        if remaining_years <= 0:
            return 0
        return min(self.MAX_MORTGAGE_TERM_YEARS, remaining_years)

    def calculate_max_property_cost(
        self, annual_rate=None, max_term_years=None
    ):
        """Описание метода calculate_max_property_cost.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            annual_rate: Входной параметр, влияющий на работу метода.
            max_term_years: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        down_payment = self.initial_payment_amount or Decimal('0')
        monthly_payment = self.max_monthly_payment or Decimal('0')

        if down_payment <= 0 and monthly_payment <= 0:
            return None

        term_years = (
            self.get_max_mortgage_term_years()
            if max_term_years is None
            else int(max_term_years)
        )
        if term_years <= 0:
            return down_payment if down_payment > 0 else None

        months = term_years * 12
        annual_rate_decimal = self.get_effective_annual_rate()
        if annual_rate is not None:
            annual_rate_decimal = Decimal(str(annual_rate))

        monthly_rate = (annual_rate_decimal / Decimal('100')) / Decimal('12')
        credit_amount = Decimal('0')
        if monthly_payment > 0:
            if monthly_rate == 0:
                credit_amount = monthly_payment * Decimal(months)
            else:
                discount_factor = (Decimal('1') + monthly_rate) ** (-months)
                credit_amount = (
                    monthly_payment
                    * (Decimal('1') - discount_factor)
                    / monthly_rate
                )

        total_property_cost = down_payment + credit_amount
        if total_property_cost <= 0:
            return None
        return total_property_cost.quantize(
            Decimal('0.01'), rounding=ROUND_HALF_UP
        )
