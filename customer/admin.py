from django.contrib import admin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(admin.ModelAdmin):
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
    list_filter = ('is_active', 'purchase_goal', 'has_owned_property', 'residence_city', 'desired_city')
    search_fields = ('first_name', 'last_name', 'phone', 'email', 'user__email')
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
