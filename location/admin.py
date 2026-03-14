from django.contrib import admin

from .models import City, District, Region


@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    """Описание класса RegionAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = ('name', 'code', 'is_active', 'created_at')
    list_filter = ('is_active', 'created_at')
    search_fields = ('name', 'code')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    """Описание класса CityAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = ('name', 'region', 'is_active', 'created_at')
    list_filter = ('is_active', 'region', 'created_at')
    search_fields = ('name', 'region__name')
    list_editable = ('is_active',)
    ordering = ('name',)


@admin.register(District)
class DistrictAdmin(admin.ModelAdmin):
    """Описание класса DistrictAdmin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    list_display = ('name', 'city', 'is_active', 'created_at')
    list_filter = ('is_active', 'city', 'city__region', 'created_at')
    search_fields = ('name', 'city__name')
    list_editable = ('is_active',)
    ordering = ('name',)
