from django.core.validators import RegexValidator
from django.db import models

from core.models import BaseModel


class Region(BaseModel):
    """
    Справочник регионов.
    """

    name = models.CharField(max_length=100, unique=True, verbose_name='Регион')
    code = models.CharField(
        max_length=10, unique=True, verbose_name='Код региона'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'region'
        verbose_name = 'Регион'
        verbose_name_plural = 'Регионы'
        ordering = ['name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name


class City(BaseModel):
    """
    Справочник городов.
    """

    name = models.CharField(max_length=100, verbose_name='Город')
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, verbose_name='Регион'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'city'
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        unique_together = ('name', 'region')
        ordering = ['name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name


class District(BaseModel):
    """
    Справочник районов городов.
    """

    name = models.CharField(max_length=100, verbose_name='Район')
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, verbose_name='Город'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'district'
        verbose_name = 'Район'
        verbose_name_plural = 'Районы'
        unique_together = ('name', 'city')
        ordering = ['name']

    def __str__(self):
        """Описание метода __str__.

        Возвращает строковое представление объекта для отображения.

        Возвращает:
            str: Человекочитаемое представление текущего объекта.
        """
        return self.name


class MetroLine(BaseModel):
    """
    Справочник линий метро.
    """

    line = models.CharField(max_length=100, verbose_name='Линия')
    line_color = models.CharField(
        max_length=7,
        verbose_name='Цвет линии (RGB)',
        help_text='Код цвета линии в формате #RRGGBB.',
        validators=[
            RegexValidator(
                r'^#[0-9A-Fa-f]{6}$',
                'Введите цвет в формате #RRGGBB.',
            )
        ],
    )
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, verbose_name='Город'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'metro_line'
        verbose_name = 'Линия метро'
        verbose_name_plural = 'Линии метро'
        unique_together = ('line', 'city')
        ordering = ['city__name', 'line']

    def __str__(self):
        """Возвращает строковое представление линии метро."""
        return f'{self.line} ({self.city})'


class Metro(BaseModel):
    """
    Справочник станций метро.
    """

    station = models.CharField(max_length=100, verbose_name='Станция')
    metro_line = models.ForeignKey(
        MetroLine, on_delete=models.PROTECT, verbose_name='Линия метро'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'metro'
        verbose_name = 'Метро'
        verbose_name_plural = 'Метро'
        unique_together = ('station', 'metro_line')
        ordering = ['metro_line__city__name', 'metro_line__line', 'station']

    def __str__(self):
        """Возвращает строковое представление станции метро."""
        return f'{self.station} ({self.metro_line.line})'
