from django.db import models


class Property(models.Model):
    CITY_CHOICES = [
        ('Москва', 'Москва'),
        ('Санкт-Петербург', 'Санкт-Петербург'),
        ('Калининград', 'Калининград'),
    ]

    CLASS_CHOICES = [
        ('Бизнес', 'Бизнес'),
        ('Комфорт', 'Комфорт'),
        ('Комфорт+', 'Комфорт+'),
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

    def __str__(self):
        return f"{self.complex_name}, кв. {self.apartment_number}"


class MortgageCalculation(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, verbose_name='Объект')
    initial_payment_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                                  verbose_name='Первоначальный взнос, %')
    initial_payment_date = models.DateField(verbose_name='Дата первоначального взноса')
    mortgage_term = models.IntegerField(verbose_name='Срок ипотеки, годы')
    annual_rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Годовая ставка, %')
    has_grace_period = models.BooleanField(verbose_name='Наличие льготного периода')
    grace_period_term = models.IntegerField(null=True, blank=True, verbose_name='Срок льготного периода, годы')
    grace_period_rate = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True,
                                            verbose_name='Годовая ставка на срок действия льготного периода, %')

    # Новые поля
    DISCOUNT_MARKUP_CHOICES = [
        ('discount', 'Скидка'),
        ('markup', 'Удорожание'),
    ]
    discount_markup_type = models.CharField(max_length=10, choices=DISCOUNT_MARKUP_CHOICES, default='discount',
                                            verbose_name='Тип изменения цены')
    discount_markup_value = models.DecimalField(max_digits=5, decimal_places=2, default=0, verbose_name='Значение, %')
    final_property_cost = models.DecimalField(max_digits=15, decimal_places=2,
                                              verbose_name='Итоговая стоимость объекта, руб.')

    # Результаты расчета
    grace_payments_count = models.IntegerField(null=True, blank=True)
    grace_period_end_date = models.DateField(null=True, blank=True)
    grace_monthly_payment = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    loan_after_grace = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    main_payments_count = models.IntegerField(null=True, blank=True)
    mortgage_end_date = models.DateField(null=True, blank=True)
    main_monthly_payment = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total_loan_amount = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)
    total_overpayment = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Расчет от {self.timestamp.strftime('%d.%m.%Y %H:%M')}"
