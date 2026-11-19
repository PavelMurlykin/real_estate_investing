"""Handle protected memberships and retained legacy import references."""

from django.db.models.deletion import ProtectedError
from django.db.models.signals import post_delete, post_save, pre_delete
from django.dispatch import receiver

from .models import City, District, LegacyLocationMapping, MetroLine, Region
from .migration_support import legacy_catalog_metadata


@receiver(pre_delete, sender=MetroLine)
def protect_station_line_memberships(sender, instance, using, **kwargs):
    """Keep an additional line as protected as the primary station line."""
    if instance.stations.using(using).exists():
        raise ProtectedError('Линия используется станциями метро.', [instance])


@receiver(post_delete, sender=Region)
@receiver(post_delete, sender=City)
@receiver(post_delete, sender=District)
def clear_deleted_import_reference(sender, instance, using, **kwargs):
    """Keep the old URL mapping and release the deleted row's import metadata."""
    LegacyLocationMapping.objects.using(using).filter(
        model_name=sender._meta.model_name, legacy_id=instance.pk,
    ).update(legacy_name='', legacy_code='', legacy_source_identifier='')


@receiver(post_save, sender=Region)
@receiver(post_save, sender=City)
@receiver(post_save, sender=District)
def refresh_legacy_catalog_metadata(sender, instance, using, created, raw, update_fields, **kwargs):
    """Reflect status changes from callers that still save a legacy row directly."""
    if created or raw:
        return
    metadata = legacy_catalog_metadata(instance)
    if update_fields is not None:
        metadata = {field: value for field, value in metadata.items() if field.removeprefix('legacy_') in update_fields}
    if metadata:
        LegacyLocationMapping.objects.using(using).filter(
            model_name=sender._meta.model_name, legacy_id=instance.pk,
        ).update(**metadata)
