from django.db import models


class MortgageCalculation(models.Model):
    timestamp = models.DateTimeField(auto_now_add=True)
    property_cost = models.DecimalField(max_digits=15, decimal_places=2)
    initial_payment_percent = models.DecimalField(
        max_digits=5, decimal_places=2)
    initial_payment_date = models.DateField()
    mortgage_term = models.IntegerField()
    annual_rate = models.DecimalField(max_digits=5, decimal_places=2)
    has_grace_period = models.BooleanField()
    grace_period_term = models.IntegerField(null=True, blank=True)
    grace_period_rate = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True)

    # Results
    grace_payments_count = models.IntegerField(null=True, blank=True)
    grace_period_end_date = models.DateField(null=True, blank=True)
    grace_monthly_payment = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True)
    loan_after_grace = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True)
    main_payments_count = models.IntegerField(null=True, blank=True)
    mortgage_end_date = models.DateField(null=True, blank=True)
    main_monthly_payment = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True)
    total_loan_amount = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True)
    total_overpayment = models.DecimalField(
        max_digits=15, decimal_places=2, null=True, blank=True)

    def __str__(self):
        return f"Расчет от {self.timestamp.strftime('%d.%m.%Y %H:%M')}"
