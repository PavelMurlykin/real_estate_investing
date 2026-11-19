"""Portable complex import, independent of file or future API transport."""

import base64
import binascii
import logging
import re
from unicodedata import normalize

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, connection, transaction
from django.db.models import CharField, Func, Prefetch, Q, Value
from django.db.models.functions import Lower, Replace
from rest_framework import serializers

from core.json_import import JsonImportError
from location.models import LegacyLocationMapping, Location, LocationClosure
from .complex_import_locations import ImportLocationResolver
from .complex_import_metro import ImportMetroResolver
from .location_context import geography_prefetch, location_context
from .complex_photos import add_complex_photos, validate_complex_photos
from .models import (
    Developer, RealEstateClass, RealEstateComplex, RealEstateComplexLocation,
    RealEstateComplexPhoto, RealEstateType, TransportAccessibilityType,
)


MAX_COMPLEX_IMPORT_BYTES = 16 * 1024 * 1024
logger = logging.getLogger(__name__)


def normalized_name(value):
    """Ignore casing, spacing and decorative project-name punctuation."""
    value = normalize('NFKC', value).casefold().replace('ё', 'е')
    value = re.sub(r'^жк\s+', '', value)
    return re.sub(r'[^a-zа-я0-9]', '', value)


class ImportPhotoSerializer(serializers.Serializer):
    """Validate an embedded image without fetching arbitrary remote URLs."""

    name = serializers.CharField(max_length=150)
    data = serializers.CharField(max_length=8 * 1024 * 1024, trim_whitespace=False)
    source_url = serializers.URLField(required=False, max_length=2000)


class ImportLocationReferenceSerializer(serializers.Serializer):
    """Accept one portable FIAS GUID or an explicit local canonical ID."""

    id = serializers.IntegerField(min_value=1, required=False)
    fias_id = serializers.UUIDField(required=False)

    def to_internal_value(self, data):
        """Reject misspelled reference fields instead of ignoring conflicting IDs."""
        if isinstance(data, dict) and data.keys() - {'id', 'fias_id'}:
            raise serializers.ValidationError('Ссылка содержит только id или fias_id.')
        return super().to_internal_value(data)

    def validate(self, attributes):
        """Reject missing and conflicting reference mechanisms."""
        if len(attributes) != 1:
            raise serializers.ValidationError('Укажите ровно одно поле: id или fias_id.')
        return attributes


class ImportMetroSerializer(serializers.Serializer):
    """Describe station identity independently of the complex's locality."""

    station = serializers.CharField(max_length=100, required=False)
    line = serializers.CharField(max_length=100, required=False)
    color = serializers.RegexField(r'^#[0-9a-fA-F]{6}$', required=False)
    station_id = serializers.IntegerField(min_value=1, required=False)
    station_source_identifier = serializers.CharField(max_length=200, required=False)
    system_id = serializers.IntegerField(min_value=1, required=False)
    system_location = ImportLocationReferenceSerializer(required=False)
    mode = serializers.ChoiceField(
        choices=('Пешком', 'На транспорте', 'На электричке'),
    )
    minutes = serializers.IntegerField(min_value=1, max_value=1440)

    def validate(self, attributes):
        """Require either one station reference or a complete natural key."""
        references = {'station_id', 'station_source_identifier'}.intersection(attributes)
        natural_fields = {'station', 'line', 'color', 'system_id', 'system_location'}
        if len(references) > 1 or references and natural_fields.intersection(attributes):
            raise serializers.ValidationError('Передайте одну ссылку на станцию либо её систему, линию и название.')
        if not references and not {'station', 'line'}.issubset(attributes):
            raise serializers.ValidationError('Укажите станцию и линию либо ссылку на станцию.')
        if 'system_id' in attributes and 'system_location' in attributes:
            raise serializers.ValidationError('Укажите систему по ID либо её центру.')
        return attributes


class ImportComplexSerializer(serializers.Serializer):
    """Validate one canonical project with its source and nested records."""

    key = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)
    match_name = serializers.CharField(max_length=255, required=False)
    match_city = serializers.CharField(max_length=100, required=False)
    region_code = serializers.CharField(max_length=10, required=False)
    region = serializers.CharField(max_length=100, required=False)
    city = serializers.CharField(max_length=100, required=False)
    district = serializers.CharField(max_length=100, required=False)
    location = ImportLocationReferenceSerializer(required=False)
    match_location = ImportLocationReferenceSerializer(required=False)
    developer = serializers.CharField(max_length=255)
    real_estate_class = serializers.CharField(max_length=100)
    real_estate_type = serializers.CharField(max_length=100)
    description = serializers.CharField(max_length=15000)
    map_link = serializers.URLField(
        required=False, allow_blank=True, max_length=2000,
    )
    presentation_link = serializers.URLField(
        required=False, allow_blank=True, max_length=2000,
    )
    buildings = serializers.ListField(
        child=serializers.DictField(), min_length=1, max_length=100,
    )
    metro = ImportMetroSerializer(many=True, max_length=100, default=list)
    photos = ImportPhotoSerializer(many=True, max_length=3, default=list)
    primary_photo = serializers.IntegerField(min_value=0, required=False)
    sources = serializers.ListField(
        child=serializers.URLField(max_length=2000), min_length=1,
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attributes):
        """Decode and verify all photos before any database mutation."""
        photos = attributes['photos']
        if (
            'primary_photo' in attributes and not photos
            or photos and attributes.get('primary_photo', 0) >= len(photos)
        ):
            raise serializers.ValidationError({
                'primary_photo': 'Выберите существующее фото.',
            })
        attributes['primary_photo'] = attributes.get('primary_photo', 0) if photos else None
        files = []
        for photo in attributes['photos']:
            try:
                content = base64.b64decode(photo['data'], validate=True)
            except (binascii.Error, ValueError) as error:
                raise serializers.ValidationError(
                    {'photos': 'Неверный base64.'},
                ) from error
            files.append(SimpleUploadedFile(photo['name'], content))
        attributes['photo_files'] = validate_complex_photos(files) if files else []
        return attributes


class ComplexImportSerializer(serializers.Serializer):
    """Version the transport-neutral catalog contract."""

    version = serializers.ChoiceField(choices=(1, 2))
    complexes = ImportComplexSerializer(many=True, min_length=1, max_length=100)
    metadata = serializers.DictField(required=False)

    def validate(self, attributes):
        """Keep version 1 intact and make version 2 geography explicit."""
        for row in attributes['complexes']:
            if attributes['version'] == 1:
                required = {'region_code', 'region', 'city', 'district'}
                if not required.issubset(row) or not row['metro'] or not row['photos']:
                    raise serializers.ValidationError('Версия 1 требует регион, город, район, метро и фотографии.')
                if 'location' in row or 'match_location' in row:
                    raise serializers.ValidationError('Для ссылок на локации используйте версию 2.')
                for station in row['metro']:
                    if not {'station', 'line', 'color'}.issubset(station):
                        raise serializers.ValidationError('В версии 1 укажите название станции, линию и цвет.')
            else:
                if 'location' not in row:
                    raise serializers.ValidationError('В версии 2 требуется location: id или fias_id населённого пункта.')
                if {'region_code', 'region', 'city', 'district', 'match_city'}.intersection(row):
                    raise serializers.ValidationError('В версии 2 используйте location и match_location вместо старой географии.')
                for station in row['metro']:
                    if 'station' in station and not {'system_id', 'system_location'}.intersection(station):
                        raise serializers.ValidationError('Для названия станции в версии 2 укажите систему метро.')
        return attributes


def _resolve(model, field, value, defaults=None, **scope):
    """Resolve a normalized natural key, rejecting ambiguous dictionaries."""
    candidates = [
        row for row in model.objects.filter(**scope)
        if normalized_name(getattr(row, field)) == normalized_name(value)
    ]
    if len(candidates) > 1:
        raise JsonImportError(f'Неоднозначное значение справочника: {value}.')
    if candidates:
        return candidates[0]
    return model.objects.create(**{**(defaults or {}), field: value, **scope})


def _existing_buildings(complex_object):
    """Retain omitted buildings and all links used by saved properties."""
    fields = {
        'commissioning_date': 'commissioningDate',
        'commissioning_year': 'commissioningYear',
        'commissioning_quarter': 'commissioningQuarter',
        'key_handover_date': 'keyHandoverDate',
        'key_handover_year': 'keyHandoverYear',
        'key_handover_quarter': 'keyHandoverQuarter',
    }
    buildings = {}
    if complex_object is None:
        return buildings
    for row in complex_object.realestatecomplexbuilding_set.all():
        attributes = {
            'id': row.pk, 'number': row.number, 'address': row.address,
            'isActive': row.is_active,
        }
        for source, target in fields.items():
            value = getattr(row, source)
            attributes[target] = (
                value.isoformat() if hasattr(value, 'isoformat') else value
            )
        buildings[normalized_name(row.number)] = attributes
    return buildings


def _merged_import_buildings(existing, supplied_buildings, complex_name):
    """Rename explicitly matched buildings without moving their properties."""
    buildings = _existing_buildings(existing)
    supplied_numbers = [
        normalized_name(building.get('number', ''))
        for building in supplied_buildings
    ]
    if len(set(supplied_numbers)) != len(supplied_numbers):
        raise JsonImportError(f'Повторяющиеся корпуса в ЖК «{complex_name}».')
    matched_identifiers = set()
    matched_numbers = set()
    replacements = []
    for supplied in supplied_buildings:
        if 'id' in supplied:
            raise JsonImportError(
                'В импорте используются номера корпусов, без ID базы.',
            )
        building = dict(supplied)
        number = normalized_name(building.get('number', ''))
        previous_number = building.pop('match_number', None)
        previous = None
        if 'match_number' in supplied:
            if (
                not isinstance(previous_number, str)
                or not previous_number.strip()
                or len(previous_number) > 100
                or not normalized_name(previous_number)
            ):
                raise JsonImportError(
                    'match_number должен содержать прежний номер корпуса.',
                )
            previous_number = normalized_name(previous_number)
            if previous_number in matched_numbers:
                raise JsonImportError(
                    'Прежний номер корпуса использован несколько раз.',
                )
            matched_numbers.add(previous_number)
            previous = buildings.get(previous_number)
        current = buildings.get(number)
        if current and previous and current['id'] != previous['id']:
            raise JsonImportError(
                f'Старый и новый номера корпуса в ЖК «{complex_name}» '
                'относятся к разным записям.',
            )
        matched = current or previous
        if existing and 'match_number' in supplied and matched is None:
            raise JsonImportError(
                f'Корпус для переименования в ЖК «{complex_name}» не найден.',
            )
        if matched:
            if matched['id'] in matched_identifiers:
                raise JsonImportError(
                    'Один корпус сопоставлен нескольким записям файла.',
                )
            matched_identifiers.add(matched['id'])
        replacements.append((number, {**(matched or {}), **building}))

    buildings = {
        number: building for number, building in buildings.items()
        if building['id'] not in matched_identifiers
    }
    buildings.update(replacements)
    return list(buildings.values())


def import_complex_catalog(payload):
    """Validate a catalog and apply all records atomically with file cleanup."""
    serializer = ComplexImportSerializer(data=payload)
    serializer.is_valid(raise_exception=True)
    rows = serializer.validated_data['complexes']
    keys = [row['key'] for row in rows]
    if len(set(keys)) != len(keys):
        raise JsonImportError('Ключ источника повторяется в файле.')
    saved_files = []
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(%s)', [0x434F4D50])
            summary = {
                'created': 0, 'updated': 0, 'photos': 0,
                'buildings': 0, 'metro': 0,
            }
            locations = ImportLocationResolver()
            metro = ImportMetroResolver(locations)
            prepared = [(row, locations.territory(row)) for row in rows]
            names = [(territory.locality.pk, normalized_name(row['name'])) for row, territory in prepared]
            if len(set(names)) != len(names):
                raise JsonImportError('ЖК повторяется в одной территории файла.')
            for row, territory in prepared:
                _import_complex(row, territory, locations, metro, summary, saved_files)
        logger.info('Complex catalog imported: %s', summary)
        return summary
    except Exception as error:
        storage = RealEstateComplexPhoto._meta.get_field('image').storage
        for filename in saved_files:
            storage.delete(filename)
        if isinstance(error, IntegrityError):
            raise JsonImportError(
                'Конфликт существующих записей. Проверьте key, match_name и match_location. '
                'Изменения импорта отменены.',
            ) from error
        raise


def _matching_complexes(row, territory, locations):
    """Search normalized names in SQL, then compare canonical identities."""
    names = {
        normalized_name(row['name']),
        normalized_name(row.get('match_name', row['name'])),
    }
    expression = Replace(Lower('name'), Value('ё'), Value('е'))
    for pattern in (r'^жк\s+', r'[^a-zа-я0-9]'):
        expression = Func(
            expression, Value(pattern), Value(''), Value('g'),
            function='regexp_replace', output_field=CharField(),
        )
    queryset = RealEstateComplex.objects.annotate(import_name=expression).filter(
        import_name__in=names,
    )
    target = (
        locations.reference(row['match_location'])
        if row.get('match_location') else territory.locality
    )
    if not row.get('match_city'):
        current_links = RealEstateComplexLocation.objects.filter(is_primary=True).filter(
            Q(location=target) | Q(location__ancestor_links__ancestor=target)
            | Q(location__descendant_links__descendant=target),
        ).values('real_estate_complex_id')
        mapped_districts = LegacyLocationMapping.objects.filter(model_name='district').filter(
            Q(location=target) | Q(location__ancestor_links__ancestor=target)
            | Q(location__descendant_links__descendant=target),
        ).values('legacy_id')
        queryset = queryset.filter(Q(pk__in=current_links) | Q(district_id__in=mapped_districts))
    candidates = list(queryset.prefetch_related(geography_prefetch()).select_for_update(of=('self',))[:101])
    if len(candidates) > 100:
        raise JsonImportError('Слишком много совпадений названия. Укажите уникальный ключ источника.')
    fallback_ids = {candidate.district_id for candidate in candidates
                    if candidate.district_id and candidate.primary_location is None}
    fallbacks = {}
    if fallback_ids:
        ancestors = LocationClosure.objects.select_related('ancestor__location_type').prefetch_related(
            'ancestor__legacy_mappings',
        ).order_by('depth')
        fallbacks = {mapping.legacy_id: mapping.location for mapping in LegacyLocationMapping.objects.filter(
            model_name='district', legacy_id__in=fallback_ids,
        ).select_related('location__location_type').prefetch_related(
            Prefetch('location__ancestor_links', queryset=ancestors),
        )}
    matches = []
    for candidate in candidates:
        current = candidate.primary_location or fallbacks.get(candidate.district_id)
        if current is None:
            continue
        geography = location_context(candidate, explicit_location=current)
        if row.get('match_city'):
            names = {geography.city}
            if current.location_type.category == 'district' and candidate.district_id:
                for path in current.ancestor_links.all():
                    if path.ancestor_id == geography.locality_id:
                        names.update(mapping.legacy_name for mapping in path.ancestor.legacy_mappings.all()
                                     if mapping.model_name == 'city' and mapping.legacy_name)
            matched = any(normalized_name(name) == normalized_name(row['match_city']) for name in names)
        elif row.get('match_location') or row.get('location'):
            matched = geography.locality_id == target.pk or (
                current.location_type.category == 'district' and locations.contains(current, target)
            )
        else:
            matched = geography.locality_id == territory.locality.pk or locations.contains(territory.primary, current)
        if matched:
            matches.append(candidate)
    return matches


def _import_complex(row, territory, locations, metro, summary, saved_files):
    """Resolve one canonical project and merge its buildings and metro."""
    from api_v1.serializers import RealEstateComplexWriteSerializer

    existing = RealEstateComplex.objects.select_for_update().filter(
        source_key=row['key'],
    ).first()
    matches = _matching_complexes(row, territory, locations)
    if len(matches) > 1 or (existing and matches and existing.pk != matches[0].pk):
        raise JsonImportError(f'Неоднозначное сопоставление ЖК «{row["name"]}».')
    existing = existing or (matches[0] if matches else None)
    if existing and existing.source_key and existing.source_key != row['key']:
        raise JsonImportError(f'ЖК «{row["name"]}» уже привязан к другому ключу.')
    primary = locations.primary_for(row, territory, existing)
    developer = existing.developer if existing else _resolve(
        Developer, 'name', row['developer'],
    )
    estate_class = RealEstateClass.objects.filter(
        name__iexact=row['real_estate_class']
    ).first()
    if estate_class is None:
        raise JsonImportError(f'Класс ЖК отсутствует: {row["real_estate_class"]}.')
    estate_type = _resolve(RealEstateType, 'name', row['real_estate_type'])
    buildings = _merged_import_buildings(existing, row['buildings'], row['name'])

    metro_rows = {}
    if existing:
        for entry in existing.metro_availability.all():
            metro_rows[entry.metro_id] = {
                'id': entry.pk, 'metroId': entry.metro_id,
                'transportAccessibilityTypeId': entry.transport_accessibility_type_id,
                'walkingTimeMinutes': entry.walking_time_minutes,
                'isActive': entry.is_active,
            }
    seen_stations = set()
    for availability in row['metro']:
        station = metro.resolve(availability, territory)
        if station.pk in seen_stations:
            raise JsonImportError(f'Станция метро повторяется: {availability["station"]}.')
        seen_stations.add(station.pk)
        mode = _resolve(TransportAccessibilityType, 'name', availability['mode'])
        metro_rows[station.pk] = {
            **metro_rows.get(station.pk, {}), 'metroId': station.pk,
            'transportAccessibilityTypeId': mode.pk,
            'walkingTimeMinutes': availability['minutes'],
            'isActive': metro_rows.get(station.pk, {}).get('isActive', True),
        }
    attributes = {
        'name': row['name'], 'developerId': developer.pk,
        'locationId': primary.pk, 'realEstateClassId': estate_class.pk,
        'realEstateTypeId': estate_type.pk, 'description': row['description'],
        'buildings': buildings,
        'metroAvailability': list(metro_rows.values()),
    }
    for source, target in [
        ('map_link', 'mapLink'), ('presentation_link', 'presentationLink'),
    ]:
        if source in row:
            attributes[target] = row[source]
    writer = RealEstateComplexWriteSerializer(
        existing, data=attributes, partial=existing is not None,
    )
    # A version 1 file may identify only an administrative district. Keep it coarse.
    writer.fields['locationId'].queryset = Location.objects.filter(pk=primary.pk)
    writer.is_valid(raise_exception=True)
    complex_object = writer.save()
    complex_object.source_key = row['key']
    complex_object.save(update_fields=['source_key'])
    before_photos = complex_object.photos.count()
    if row['photo_files']:
        add_complex_photos(
            complex_object, row['photo_files'], row['primary_photo'], saved_files,
        )
    summary['created' if existing is None else 'updated'] += 1
    summary['photos'] += complex_object.photos.count() - before_photos
    summary['buildings'] += len(row['buildings'])
    summary['metro'] += len(row['metro'])
