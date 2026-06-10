from django.contrib import admin

from .models import (
    Bank,
    BankProgram,
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
        'interest_rate',
        'salary_client_discount',
        'maximum_loan_term_years',
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

    list_display = (
        'mortgage_program',
        'region',
        'credit_limit',
        'is_active',
        'created_at',
    )
    list_filter = (
        'mortgage_program',
        'region',
        'is_active',
        'created_at',
    )
    search_fields = ('mortgage_program__name', 'region__name')
    ordering = ('mortgage_program__name', 'region__name')


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
