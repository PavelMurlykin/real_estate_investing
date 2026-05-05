# property/models.py
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from core.models import BaseModel
from location.models import District, Metro

User = get_user_model()


class Developer(BaseModel):
    """
    Справочник застройщиков.
    """

    name = models.CharField(
        max_length=255, unique=True, verbose_name='Застройщик'
    )
    description = models.TextField(
        blank=True, null=True, verbose_name='Описание'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'developer'
        verbose_name = 'Застройщик'
        verbose_name_plural = 'Застройщики'
        ordering = ['name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name


class RealEstateType(BaseModel):
    """
    Справочник типов недвижимости.
    """

    name = models.CharField(
        max_length=100, unique=True, verbose_name='Тип недвижимости'
    )
    description = models.TextField(
        blank=True, null=True, verbose_name='Описание'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'real_estate_type'
        verbose_name = 'Тип недвижимости'
        verbose_name_plural = 'Типы недвижимости'
        ordering = ['name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name


class RealEstateClass(BaseModel):
    """
    Справочник типов недвижимости.
    """

    name = models.CharField(
        max_length=100, unique=True, verbose_name='Класс ЖК'
    )
    description = models.TextField(
        blank=True, null=True, verbose_name='Описание'
    )
    weight = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name='Коэффициент класса'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'real_estate_class'
        verbose_name = 'Класс ЖК'
        verbose_name_plural = 'Классы ЖК'
        ordering = ['weight']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name


class RealEstateComplex(BaseModel):
    """
    Справочник ЖК.
    """

    name = models.CharField(max_length=255, verbose_name='ЖК')
    description = models.TextField(
        blank=True, null=True, verbose_name='Описание'
    )
    map_link = models.TextField(
        blank=True, null=True, verbose_name='Ссылка на картах'
    )
    presentation_link = models.TextField(
        blank=True, null=True, verbose_name='Ссылка на презентацию'
    )

    developer = models.ForeignKey(
        Developer, on_delete=models.PROTECT, verbose_name='Застройщик'
    )
    district = models.ForeignKey(
        District, on_delete=models.PROTECT, verbose_name='Район'
    )
    real_estate_class = models.ForeignKey(
        RealEstateClass, on_delete=models.PROTECT, verbose_name='Класс ЖК'
    )
    real_estate_type = models.ForeignKey(
        RealEstateType,
        on_delete=models.PROTECT,
        verbose_name='Тип недвижимости',
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'real_estate_complex'
        verbose_name = 'ЖК'
        verbose_name_plural = 'ЖК'
        unique_together = ('name', 'developer')
        ordering = ['name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name


class RealEstateComplexMetroAvailability(BaseModel):
    """
    Доступность метро относительно ЖК.
    """

    real_estate_complex = models.ForeignKey(
        RealEstateComplex,
        on_delete=models.CASCADE,
        related_name='metro_availability',
        verbose_name='ЖК',
    )
    metro = models.ForeignKey(
        Metro,
        on_delete=models.PROTECT,
        verbose_name='Станция метро',
    )
    walking_time_minutes = models.PositiveSmallIntegerField(
        verbose_name='Время до метро, мин. пешком'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'real_estate_complex_metro_availability'
        verbose_name = 'Доступность метро ЖК'
        verbose_name_plural = 'Доступность метро ЖК'
        unique_together = ('real_estate_complex', 'metro')
        ordering = ['walking_time_minutes', 'metro__station']

    def __str__(self):
        """Возвращает строковое представление доступности метро."""
        return (
            f'{self.real_estate_complex}: {self.metro} '
            f'({self.walking_time_minutes} мин.)'
        )


class RealEstateComplexBuilding(BaseModel):
    """
    Список корпусов ЖК.
    """

    class Quarter(models.IntegerChoices):
        FIRST = 1, 'I кв.'
        SECOND = 2, 'II кв.'
        THIRD = 3, 'III кв.'
        FOURTH = 4, 'IV кв.'

    number = models.CharField(max_length=100, verbose_name='Корпус')
    address = models.CharField(null=True, max_length=255, verbose_name='Адрес')
    commissioning_date = models.DateField(
        null=True, blank=True, verbose_name='Дата ввода в эксплуатацию'
    )
    commissioning_year = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Год ввода в эксплуатацию'
    )
    commissioning_quarter = models.PositiveSmallIntegerField(
        choices=Quarter.choices,
        null=True,
        blank=True,
        verbose_name='Квартал ввода в эксплуатацию',
    )
    key_handover_date = models.DateField(
        null=True, blank=True, verbose_name='Дата выдачи ключей'
    )
    key_handover_year = models.PositiveSmallIntegerField(
        null=True, blank=True, verbose_name='Год выдачи ключей'
    )
    key_handover_quarter = models.PositiveSmallIntegerField(
        choices=Quarter.choices,
        null=True,
        blank=True,
        verbose_name='Квартал выдачи ключей',
    )

    real_estate_complex = models.ForeignKey(
        RealEstateComplex, on_delete=models.CASCADE, verbose_name='ЖК'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'real_estate_complex_building'
        verbose_name = 'Корпус ЖК'
        verbose_name_plural = 'Корпуса ЖК'
        unique_together = ('number', 'real_estate_complex')
        ordering = ['number']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.number

    def clean(self):
        super().clean()
        self._clean_period_fields(
            'commissioning',
            'Укажите либо точную дату ввода в эксплуатацию, либо год и квартал.',
        )
        self._clean_period_fields(
            'key_handover',
            'Укажите либо точную дату выдачи ключей, либо год и квартал.',
        )

    def _clean_period_fields(self, prefix, message):
        date = getattr(self, f'{prefix}_date')
        year = getattr(self, f'{prefix}_year')
        quarter = getattr(self, f'{prefix}_quarter')

        if date and (year or quarter):
            raise ValidationError(
                {
                    f'{prefix}_date': message,
                    f'{prefix}_year': message,
                    f'{prefix}_quarter': message,
                }
            )

        if bool(year) != bool(quarter):
            raise ValidationError(
                {
                    f'{prefix}_year': 'Для квартального срока укажите год и квартал.',
                    f'{prefix}_quarter': 'Для квартального срока укажите год и квартал.',
                }
            )

    def _format_period(self, date, year, quarter):
        if date:
            return date
        if year and quarter:
            return f'{self.Quarter(quarter).label} {year}'
        return ''

    def get_commissioning_display(self):
        return self._format_period(
            self.commissioning_date,
            self.commissioning_year,
            self.commissioning_quarter,
        )

    def get_key_handover_display(self):
        return self._format_period(
            self.key_handover_date,
            self.key_handover_year,
            self.key_handover_quarter,
        )


class ApartmentLayout(BaseModel):
    """
    Справочник планировок объектов.
    """

    name = models.CharField(
        max_length=100, unique=True, verbose_name='Планировка'
    )
    description = models.TextField(
        blank=True, null=True, verbose_name='Описание'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'apartment_layout'
        verbose_name = 'Планировка объекта'
        verbose_name_plural = 'Планировки объекта'
        ordering = ['name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name


class ApartmentDecoration(BaseModel):
    """
    Справочник типов отделки.
    """

    name = models.CharField(
        max_length=100, unique=True, verbose_name='Отделка'
    )
    description = models.TextField(
        blank=True, null=True, verbose_name='Описание'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'apartment_decoration'
        verbose_name = 'Отделка объекта'
        verbose_name_plural = 'Отделки объекта'
        ordering = ['name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name


class Property(BaseModel):
    """
    Список объектов недвижимости.
    """

    apartment_number = models.CharField(
        max_length=50, verbose_name='№ квартиры'
    )
    building = models.ForeignKey(
        RealEstateComplexBuilding,
        on_delete=models.PROTECT,
        verbose_name='Корпус',
    )
    decoration = models.ForeignKey(
        ApartmentDecoration, on_delete=models.PROTECT, verbose_name='Отделка'
    )
    layout = models.ForeignKey(
        ApartmentLayout, on_delete=models.PROTECT, verbose_name='Планировка'
    )
    area = models.DecimalField(
        max_digits=10, decimal_places=2, verbose_name='Площадь'
    )
    floor = models.IntegerField(verbose_name='Этаж')
    property_cost = models.DecimalField(
        max_digits=15, decimal_places=2, verbose_name='Стоимость объекта, руб.'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'property'
        verbose_name = 'Объект недвижимости'
        verbose_name_plural = 'Объекты недвижимости'
        ordering = ['apartment_number']

    def get_absolute_url(self):
        """
        Возвращение URL объекта.
        """
        return reverse('property:detail', kwargs={'pk': self.pk})

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        complex_name = self.building.real_estate_complex.name
        building_number = self.building.number
        return (
            f'ЖК "{complex_name}", '
            f'корпус {building_number}, '
            f'кв. {self.apartment_number}'
        )
