from django.db import models

from core.models import BaseModel


class Region(BaseModel):
    """
    Справочник регионов.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Регион')
    code = models.CharField(max_length=10, unique=True, verbose_name='Код региона')

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """
        db_table = 'region'
        verbose_name = 'Регион'
        verbose_name_plural = 'Регионы'
        ordering = ['name']

    def __str__(self):
        return self.name


class City(BaseModel):
    """
    Справочник городов.
    """
    name = models.CharField(max_length=100, verbose_name='Город')
    region = models.ForeignKey(Region, on_delete=models.PROTECT, verbose_name='Регион')

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
        return self.name


class District(BaseModel):
    """
    Справочник районов городов.
    """
    name = models.CharField(max_length=100, verbose_name='Район')
    city = models.ForeignKey(City, on_delete=models.PROTECT, verbose_name='Город')

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
        return self.name
