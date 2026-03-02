from django.db import models
from mortgage.models import Property


class TrenchMortgageCalculation(models.Model):
    property = models.ForeignKey(Property, on_delete=models.CASCADE, verbose_name='Объект')
    final_property_cost = models.DecimalField(max_digits=15, decimal_places=2,
                                              verbose_name='Итоговая стоимость объекта, руб.')
    initial_payment_percent = models.DecimalField(max_digits=5, decimal_places=2,
                                                  verbose_name='Первоначальный взнос, %')
    initial_payment_date = models.DateField(verbose_name='Дата первоначального взноса')
    mortgage_term = models.IntegerField(verbose_name='Срок кредита, лет')
    trench_count = models.IntegerField(verbose_name='Количество траншей')

    # Результаты расчета
    total_loan_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Сумма кредита, руб.')
    total_overpayment = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Сумма переплат, руб.')

    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Траншевый расчет от {self.timestamp.strftime('%d.%m.%Y %H:%M')}"


class Trench(models.Model):
    calculation = models.ForeignKey(TrenchMortgageCalculation, on_delete=models.CASCADE, related_name='trenches')
    trench_number = models.IntegerField(verbose_name='Номер транша')
    trench_date = models.DateField(verbose_name='Дата транша')
    trench_percent = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Сумма транша, %')
    trench_amount = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Сумма транша, руб.')
    annual_rate = models.DecimalField(max_digits=5, decimal_places=2, verbose_name='Годовая ставка, %')
    monthly_payment = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Ежемесячный платеж, руб.')
    payments_count = models.IntegerField(verbose_name='Число платежей')
    remaining_debt = models.DecimalField(max_digits=15, decimal_places=2, verbose_name='Остаток долга, руб.')

    class Meta:
        ordering = ['trench_number']