# property/admin.py
from django.contrib import admin

from .models import (
    Region, City, District, Developer, RealEstateType,
    RealEstateClass, RealEstateComplex, RealEstateComplexBuilding,
    ApartmentLayout, ApartmentDecoration, Property
)


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'region', 'is_active', 'created_at')
    list_filter = ('is_active', 'region', 'created_at')
    search_fields = ('name', 'region__name')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'is_active', 'created_at')
    list_filter = ('is_active', 'city', 'city__region', 'created_at')
    search_fields = ('name', 'city__name')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(Developer)
class DeveloperAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(RealEstateType)
class RealEstateTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(RealEstateClass)
class RealEstateClassAdmin(admin.ModelAdmin):
    list_display = ('name', 'weight', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active', 'weight')
    ordering = ('weight',)


class RealEstateComplexBuildingInline(admin.TabularInline):
    model = RealEstateComplexBuilding
    extra = 1
    fields = ('number', 'address', 'commissioning_date', 'key_handover_date', 'is_active')
    show_change_link = True


@admin.register(RealEstateComplex)
class RealEstateComplexAdmin(admin.ModelAdmin):
    list_display = (
        'name', 'developer', 'district', 'real_estate_class',
        'real_estate_type', 'is_active', 'created_at'
    )
    list_filter = (
        'is_active', 'developer', 'district', 'real_estate_class',
        'real_estate_type', 'created_at'
    )
    search_fields = ('name', 'description', 'developer__name', 'district__name')
    list_editable = ('is_active',)
    ordering = ('name',)
    inlines = (RealEstateComplexBuildingInline,)

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'developer', 'district', 'real_estate_class', 'real_estate_type'
        )


@admin.register(RealEstateComplexBuilding)
class RealEstateComplexBuildingAdmin(admin.ModelAdmin):
    list_display = (
        'number', 'real_estate_complex', 'address',
        'commissioning_date', 'key_handover_date', 'is_active'
    )
    list_filter = (
        'is_active', 'real_estate_complex', 'real_estate_complex__developer',
        'commissioning_date', 'created_at'
    )
    search_fields = ('number', 'address', 'real_estate_complex__name')
    list_editable = ('is_active',)
    ordering = ('real_estate_complex', 'number')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('real_estate_complex')


@admin.register(ApartmentLayout)
class ApartmentLayoutAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(ApartmentDecoration)
class ApartmentDecorationAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'description')
    list_editable = ('is_active',)
    ordering = ('name',)


class PropertyAdmin(admin.ModelAdmin):
    list_display = (
        'apartment_number', 'get_complex_name', 'get_building_number',
        'area', 'floor', 'property_cost', 'is_active', 'created_at'
    )
    list_filter = (
        'is_active', 'building__real_estate_complex',
        'decoration', 'layout', 'created_at'
    )
    search_fields = (
        'apartment_number', 'building__real_estate_complex__name',
        'building__number'
    )
    list_editable = ('is_active',)
    ordering = ('building__real_estate_complex', 'building', 'apartment_number')

    def get_queryset(self, request):
        return super().get_queryset(request).select_related(
            'building__real_estate_complex', 'decoration', 'layout'
        )

    def get_complex_name(self, obj):
        return obj.building.real_estate_complex.name

    get_complex_name.short_description = 'ЖК'
    get_complex_name.admin_order_field = 'building__real_estate_complex__name'

    def get_building_number(self, obj):
        return obj.building.number

    get_building_number.short_description = 'Корпус'
    get_building_number.admin_order_field = 'building__number'


admin.site.register(Property, PropertyAdmin)
