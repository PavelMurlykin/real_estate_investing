from django.contrib import admin

from .models import MortgageCalculation, Property


@admin.register(Property)
class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        'developer',
        'city',
        'complex_name',
        'complex_class',
        'building',
        'apartment_number',
        'property_cost'
    )
    list_filter = ('city', 'complex_class')
    search_fields = ('complex_name', 'developer')


@admin.register(MortgageCalculation)
class MortgageCalculationAdmin(admin.ModelAdmin):
    list_display = (
        'timestamp',
        'get_property_cost',
        'initial_payment_percent',
        'mortgage_term',
        'annual_rate',
        'has_grace_period'
    )
    list_filter = ('timestamp', 'has_grace_period')
    readonly_fields = ('timestamp',)

    def get_property_cost(self, obj):
        return obj.property.property_cost

    get_property_cost.short_description = 'Стоимость объекта'

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('property')
