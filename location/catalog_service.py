"""Maintain canonical dictionaries without changing legacy or business identities."""

from django.core.exceptions import ValidationError
from django.db import connection, transaction
from django.db.models import Q

from .models import Location, LocationAlias, LocationClosure


CATALOG_CATEGORIES = {
    'regions': 'region', 'localities': 'locality', 'districts': 'district',
}
CATALOG_KEYS = {category: key for key, category in CATALOG_CATEGORIES.items()}


def lock_location_catalog():
    """Serialize tree writes with each atomic GAR region load."""
    with connection.cursor() as cursor:
        cursor.execute('SELECT pg_advisory_xact_lock(%s)', [78001109])


def catalog_locations(key):
    """Return administrative levels without substituting municipalities."""
    from property.location_context import locality_filter

    queryset = Location.objects.select_related('parent', 'region', 'location_type')
    if key == 'localities':
        return queryset.filter(locality_filter())
    return queryset.filter(location_type__category=CATALOG_CATEGORIES[key])


def filter_catalog_locations(queryset, parameters):
    """Apply the same canonical search, scope and ordering in React and Django."""
    from .models import LegacyLocationMapping

    if parameters.get('q'):
        search = parameters['q']
        queryset = queryset.filter(
            Q(name__icontains=search) | Q(aliases__name__icontains=search),
        ).distinct()
    if parameters.get('regionId'):
        queryset = queryset.filter(region_id=parameters['regionId'])
    if parameters.get('legacyRegionId'):
        queryset = queryset.filter(region_id__in=LegacyLocationMapping.objects.filter(
            model_name='region', legacy_id=parameters['legacyRegionId'],
        ).values('location_id'))
    if parameters.get('ancestorId'):
        queryset = queryset.filter(ancestor_links__ancestor_id=parameters['ancestorId'])
    if parameters.get('typeId'):
        queryset = queryset.filter(location_type_id=parameters['typeId'])
    if parameters.get('status') in ('active', 'inactive'):
        queryset = queryset.filter(is_active=parameters['status'] == 'active')
    ordering = parameters.get('ordering') or 'name'
    field = {
        'name': 'name', 'region': 'region__name', 'type': 'location_type__name',
    }[ordering.lstrip('-')]
    return queryset.order_by(
        ('-' if ordering.startswith('-') else '') + field, 'name', 'pk',
    )


@transaction.atomic
def save_catalog_location(category, values, instance=None):
    """Retain IDs, aliases and source identities while updating a subtree safely."""
    lock_location_catalog()
    if instance is not None:
        instance = Location.objects.select_for_update().get(pk=instance.pk)
        category = instance.location_type.category
    location_type = values.get('location_type', instance.location_type if instance else None)
    if location_type is None or location_type.category != category:
        raise ValidationError({'typeId': 'Выберите тип соответствующего уровня.'})
    parent = values.get('parent', instance.parent if instance else None)
    if category == 'region' and parent is not None:
        raise ValidationError({'parentId': 'Регион не может иметь родительскую территорию.'})
    if category != 'region' and parent is None:
        raise ValidationError({'parentId': 'Выберите родительскую административную территорию.'})
    if parent is not None:
        parent = (
            Location.objects.select_for_update(of=('self',))
            .select_related('region').get(pk=parent.pk)
        )
        if not parent.region_id or parent.region.location_type.category != 'region':
            raise ValidationError({'parentId': 'У родительской территории не определён регион.'})
        if instance and LocationClosure.objects.filter(
            ancestor=instance, descendant=parent,
        ).exists():
            raise ValidationError({'parentId': 'Нельзя перенести территорию внутрь самой себя.'})
    name = values.get('name', instance.name if instance else '').strip()
    if not name:
        raise ValidationError({'name': 'Введите название.'})
    duplicates = Location.objects.filter(
        name__iexact=name, parent=parent, location_type=location_type,
    )
    if instance:
        duplicates = duplicates.exclude(pk=instance.pk)
    if duplicates.exists():
        raise ValidationError({
            'name': 'Такая территория этого типа уже существует у выбранного родителя.',
        })
    previous_name = instance.name if instance else name
    previous_parent = instance.parent_id if instance else None
    created = instance is None
    location = instance or Location(source_status='manual')
    location.name, location.location_type, location.parent = name, location_type, parent
    location.region_id = parent.region_id if parent else location.pk
    location.is_active = values.get('is_active', location.is_active)
    location.full_clean()
    location.save()
    if category == 'region' and location.region_id != location.pk:
        location.region_id = location.pk
        location.save(update_fields=['region'])
    LocationAlias.objects.bulk_create([
        LocationAlias(location=location, name=alias) for alias in {previous_name, name}
    ], ignore_conflicts=True)
    if created:
        LocationClosure.objects.create(ancestor=location, descendant=location, depth=0)
    if created or previous_parent != location.parent_id:
        descendants = list(LocationClosure.objects.filter(
            ancestor=location,
        ).values_list('descendant_id', 'depth'))
        identifiers = [identifier for identifier, _ in descendants]
        Location.objects.filter(pk__in=identifiers).update(region_id=location.region_id)
        LocationClosure.objects.filter(
            descendant_id__in=identifiers,
        ).exclude(ancestor_id__in=identifiers).delete()
        ancestors = list(LocationClosure.objects.filter(
            descendant=parent,
        ).values_list('ancestor_id', 'depth')) if parent else []
        LocationClosure.objects.bulk_create([
            LocationClosure(
                ancestor_id=ancestor, descendant_id=descendant,
                depth=depth + distance + 1,
            )
            for ancestor, depth in ancestors for descendant, distance in descendants
        ], batch_size=2000)
    return catalog_locations(CATALOG_KEYS[category]).get(pk=location.pk)


@transaction.atomic
def delete_catalog_location(location):
    """Delete only unused manual records; protect imported identities and all links."""
    lock_location_catalog()
    location = Location.objects.select_for_update().get(pk=location.pk)
    if location.identifiers.exists() or location.legacy_mappings.exists():
        raise ValidationError(
            'Запись связана с источником или прежним справочником. '
            'Снимите флаг «Активно».',
        )
    if location.region_id == location.pk:
        location.region = None
        location.save(update_fields=['region'])
    location.delete()
