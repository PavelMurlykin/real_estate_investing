"""Authoritative writes for metro systems, lines and station geography."""

from django.db import transaction
from rest_framework import serializers

from location.models import Location, Metro, MetroLine, MetroSystem
from property.location_context import locality_filter


class MetroDictionaryWriteSerializer(serializers.Serializer):
    """Validate a network separately from the station's actual locality."""

    name = serializers.CharField(max_length=100, trim_whitespace=True)
    isActive = serializers.BooleanField(source='is_active', default=True)
    systemId = serializers.PrimaryKeyRelatedField(
        source='system', queryset=MetroSystem.objects.all(), required=False,
    )
    locationId = serializers.PrimaryKeyRelatedField(
        source='location', queryset=Location.objects.filter(locality_filter()),
        required=False, allow_null=True,
    )
    metroLineId = serializers.PrimaryKeyRelatedField(
        source='metro_line', queryset=MetroLine.objects.select_related('system'), required=False,
    )
    lineIds = serializers.PrimaryKeyRelatedField(
        source='lines', queryset=MetroLine.objects.all(), many=True, required=False,
    )
    lineColor = serializers.RegexField(r'^#[0-9A-Fa-f]{6}$', source='line_color', required=False)
    locationIsInferred = serializers.BooleanField(source='location_is_inferred', required=False)

    def validate(self, attributes):
        """Reject cross-network memberships and duplicate scoped names."""
        unknown = self.initial_data.keys() - self.fields.keys()
        if unknown:
            raise serializers.ValidationError({
                field: 'Поле недоступно для этого справочника.' for field in unknown
            })
        configuration = self.context['dictionary_configuration']
        key = configuration['key']
        allowed = {
            'metro-systems': {'name', 'is_active', 'location'},
            'metro-lines': {'name', 'is_active', 'system', 'line_color'},
            'metro': {'name', 'is_active', 'metro_line', 'lines', 'location', 'location_is_inferred'},
        }[key]
        unsupported = attributes.keys() - allowed
        if unsupported:
            raise serializers.ValidationError('Поле недоступно для этого справочника.')
        name_field = configuration['name_field']
        if 'name' in attributes:
            attributes[name_field] = ' '.join(attributes.pop('name').split())
        required = {'metro-systems': ('location', 'locationId'),
                    'metro-lines': ('system', 'systemId'),
                    'metro': ('metro_line', 'metroLineId')}[key]
        parent = attributes.get(required[0], getattr(self.instance, required[0], None))
        if parent is None:
            raise serializers.ValidationError({required[1]: 'Выберите связанную запись.'})
        if key == 'metro-lines':
            if self.instance is None and 'line_color' not in attributes:
                raise serializers.ValidationError({'lineColor': 'Укажите цвет линии.'})
            if self.instance and parent.pk != self.instance.system_id:
                if self.instance.metro_set.exists() or self.instance.stations.exists():
                    raise serializers.ValidationError({'systemId': 'У линии есть станции. Сохраните её систему.'})
        elif key == 'metro':
            memberships = attributes.get('lines')
            if memberships is None:
                memberships = list(self.instance.lines.all()) if self.instance else []
            memberships = {line.pk: line for line in memberships}
            memberships[parent.pk] = parent
            if any(line.system_id != parent.system_id for line in memberships.values()):
                raise serializers.ValidationError({'lineIds': 'Все линии станции должны относиться к одной системе.'})
            attributes['lines'] = list(memberships.values())
            if 'location' in attributes:
                attributes.setdefault('location_is_inferred', attributes['location'] is None)
            precise = not attributes.get(
                'location_is_inferred', getattr(self.instance, 'location_is_inferred', True),
            )
            if precise and not attributes.get('location', getattr(self.instance, 'location', None)):
                raise serializers.ValidationError({'locationId': 'Укажите населённый пункт станции.'})
        duplicate = configuration['model'].objects.filter(**{
            f'{name_field}__iexact': attributes.get(name_field, getattr(self.instance, name_field, '')),
        })
        if key != 'metro-systems':
            duplicate = duplicate.filter(**{required[0]: parent})
        if self.instance:
            duplicate = duplicate.exclude(pk=self.instance.pk)
        if duplicate.exists():
            raise serializers.ValidationError({'name': 'Запись с таким названием уже существует.'})
        return attributes

    @transaction.atomic
    def create(self, validated_data):
        """Create the entry and all memberships in one transaction."""
        lines = validated_data.pop('lines', None)
        instance = self.context['dictionary_configuration']['model'].objects.create(**validated_data)
        if lines is not None:
            instance.lines.set(lines)
        return instance

    @transaction.atomic
    def update(self, instance, validated_data):
        """Preserve legacy foreign keys and complex availability links."""
        lines = validated_data.pop('lines', None)
        for field, value in validated_data.items():
            setattr(instance, field, value)
        instance.save(update_fields=[*validated_data, 'updated_at'])
        if lines is not None:
            instance.lines.set(lines)
        return instance
