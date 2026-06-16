from django.apps import AppConfig


FORM_DATA_CACHE_KEYS = (
    'mortgage:property_form_data:v1',
    'mortgage:program_form_data:v1',
)


def clear_form_data_cache(**kwargs):
    """Clear cached mortgage form selector payloads."""
    from django.core.cache import cache

    cache.delete_many(FORM_DATA_CACHE_KEYS)


class CalculatorConfig(AppConfig):
    """Mortgage app configuration."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'mortgage'
    verbose_name = 'Ипотека'

    def ready(self):
        """Register cache invalidation hooks for selector payloads."""
        from django.db.models.signals import post_delete, post_save

        from bank.models import Bank, BankProgram, KeyRate
        from location.models import City, District
        from property.models import (
            ApartmentDecoration,
            ApartmentLayout,
            Developer,
            Property,
            RealEstateComplex,
            RealEstateComplexBuilding,
        )

        for model in (
            ApartmentDecoration,
            ApartmentLayout,
            Bank,
            BankProgram,
            City,
            Developer,
            District,
            KeyRate,
            Property,
            RealEstateComplex,
            RealEstateComplexBuilding,
        ):
            dispatch_uid = f'mortgage.clear_form_data_cache.{model._meta.label}'
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
