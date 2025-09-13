from django.contrib import admin
from .models import MortgageCalculation


@admin.register(MortgageCalculation)
class MortgageCalculationAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp',
        'get_property',
        'final_property_cost',
        'initial_payment_percent',
        'mortgage_term',
        'annual_rate',
        'has_grace_period'
    )
    list_filter = ('timestamp', 'has_grace_period', 'discount_markup_type')
    readonly_fields = ('timestamp',)
    search_fields = ('property__complex_name', 'property__apartment_number')

    def get_property(self, obj):
        return f"{obj.property.complex_name}, кв. {obj.property.apartment_number}"

    get_property.short_description = 'Объект'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('property')