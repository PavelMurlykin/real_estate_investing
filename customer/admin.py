from django.contrib import admin

from .models import Customer, CustomerCalculation


class CustomerCalculationInline(admin.TabularInline):
    model = CustomerCalculation
    extra = 0
    autocomplete_fields = ('calculation',)
    readonly_fields = ('created_at',)


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
    """Описание класса CustomerAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = (
        'id',
        'first_name',
        'last_name',
        'phone',
        'user',
        'age',
        'residence_city',
        'created_at',
        'is_active',
    )
    list_filter = (
        'is_active',
        'purchase_goal',
        'has_owned_property',
        'residence_city',
        'desired_city',
    )
    search_fields = (
        'first_name',
        'last_name',
        'phone',
        'email',
        'user__email',
    )
    autocomplete_fields = (
        'user',
        'residence_city',
        'desired_city',
        'desired_district',
        'desired_layouts',
        'preferential_programs',
    )
    ordering = ('-created_at',)
    list_editable = ('is_active',)
    inlines = (CustomerCalculationInline,)


@admin.register(CustomerCalculation)
class CustomerCalculationAdmin(admin.ModelAdmin):
    list_display = ('customer', 'calculation', 'created_at')
    list_filter = ('created_at',)
    search_fields = (
        'customer__first_name',
        'customer__last_name',
        'customer__phone',
        'calculation__property__apartment_number',
    )
    autocomplete_fields = ('customer', 'calculation')
    readonly_fields = ('created_at',)
    ordering = ('-created_at',)
