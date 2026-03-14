# mortgage/admin.py
from django.contrib import admin

from .models import MortgageCalculation


@admin.register(MortgageCalculation)
class MortgageCalculationAdmin(admin.ModelAdmin):
    """Описание класса MortgageCalculationAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = (
        'timestamp',
        'get_property',
        'final_property_cost',
        'initial_payment_percent',
        'mortgage_term',
        'annual_rate',
        'has_grace_period',
    )
    list_filter = ('timestamp', 'has_grace_period', 'discount_markup_type')
    readonly_fields = ('timestamp',)
    search_fields = ('property__complex_name', 'property__apartment_number')

    def get_property(self, obj):
        """Описание метода get_property.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            obj: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return (
            f'{obj.property.complex_name}, кв. {obj.property.apartment_number}'
        )

    get_property.short_description = 'Объект'

    def get_queryset(self, request):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            request: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return super().get_queryset(request).select_related('property')
