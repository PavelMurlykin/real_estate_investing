"""Protect station memberships on every ORM deletion path."""

from django.db.models.deletion import ProtectedError
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from .models import MetroLine


@receiver(pre_delete, sender=MetroLine)
def protect_station_line_memberships(sender, instance, using, **kwargs):
    """Keep an additional line as protected as the primary station line."""
    if instance.stations.using(using).exists():
        raise ProtectedError('Линия используется станциями метро.', [instance])
