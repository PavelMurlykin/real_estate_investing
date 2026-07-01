# property/models.py
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse

from core.models import BaseModel
from location.models import District, Metro, Region

from .validators import validate_property_image_upload

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
    company_group = models.ForeignKey(
        'CompanyGroup',
        on_delete=models.PROTECT,
        blank=True,
        null=True,
        related_name='developers',
        verbose_name='Группа компаний',
    )
    regions = models.ManyToManyField(
        Region,
        through='DeveloperRegion',
        related_name='developers',
        blank=True,
        verbose_name='Регионы',
    )
    legal_address = models.TextField(
        blank=True, null=True, verbose_name='Юридический адрес'
    )
    actual_address = models.TextField(
        blank=True, null=True, verbose_name='Фактический адрес'
    )
    taxpayer_identification_number = models.CharField(
        max_length=12, blank=True, null=True, verbose_name='ИНН'
    )
    tax_registration_reason_code = models.CharField(
        max_length=9, blank=True, null=True, verbose_name='КПП'
    )
    primary_state_registration_number = models.CharField(
        max_length=15, blank=True, null=True, verbose_name='ОГРН'
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
        """Возвращает название застройщика."""
        return self.name


class DeveloperRegion(BaseModel):
    """Регион работы застройщика."""

    developer = models.ForeignKey(
        Developer,
        on_delete=models.CASCADE,
        related_name='region_links',
        verbose_name='Застройщик',
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name='developer_links',
        verbose_name='Регион',
    )

    class Meta(BaseModel.Meta):
        """Метаданные связи застройщика и региона."""

        db_table = 'developer_region'
        verbose_name = 'Регион застройщика'
        verbose_name_plural = 'Регионы застройщиков'
        ordering = ['developer__name', 'region__name']
        constraints = [
            models.UniqueConstraint(
                fields=['developer', 'region'],
                name='unique_developer_region',
            ),
        ]

    def __str__(self):
        """Возвращает строковое представление связи застройщика и региона."""
        return f'{self.developer} - {self.region}'


class CompanyGroup(models.Model):
    """
    Справочник групп компаний.
    """

    name = models.CharField(
        max_length=255, unique=True, verbose_name='Группа компаний'
    )

    class Meta:
        """
        Метаданные таблицы.
        """

        db_table = 'company_group'
        verbose_name = 'Группа компаний'
        verbose_name_plural = 'Группы компаний'
        ordering = ['name']

    def __str__(self):
        """Возвращает название группы компаний."""
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
        """Возвращает название типа недвижимости."""
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
        """Возвращает название класса ЖК."""
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
    investment_potential = models.TextField(
        blank=True,
        null=True,
        verbose_name='Инвестиционный потенциал',
    )
    photo = models.ImageField(
        upload_to='property/complexes/',
        blank=True,
        null=True,
        validators=[validate_property_image_upload],
        verbose_name='Фото ЖК',
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
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'developer'],
                name='unique_complex_name_developer',
            ),
        ]

    def get_photo_filename(self):
        """Return the saved complex photo filename."""
        if not self.photo:
            return ''
        return self.photo.name.rsplit('/', 1)[-1]

    def __str__(self):
        """Возвращает название ЖК."""
        return self.name


class TransportAccessibilityType(BaseModel):
    """
    Справочник типов транспортной доступности.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Тип транспортной доступности',
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Описание',
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'transport_accessibility_type'
        verbose_name = 'Тип транспортной доступности'
        verbose_name_plural = 'Типы транспортной доступности'
        ordering = ['id']

    def __str__(self):
        """Возвращает название типа транспортной доступности."""
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
    transport_accessibility_type = models.ForeignKey(
        TransportAccessibilityType,
        on_delete=models.PROTECT,
        verbose_name='Способ',
    )
    walking_time_minutes = models.PositiveSmallIntegerField(
        verbose_name='Время, мин'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'real_estate_complex_metro_availability'
        verbose_name = 'Доступность метро ЖК'
        verbose_name_plural = 'Доступность метро ЖК'
        ordering = ['walking_time_minutes', 'metro__station']
        constraints = [
            models.UniqueConstraint(
                fields=['real_estate_complex', 'metro'],
                name='unique_complex_metro_station',
            ),
        ]

    def __str__(self):
        """Возвращает строковое представление доступности метро."""
        return (
            f'{self.real_estate_complex}: {self.metro} '
            f'({self.transport_accessibility_type}, '
            f'{self.walking_time_minutes} мин.)'
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
        ordering = ['number']
        indexes = [
            models.Index(fields=['number'], name='building_number_idx'),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['number', 'real_estate_complex'],
                name='unique_complex_building_number',
            ),
        ]

    def __str__(self):
        """Возвращает номер корпуса."""
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
        """Возвращает название планировки."""
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
        """Возвращает название отделки."""
        return self.name


class WindowView(BaseModel):
    """Dictionary entry for a property window view."""

    name = models.CharField(
        max_length=100,
        unique=True,
        verbose_name='Вид из окна',
    )
    description = models.TextField(
        blank=True,
        null=True,
        verbose_name='Описание',
    )

    class Meta(BaseModel.Meta):
        """Window view table metadata."""

        db_table = 'window_view'
        verbose_name = 'Вид из окна'
        verbose_name_plural = 'Виды из окна'
        ordering = ['name']

    def __str__(self):
        """Return the window view name."""
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
    layout_image = models.ImageField(
        upload_to='property/layouts/',
        blank=True,
        null=True,
        validators=[validate_property_image_upload],
        verbose_name='Планировка',
    )
    floor_plan_image = models.ImageField(
        upload_to='property/floor_plans/',
        blank=True,
        null=True,
        validators=[validate_property_image_upload],
        verbose_name='План этажа',
    )
    window_view_image = models.ImageField(
        upload_to='property/window_views/',
        blank=True,
        null=True,
        validators=[validate_property_image_upload],
        verbose_name='Вид из окна',
    )
    window_views = models.ManyToManyField(
        WindowView,
        through='PropertyWindowView',
        related_name='properties',
        blank=True,
        verbose_name='Виды из окна',
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'property'
        verbose_name = 'Объект недвижимости'
        verbose_name_plural = 'Объекты недвижимости'
        ordering = ['apartment_number']
        indexes = [
            models.Index(
                fields=['apartment_number'],
                name='property_apartment_num_idx',
            ),
        ]

    def get_absolute_url(self):
        """
        Возвращение URL объекта.
        """
        return reverse('property:detail', kwargs={'pk': self.pk})

    def _get_image_filename(self, image_field):
        """Return a saved image filename without its upload directory."""
        if not image_field:
            return ''
        return image_field.name.rsplit('/', 1)[-1]

    def get_layout_image_filename(self):
        """Return the saved layout image filename."""
        return self._get_image_filename(self.layout_image)

    def get_floor_plan_image_filename(self):
        """Return the saved floor plan image filename."""
        return self._get_image_filename(self.floor_plan_image)

    def get_window_view_image_filename(self):
        """Return the saved window view image filename."""
        return self._get_image_filename(self.window_view_image)

    def __str__(self):
        """Возвращает адресное описание объекта недвижимости."""
        complex_name = self.building.real_estate_complex.name
        building_number = self.building.number
        return (
            f'ЖК "{complex_name}", '
            f'корпус {building_number}, '
            f'кв. {self.apartment_number}'
        )


class PropertyWindowView(BaseModel):
    """Text window view selected for a property."""

    property = models.ForeignKey(
        Property,
        on_delete=models.CASCADE,
        verbose_name='Объект недвижимости',
    )
    window_view = models.ForeignKey(
        WindowView,
        on_delete=models.PROTECT,
        verbose_name='Вид из окна',
    )

    class Meta(BaseModel.Meta):
        """Property to window view link table metadata."""

        db_table = 'property_window_view'
        verbose_name = 'Вид из окна объекта недвижимости'
        verbose_name_plural = 'Виды из окна объектов недвижимости'
        ordering = ['property', 'window_view__name']
        constraints = [
            models.UniqueConstraint(
                fields=['property', 'window_view'],
                name='unique_property_window_view',
            ),
        ]

    def __str__(self):
        """Return a readable property window view link."""
        return f'{self.property}: {self.window_view}'
