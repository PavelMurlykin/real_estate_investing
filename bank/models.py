from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from core.models import BaseModel
from location.models import Region


class Bank(BaseModel):
    """Описание класса Bank.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    name = models.CharField(
        max_length=255, unique=True, verbose_name='Название'
    )
    logo_url = models.URLField(
        max_length=1000,
        blank=True,
        default='',
        verbose_name='Логотип',
    )
    interest_rate = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name='Процентная ставка, %'
    )
    salary_client_discount = models.DecimalField(
        max_digits=4,
        decimal_places=2,
        default=0,
        verbose_name='Дисконт по ставке для зарплатных клиентов, п.п.',
    )
    maximum_loan_term_years = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name='Максимальный срок кредита, лет',
    )
    mortgage_programs = models.ManyToManyField(
        'MortgageProgram',
        through='BankProgram',
        related_name='banks',
        verbose_name='Ипотечные программы',
    )

    class Meta(BaseModel.Meta):
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        db_table = 'bank'
        verbose_name = 'Банк'
        verbose_name_plural = 'Банки'
        ordering = ['name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name


class MortgageProgram(BaseModel):
    """Описание класса MortgageProgram.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    name = models.CharField(
        max_length=255, unique=True, verbose_name='Название'
    )
    condition = models.TextField(verbose_name='Условие')
    is_preferential = models.BooleanField(
        default=False, verbose_name='Льготная программа'
    )
    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Кредитный лимит',
    )

    class Meta(BaseModel.Meta):
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        db_table = 'mortgage_program'
        verbose_name = 'Ипотечная программа'
        verbose_name_plural = 'Ипотечные программы'
        ordering = ['name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name

    def get_credit_limit(self, region=None):
        """Возвращает лимит суммы кредита для льготной программы."""
        if not self.is_preferential:
            return None

        if region is None:
            return self.credit_limit

        region_id = getattr(region, 'pk', region)
        prefetched_credit_limits = getattr(
            self, '_prefetched_objects_cache', {}
        ).get('regional_credit_limits')
        if prefetched_credit_limits is not None:
            for regional_credit_limit in prefetched_credit_limits:
                if (
                    regional_credit_limit.is_active
                    and regional_credit_limit.region_id == region_id
                ):
                    return regional_credit_limit.credit_limit
            return self.credit_limit

        regional_credit_limit = (
            self.regional_credit_limits.filter(
                region_id=region_id,
                is_active=True,
            )
            .values_list('credit_limit', flat=True)
            .first()
        )
        if regional_credit_limit is not None:
            return regional_credit_limit

        return self.credit_limit


class MortgageProgramRegionalCreditLimit(BaseModel):
    """Региональное исключение кредитного лимита ипотечной программы."""

    mortgage_program = models.ForeignKey(
        MortgageProgram,
        on_delete=models.CASCADE,
        related_name='regional_credit_limits',
        verbose_name='Ипотечная программа',
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name='mortgage_program_credit_limits',
        verbose_name='Регион',
    )
    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Кредитный лимит',
    )

    class Meta(BaseModel.Meta):
        """Метаданные региональных исключений кредитного лимита."""

        db_table = 'mortgage_program_regional_credit_limit'
        verbose_name = 'Региональный лимит ипотечной программы'
        verbose_name_plural = 'Региональные лимиты ипотечных программ'
        ordering = ['mortgage_program__name', 'region__name']
        constraints = [
            models.UniqueConstraint(
                fields=['mortgage_program', 'region'],
                name='unique_mortgage_program_region_credit_limit',
            )
        ]

    def __str__(self):
        """Возвращает строковое представление регионального лимита."""
        return (
            f'{self.mortgage_program} - {self.region}: '
            f'{self.credit_limit}'
        )


class BankProgram(BaseModel):
    """Описание класса BankProgram.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    bank = models.ForeignKey(
        Bank, on_delete=models.CASCADE, verbose_name='Банк'
    )
    mortgage_program = models.ForeignKey(
        MortgageProgram,
        on_delete=models.PROTECT,
        verbose_name='Ипотечная программа',
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Процентная ставка, %',
    )
    minimum_initial_payment_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Минимальный первый взнос, %',
    )
    maximum_loan_term_years = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name='Максимальный срок кредита, лет',
    )

    class Meta(BaseModel.Meta):
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        db_table = 'bank_program'
        verbose_name = 'Программа банка'
        verbose_name_plural = 'Программы банков'
        unique_together = ('bank', 'mortgage_program')
        ordering = ['bank__name', 'mortgage_program__name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return f'{self.bank} - {self.mortgage_program}'


class KeyRate(BaseModel):
    """Описание класса KeyRate.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    meeting_date = models.DateField(unique=True, verbose_name='Дата заседания')
    key_rate = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name='Ключевая ставка, %'
    )

    class Meta(BaseModel.Meta):
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        db_table = 'key_rate'
        verbose_name = 'Ключевая ставка'
        verbose_name_plural = 'Ключевые ставки'
        ordering = ['-meeting_date']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return f'{self.meeting_date}: {self.key_rate}%'
