from django.contrib import admin

from .models import Bank, BankProgram, KeyRate, MortgageProgram


@admin.register(Bank)
class BankAdmin(admin.ModelAdmin):
    """Описание класса BankAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = (
        'name',
        'interest_rate',
        'salary_client_discount',
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

    list_display = ('name', 'is_preferential', 'is_active', 'created_at')
    list_filter = ('is_preferential', 'is_active', 'created_at')
    search_fields = ('name', 'condition')
    ordering = ('name',)


@admin.register(BankProgram)
class BankProgramAdmin(admin.ModelAdmin):
    """Описание класса BankProgramAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = ('bank', 'mortgage_program', 'is_active', 'created_at')
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
