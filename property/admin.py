# property/admin.py
from django.contrib import admin

from .models import (
    ApartmentDecoration,
    ApartmentLayout,
    Developer,
    Property,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateComplexMetroAvailability,
    RealEstateType,
)


@admin.register(Developer)
class DeveloperAdmin(admin.ModelAdmin):
    """Описание класса DeveloperAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(RealEstateType)
class RealEstateTypeAdmin(admin.ModelAdmin):
    """Описание класса RealEstateTypeAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(RealEstateClass)
class RealEstateClassAdmin(admin.ModelAdmin):
    """Описание класса RealEstateClassAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = ('name', 'weight', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active', 'weight')
    ordering = ('weight',)


class RealEstateComplexBuildingInline(admin.TabularInline):
    """Описание класса RealEstateComplexBuildingInline.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = RealEstateComplexBuilding
    extra = 1
    fields = (
        'number',
        'address',
        'commissioning_date',
        'key_handover_date',
        'is_active',
    )
    show_change_link = True


class RealEstateComplexMetroAvailabilityInline(admin.TabularInline):
    """Inline for metro availability near a complex."""

    model = RealEstateComplexMetroAvailability
    extra = 1
    fields = ('metro', 'walking_time_minutes', 'is_active')
    show_change_link = True


@admin.register(RealEstateComplex)
class RealEstateComplexAdmin(admin.ModelAdmin):
    """Описание класса RealEstateComplexAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = (
        'name',
        'developer',
        'district',
        'real_estate_class',
        'real_estate_type',
        'is_active',
        'created_at',
    )
    list_filter = (
        'is_active',
        'developer',
        'district',
        'real_estate_class',
        'real_estate_type',
        'created_at',
    )
    search_fields = (
        'name',
        'description',
        'developer__name',
        'district__name',
    )
    list_editable = ('is_active',)
    ordering = ('name',)
    inlines = (
        RealEstateComplexBuildingInline,
        RealEstateComplexMetroAvailabilityInline,
    )

    def get_queryset(self, request):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            request: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return (
            super()
            .get_queryset(request)
            .select_related(
                'developer',
                'district',
                'real_estate_class',
                'real_estate_type',
            )
        )


@admin.register(RealEstateComplexBuilding)
class RealEstateComplexBuildingAdmin(admin.ModelAdmin):
    """Описание класса RealEstateComplexBuildingAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = (
        'number',
        'real_estate_complex',
        'address',
        'commissioning_date',
        'key_handover_date',
        'is_active',
    )
    list_filter = (
        'is_active',
        'real_estate_complex',
        'real_estate_complex__developer',
        'commissioning_date',
        'created_at',
    )
    search_fields = ('number', 'address', 'real_estate_complex__name')
    list_editable = ('is_active',)
    ordering = ('real_estate_complex', 'number')

    def get_queryset(self, request):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            request: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return (
            super().get_queryset(request).select_related('real_estate_complex')
        )


@admin.register(RealEstateComplexMetroAvailability)
class RealEstateComplexMetroAvailabilityAdmin(admin.ModelAdmin):
    """Admin for metro availability near complexes."""

    list_display = (
        'real_estate_complex',
        'metro',
        'walking_time_minutes',
        'is_active',
    )
    list_filter = (
        'is_active',
        'metro__metro_line__city',
        'metro__metro_line',
        'created_at',
    )
    search_fields = (
        'real_estate_complex__name',
        'metro__station',
        'metro__metro_line__line',
    )
    list_editable = ('is_active',)
    ordering = (
        'real_estate_complex__name',
        'walking_time_minutes',
        'metro__station',
    )

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                'real_estate_complex',
                'metro__metro_line__city',
            )
        )


@admin.register(ApartmentLayout)
class ApartmentLayoutAdmin(admin.ModelAdmin):
    """Описание класса ApartmentLayoutAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(ApartmentDecoration)
class ApartmentDecorationAdmin(admin.ModelAdmin):
    """Описание класса ApartmentDecorationAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    ordering = ('name',)


class PropertyAdmin(admin.ModelAdmin):
    """Описание класса PropertyAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = (
        'apartment_number',
        'get_complex_name',
        'get_building_number',
        'area',
        'floor',
        'property_cost',
        'is_active',
        'created_at',
    )
    list_filter = (
        'is_active',
        'building__real_estate_complex',
        'decoration',
        'layout',
        'created_at',
    )
    search_fields = (
        'apartment_number',
        'building__real_estate_complex__name',
        'building__number',
    )
    list_editable = ('is_active',)
    ordering = (
        'building__real_estate_complex',
        'building',
        'apartment_number',
    )

    def get_queryset(self, request):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            request: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return (
            super()
            .get_queryset(request)
            .select_related(
                'building__real_estate_complex', 'decoration', 'layout'
            )
        )

    def get_complex_name(self, obj):
        """Описание метода get_complex_name.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            obj: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return obj.building.real_estate_complex.name

    get_complex_name.short_description = 'ЖК'
    get_complex_name.admin_order_field = 'building__real_estate_complex__name'

    def get_building_number(self, obj):
        """Описание метода get_building_number.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            obj: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return obj.building.number

    get_building_number.short_description = 'Корпус'
    get_building_number.admin_order_field = 'building__number'


admin.site.register(Property, PropertyAdmin)
