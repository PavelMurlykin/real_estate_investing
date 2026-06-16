from django.apps import AppConfig


FORM_DATA_CACHE_KEYS = (
    'property:complex_form_location:v1',
    'property:property_form_location:v1',
)


def clear_form_data_cache(**kwargs):
    """Clear cached property form location payloads."""
    from django.core.cache import cache

    cache.delete_many(FORM_DATA_CACHE_KEYS)


class PropertyConfig(AppConfig):
    """Property app configuration."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'property'
    verbose_name = 'Недвижимость'

    def ready(self):
        """Register cache invalidation hooks for location payloads."""
        from django.db.models.signals import post_delete, post_save

        from location.models import City, District, Metro

        from .models import (
            Developer,
            RealEstateComplex,
            RealEstateComplexBuilding,
        )

        for model in (
            City,
            Developer,
            District,
            Metro,
            RealEstateComplex,
            RealEstateComplexBuilding,
        ):
            dispatch_uid = f'property.clear_form_data_cache.{model._meta.label}'
            post_save.connect(
                clear_form_data_cache,
                sender=model,
                dispatch_uid=f'{dispatch_uid}.save',
            )
            post_delete.connect(
                clear_form_data_cache,
                sender=model,
                dispatch_uid=f'{dispatch_uid}.delete',
            )
