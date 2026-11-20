from django.contrib import admin
from django.db import transaction

from location.catalog_service import lock_location_catalog

from .forms import RegionalCreditLimitForm
from .limit_regions import limit_region_labels
from .models import (
    Bank,
    BankProgram,
    DeveloperMortgageProgram,
    KeyRate,
    MortgageProgram,
    MortgageProgramRegionalCreditLimit,
)


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    """Описание класса BankAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = (
        'name',
        'logo_url',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'created_at')
    search_fields = ('name',)
    ordering = ('name',)


@admin.register(MortgageProgram)
class MortgageProgramAdmin(admin.ModelAdmin):
    """Описание класса MortgageProgramAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = (
        'name',
        'is_preferential',
        'credit_limit',
        'is_active',
        'created_at',
    )
    list_filter = (
        'is_preferential',
        'is_active',
        'created_at',
    )
    search_fields = ('name', 'condition')
    ordering = ('name',)


@admin.register(MortgageProgramRegionalCreditLimit)
class MortgageProgramRegionalCreditLimitAdmin(admin.ModelAdmin):
    """Администрирование региональных лимитов ипотечных программ."""

    form = RegionalCreditLimitForm
    autocomplete_fields = ('region_location',)
    list_display = (
        'mortgage_program',
        'get_region_name',
        'credit_limit',
        'is_active',
        'created_at',
    )
    list_filter = (
        'mortgage_program',
        'region_location',
        'is_active',
        'created_at',
    )
    search_fields = ('mortgage_program__name', 'region_location__name', 'legacy_region_name')
    ordering = ('mortgage_program__name', 'region_location__name')

    @transaction.atomic
    def changeform_view(self, request, object_id=None, form_url='', extra_context=None):
        """Keep alias resolution consistent throughout the save."""
        if request.method == 'POST':
            lock_location_catalog()
        return super().changeform_view(request, object_id, form_url, extra_context)

    def get_queryset(self, request):
        """Include the old label without querying Region for each row."""
        return limit_region_labels(super().get_queryset(request)).select_related('mortgage_program')

    @admin.display(description='Регион', ordering='display_region_name')
    def get_region_name(self, limit):
        """Show the effective region in the editor's list."""
        return limit.display_region_name


@admin.register(BankProgram)
class BankProgramAdmin(admin.ModelAdmin):
    """Описание класса BankProgramAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = (
        'bank',
        'mortgage_program',
        'interest_rate',
        'minimum_initial_payment_percent',
        'maximum_loan_term_years',
        'is_active',
        'created_at',
    )
    list_filter = ('bank', 'mortgage_program', 'is_active', 'created_at')
    search_fields = ('bank__name', 'mortgage_program__name')
    ordering = ('bank__name', 'mortgage_program__name')


@admin.register(DeveloperMortgageProgram)
class DeveloperMortgageProgramAdmin(admin.ModelAdmin):
    """Администрирование ипотечных программ застройщиков."""

    list_display = (
        'company_group',
        'real_estate_complex',
        'bank',
        'mortgage_program',
        'price_increase_percent',
        'grace_period_months',
        'grace_period_interest_rate',
        'minimum_initial_payment_percent',
        'interest_rate',
        'maximum_loan_term_years',
        'maximum_loan_amount',
        'rate_discount_percent',
        'is_active',
    )
    list_filter = (
        'company_group',
        'bank',
        'mortgage_program',
        'is_active',
    )
    search_fields = (
        'company_group__name',
        'real_estate_complex__name',
        'bank__name',
        'mortgage_program__name',
    )
    list_select_related = (
        'company_group',
        'real_estate_complex',
        'bank',
        'mortgage_program',
    )
    autocomplete_fields = (
        'company_group',
        'real_estate_complex',
        'bank',
        'mortgage_program',
    )
    ordering = (
        'company_group__name',
        'real_estate_complex__name',
        'bank__name',
        'mortgage_program__name',
    )


@admin.register(KeyRate)
class KeyRateAdmin(admin.ModelAdmin):
    """Описание класса KeyRateAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = ('meeting_date', 'key_rate', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('meeting_date',)
    ordering = ('-meeting_date',)
