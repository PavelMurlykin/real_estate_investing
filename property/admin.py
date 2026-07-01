# property/admin.py
from django.contrib import admin

from .models import (
    ApartmentDecoration,
    ApartmentLayout,
    CompanyGroup,
    Developer,
    DeveloperRegion,
    Property,
    PropertyWindowView,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateComplexMetroAvailability,
    RealEstateType,
    TransportAccessibilityType,
    WindowView,
)


@admin.register(CompanyGroup)
class CompanyGroupAdmin(admin.ModelAdmin):
    """Admin for company group dictionary entries."""

    list_display = ('name',)
    search_fields = ('name',)
    ordering = ('name',)


class DeveloperRegionInline(admin.TabularInline):
    """Inline for developer regions."""

    model = DeveloperRegion
    extra = 1
    fields = ('region', 'is_active')
    show_change_link = True


@admin.register(DeveloperRegion)
class DeveloperRegionAdmin(admin.ModelAdmin):
    """Admin for developer region links."""

    list_display = (
        'developer',
        'region',
        'is_active',
        'created_at',
    )
    list_filter = ('developer', 'region', 'is_active', 'created_at')
    search_fields = ('developer__name', 'region__name')
    ordering = ('developer__name', 'region__name')

    def get_queryset(self, request):
        """Return developer region links with related objects loaded."""
        return super().get_queryset(request).select_related(
            'developer',
            'region',
        )


@admin.register(Developer)
class DeveloperAdmin(admin.ModelAdmin):
    """Описание класса DeveloperAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = (
        'name',
        'company_group',
        'get_region_names',
        'taxpayer_identification_number',
        'tax_registration_reason_code',
        'primary_state_registration_number',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'company_group', 'regions', 'created_at')
    search_fields = (
        'name',
        'company_group__name',
        'regions__name',
        'legal_address',
        'actual_address',
        'taxpayer_identification_number',
        'tax_registration_reason_code',
        'primary_state_registration_number',
        'description',
    )
    list_editable = ('is_active',)
    ordering = ('name',)
    inlines = (DeveloperRegionInline,)

    def get_queryset(self, request):
        """Return developers with company groups loaded."""
        return (
            super()
            .get_queryset(request)
            .select_related('company_group')
            .prefetch_related('regions')
        )

    @admin.display(description='Регионы')
    def get_region_names(self, obj):
        """Return a comma-separated list of developer regions."""
        region_names = [region.name for region in obj.regions.all()]
        if not region_names:
            return '-'
        return ', '.join(region_names)


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
        'commissioning_year',
        'commissioning_quarter',
        'key_handover_date',
        'key_handover_year',
        'key_handover_quarter',
        'is_active',
    )
    show_change_link = True


class RealEstateComplexMetroAvailabilityInline(admin.TabularInline):
    """Inline for metro availability near a complex."""

    model = RealEstateComplexMetroAvailability
    extra = 1
    fields = (
        'metro',
        'transport_accessibility_type',
        'walking_time_minutes',
        'is_active',
    )
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
        'commissioning_period',
        'key_handover_period',
        'is_active',
    )
    list_filter = (
        'is_active',
        'real_estate_complex',
        'real_estate_complex__developer',
        'commissioning_date',
        'commissioning_year',
        'commissioning_quarter',
        'key_handover_year',
        'key_handover_quarter',
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

    @admin.display(description='Ввод в эксплуатацию')
    def commissioning_period(self, obj):
        return obj.get_commissioning_display() or '-'

    @admin.display(description='Выдача ключей')
    def key_handover_period(self, obj):
        return obj.get_key_handover_display() or '-'


@admin.register(RealEstateComplexMetroAvailability)
class RealEstateComplexMetroAvailabilityAdmin(admin.ModelAdmin):
    """Admin for metro availability near complexes."""

    list_display = (
        'real_estate_complex',
        'metro',
        'transport_accessibility_type',
        'walking_time_minutes',
        'is_active',
    )
    list_filter = (
        'is_active',
        'transport_accessibility_type',
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
        'transport_accessibility_type_id',
        'walking_time_minutes',
        'metro__station',
    )

    def get_queryset(self, request):
        """Return metro availability rows with related dictionaries loaded."""
        return (
            super()
            .get_queryset(request)
            .select_related(
                'real_estate_complex',
                'metro__metro_line__city',
                'transport_accessibility_type',
            )
        )


@admin.register(TransportAccessibilityType)
class TransportAccessibilityTypeAdmin(admin.ModelAdmin):
    """Admin for transport accessibility type dictionary."""

    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    ordering = ('id',)


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


@admin.register(WindowView)
class WindowViewAdmin(admin.ModelAdmin):
    """Admin for property window view dictionary entries."""

    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    ordering = ('name',)


class PropertyWindowViewInline(admin.TabularInline):
    """Inline for property window view text values."""

    model = PropertyWindowView
    extra = 1
    fields = ('window_view', 'is_active')


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
        'window_views',
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
    inlines = (PropertyWindowViewInline,)

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
            .prefetch_related('window_views')
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
