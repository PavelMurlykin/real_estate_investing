from django.db import models


class Region(models.Model):
    """
    Справочник регионов.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Регион')
    code = models.CharField(max_length=10, unique=True, verbose_name='Код региона')

    class Meta:
        """
        Метаданные таблицы.
        """
        db_table = 'region'
        verbose_name = 'Регион'
        verbose_name_plural = 'Регионы'
        ordering = ['name']

    def __str__(self):
        return self.name


class City(models.Model):
    """
    Справочник городов.
    """
    name = models.CharField(max_length=100, verbose_name='Город')
    region = models.ForeignKey(Region, on_delete=models.PROTECT, verbose_name='Регион')

    class Meta:
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


class District(models.Model):
    """
    Справочник районов городов.
    """
    name = models.CharField(max_length=100, verbose_name='Район')
    city = models.ForeignKey(City, on_delete=models.PROTECT, verbose_name='Город')

    class Meta:
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


class Developer(models.Model):
    """
    Справочник застройщиков.
    """
    name = models.CharField(max_length=255, unique=True, verbose_name='Застройщик')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')

    class Meta:
        """
        Метаданные таблицы.
        """
        db_table = 'developer'
        verbose_name = 'Застройщик'
        verbose_name_plural = 'Застройщики'
        ordering = ['name']

    def __str__(self):
        return self.name


class RealEstateType(models.Model):
    """
    Справочник типов недвижимости.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Тип недвижимости')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')

    class Meta:
        """
        Метаданные таблицы.
        """
        db_table = 'real_estate_type'
        verbose_name = 'Тип недвижимости'
        verbose_name_plural = 'Типы недвижимости'
        ordering = ['name']

    def __str__(self):
        return self.name


class RealEstateClass(models.Model):
    """
    Справочник типов недвижимости.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Класс ЖК')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')
    weight = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Коэффициент класса')

    class Meta:
        """
        Метаданные таблицы.
        """
        db_table = 'real_estate_class'
        verbose_name = 'Класс ЖК'
        verbose_name_plural = 'Классы ЖК'
        ordering = ['weight']

    def __str__(self):
        return self.name


class RealEstateComplex(models.Model):
    """
    Справочник ЖК.
    """
    name = models.CharField(max_length=255, verbose_name='ЖК')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')
    map_link = models.TextField(blank=True, null=True, verbose_name='Ссылка на картах')
    presentation_link = models.TextField(blank=True, null=True, verbose_name='Ссылка на презентацию')

    developer = models.ForeignKey(Developer, on_delete=models.PROTECT, verbose_name='Застройщик')
    district = models.ForeignKey(District, on_delete=models.PROTECT, verbose_name='Район')
    real_estate_class = models.ForeignKey(RealEstateClass, on_delete=models.PROTECT, verbose_name='Класс ЖК')
    real_estate_type = models.ForeignKey(RealEstateType, on_delete=models.PROTECT, verbose_name='Тип недвижимости')

    class Meta:
        """
        Метаданные таблицы.
        """
        db_table = 'real_estate_complex'
        verbose_name = 'ЖК'
        verbose_name_plural = 'ЖК'
        unique_together = ('name', 'developer')
        ordering = ['name']

    def __str__(self):
        return self.name


class RealEstateComplexBuilding(models.Model):
    """
    Список корпусов ЖК.
    """
    number = models.CharField(max_length=100, verbose_name='Корпус')
    address = models.CharField(null=True, max_length=255, verbose_name='Адрес')
    commissioning_date = models.DateField(null=True, verbose_name='Дата ввода в эксплуатацию')
    key_handover_date = models.DateField(null=True, verbose_name='Дата выдачи ключей')

    real_estate_complex = models.ForeignKey(RealEstateComplex, on_delete=models.PROTECT, verbose_name='ЖК')

    class Meta:
        """
        Метаданные таблицы.
        """
        db_table = 'real_estate_complex_building'
        verbose_name = 'Корпус ЖК'
        verbose_name_plural = 'Корпуса ЖК'
        unique_together = ('number', 'real_estate_complex')
        ordering = ['number']

    def __str__(self):
        return self.number


class ApartmentLayout(models.Model):
    """
    Справочник планировок объектов.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Планировка')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')

    class Meta:
        """
        Метаданные таблицы.
        """
        db_table = 'apartment_layout'
        verbose_name = 'Планировка объекта'
        verbose_name_plural = 'Планировки объекта'
        ordering = ['name']

    def __str__(self):
        return self.name


class ApartmentDecoration(models.Model):
    """
    Справочник типов отделки.
    """
    name = models.CharField(max_length=100, unique=True, verbose_name='Отделка')
    description = models.TextField(blank=True, null=True, verbose_name='Описание')

    class Meta:
        """
        Метаданные таблицы.
        """
        db_table = 'apartment_decoration'
        verbose_name = 'Отделка объекта'
        verbose_name_plural = 'Отделки объекта'
        ordering = ['name']

    def __str__(self):
        return self.name


class Property(models.Model):
    """
    Список объектов недвижимости.
    """

    apartment_number = models.CharField(max_length=50, verbose_name='№ квартиры')
    building = models.ForeignKey(RealEstateComplexBuilding, on_delete=models.PROTECT, verbose_name='Корпус')
    decoration = models.ForeignKey(ApartmentDecoration, on_delete=models.PROTECT, verbose_name='Отделка')
    layout = models.ForeignKey(ApartmentLayout, on_delete=models.PROTECT, verbose_name='Планировка')
    area = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Площадь')
    floor = models.IntegerField(verbose_name='Этаж')
    property_cost = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Стоимость объекта, руб.')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        """
        Метаданные таблицы.
        """
        db_table = 'property'
        verbose_name = 'Объект недвижимости'
        verbose_name_plural = 'Объекты недвижимости'
        ordering = ['apartment_number']

    def __str__(self):
        return f'ЖК "{self.building.real_estate_complex.name}", корпус {self.building.number}, кв. {self.apartment_number}'
