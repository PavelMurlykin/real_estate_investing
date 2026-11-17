from django.contrib import admin

from .models import City, District, Location, Metro, MetroLine, MetroSystem, Region
from .metro_forms import MetroForm, MetroLineForm, MetroSystemForm


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


@admin.register(Metro)
class MetroAdmin(admin.ModelAdmin):
    """Администрирование справочника станций метро."""

    form = MetroForm
    autocomplete_fields = ('location',)
    list_select_related = ('metro_line__system', 'location')

    list_display = (
        'station',
        'metro_line',
        'is_active',
        'created_at',
    )
    list_filter = (
        'is_active',
        'metro_line__system',
        'metro_line__line',
        'created_at',
    )
    search_fields = (
        'station',
        'metro_line__line',
        'metro_line__city__name',
    )
    list_editable = ('is_active',)
    ordering = ('metro_line__system__name', 'metro_line__line', 'station')


@admin.register(MetroLine)
class MetroLineAdmin(admin.ModelAdmin):
    """Администрирование справочника линий метро."""

    form = MetroLineForm
    list_select_related = ('system',)

    list_display = (
        'line',
        'line_color',
        'system',
        'is_active',
        'created_at',
    )
    list_filter = ('is_active', 'system', 'created_at')
    search_fields = ('line', 'system__name')
    list_editable = ('is_active',)
    ordering = ('system__name', 'line')

    def get_deleted_objects(self, objects, request):
        """Show protected memberships before individual or bulk deletion."""
        deleted, counts, permissions, protected = super().get_deleted_objects(objects, request)
        protected.extend(str(line) for line in MetroLine.objects.filter(
            pk__in=[item.pk for item in objects], stations__isnull=False,
        ).select_related('system', 'city').distinct())
        return deleted, counts, permissions, protected


@admin.register(MetroSystem)
class MetroSystemAdmin(admin.ModelAdmin):
    """Maintain network centers with bounded canonical autocomplete."""

    form = MetroSystemForm
    autocomplete_fields = ('location',)
    list_display = ('name', 'location', 'is_active')
    list_select_related = ('location',)
    search_fields = ('name', 'location__name')



@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Provide bounded geographic lookup for customer autocomplete fields."""

    search_fields = ('name',)
    list_display = ('name', 'location_type', 'parent', 'region')
    list_select_related = ('location_type', 'parent', 'region')

    def has_add_permission(self, request):
        """Keep canonical source creation in the import workflow."""
        return False

    def has_change_permission(self, request, obj=None):
        """Keep canonical hierarchy changes in the geographic workflow."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Preserve identifiers and existing geographic references."""
        return False
