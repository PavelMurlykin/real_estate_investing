from django.contrib import admin
from .models import MortgageCalculation

@admin.register(MortgageCalculation)
class MortgageCalculationAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp',
        'property_cost',
        'initial_payment_percent',
        'mortgage_term',
        'annual_rate',
        'has_grace_period'
    )
    list_filter = ('timestamp', 'has_grace_period')
    readonly_fields = ('timestamp',)