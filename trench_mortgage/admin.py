from django.contrib import admin

from .models import TrenchMortgageCalculation


@admin.register(TrenchMortgageCalculation)
class TrenchMortgageCalculationAdmin(admin.ModelAdmin):
    """Admin for saved trench mortgage calculations."""

    list_display = (
        'timestamp',
        'user',
        'property',
        'final_property_cost',
        'initial_payment_percent',
        'mortgage_term',
        'annual_rate',
        'trench_count',
    )
    list_filter = ('timestamp', 'user')
    readonly_fields = ('timestamp',)
    search_fields = (
        'property__building__real_estate_complex__name',
        'property__apartment_number',
    )

    def get_queryset(self, request):
        """Return trench calculations with related objects loaded."""
        return super().get_queryset(request).select_related(
            'user',
            'property',
            'property__building',
            'property__building__real_estate_complex',
        )
