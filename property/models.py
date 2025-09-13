from django.db import models

class Property(models.Model):
    CITY_CHOICES = [
        ('Москва', 'Москва'),
        ('Санкт-Петербург', 'Санкт-Петербург'),
        ('Калининград', 'Калининград'),
    ]

    CLASS_CHOICES = [
        ('Комфорт', 'Комфорт'),
        ('Комфорт+', 'Комфорт+'),
        ('Бизнес', 'Бизнес'),
        ('Элит', 'Элит'),
    ]

    developer = models.CharField(max_length=255, verbose_name='Застройщик')
    city = models.CharField(max_length=50, choices=CITY_CHOICES, verbose_name='Город')
    complex_name = models.CharField(max_length=255, verbose_name='Название ЖК')
    complex_class = models.CharField(max_length=50, choices=CLASS_CHOICES, verbose_name='Класс ЖК')
    building = models.CharField(max_length=50, verbose_name='Корпус')
    apartment_number = models.CharField(max_length=50, verbose_name='№ квартиры')
    layout = models.CharField(max_length=255, verbose_name='Планировка')
    area = models.DecimalField(max_digits=10, decimal_places=2, verbose_name='Площадь')
    floor = models.IntegerField(verbose_name='Этаж')
    property_cost = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Стоимость объекта, руб.')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Дата обновления')

    class Meta:
        verbose_name = 'Объект недвижимости'
        verbose_name_plural = 'Объекты недвижимости'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.complex_name}, кв. {self.apartment_number}"