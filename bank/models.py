from django.db import models

from core.models import BaseModel


class Bank(BaseModel):
    """Описание класса Bank.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    name = models.CharField(
        max_length=255, unique=True, verbose_name='Название'
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


class BankProgram(BaseModel):
    """Описание класса BankProgram.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    bank = models.ForeignKey(
        Bank, on_delete=models.PROTECT, verbose_name='Банк'
    )
    mortgage_program = models.ForeignKey(
        MortgageProgram,
        on_delete=models.PROTECT,
        verbose_name='Ипотечная программа',
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
