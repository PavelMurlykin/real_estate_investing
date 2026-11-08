"""Portable complex import, independent of file or future API transport."""

import base64
import binascii
import logging
import re
from unicodedata import normalize

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import connection, transaction
from rest_framework import serializers

from core.json_import import JsonImportError
from location.models import City, District, Metro, MetroLine, Region
from .complex_photos import add_complex_photos, validate_complex_photos
from .models import (
    Developer, RealEstateClass, RealEstateComplex, RealEstateComplexPhoto,
    RealEstateType, TransportAccessibilityType,
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


class ImportMetroSerializer(serializers.Serializer):
    """Describe a station by its city-local line and travel time."""

    station = serializers.CharField(max_length=100)
    line = serializers.CharField(max_length=100)
    color = serializers.RegexField(r'^#[0-9a-fA-F]{6}$')
    mode = serializers.ChoiceField(
        choices=('Пешком', 'На транспорте', 'На электричке'),
    )
    minutes = serializers.IntegerField(min_value=1, max_value=1440)


class ImportComplexSerializer(serializers.Serializer):
    """Validate one canonical project with its source and nested records."""

    key = serializers.CharField(max_length=255)
    name = serializers.CharField(max_length=255)
    match_name = serializers.CharField(max_length=255, required=False)
    match_city = serializers.CharField(max_length=100, required=False)
    region_code = serializers.CharField(max_length=10)
    region = serializers.CharField(max_length=100)
    city = serializers.CharField(max_length=100)
    district = serializers.CharField(max_length=100)
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
    metro = ImportMetroSerializer(many=True, min_length=1, max_length=100)
    photos = ImportPhotoSerializer(many=True, min_length=1, max_length=3)
    primary_photo = serializers.IntegerField(min_value=0, default=0)
    sources = serializers.ListField(
        child=serializers.URLField(max_length=2000), min_length=1,
    )
    notes = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attributes):
        """Decode and verify all photos before any database mutation."""
        if attributes['primary_photo'] >= len(attributes['photos']):
            raise serializers.ValidationError({
                'primary_photo': 'Выберите существующее фото.',
            })
        files = []
        for photo in attributes['photos']:
            try:
                content = base64.b64decode(photo['data'], validate=True)
            except (binascii.Error, ValueError) as error:
                raise serializers.ValidationError(
                    {'photos': 'Неверный base64.'},
                ) from error
            files.append(SimpleUploadedFile(photo['name'], content))
        attributes['photo_files'] = validate_complex_photos(files)
        return attributes


class ComplexImportSerializer(serializers.Serializer):
    """Version the transport-neutral catalog contract."""

    version = serializers.ChoiceField(choices=(1,))
    complexes = ImportComplexSerializer(many=True, min_length=1, max_length=100)
    metadata = serializers.DictField(required=False)


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
    names = [
        (normalized_name(row['city']), normalized_name(row['name']))
        for row in rows
    ]
    if len(set(keys)) != len(keys) or len(set(names)) != len(names):
        raise JsonImportError('ЖК или ключ источника повторяется в файле.')
    saved_files = []
    try:
        with transaction.atomic():
            with connection.cursor() as cursor:
                cursor.execute('SELECT pg_advisory_xact_lock(%s)', [0x434F4D50])
            summary = {
                'created': 0, 'updated': 0, 'photos': 0,
                'buildings': 0, 'metro': 0,
            }
            for row in rows:
                _import_complex(row, summary, saved_files)
        logger.info('Complex catalog imported: %s', summary)
        return summary
    except Exception:
        storage = RealEstateComplexPhoto._meta.get_field('image').storage
        for filename in saved_files:
            storage.delete(filename)
        raise


def _import_complex(row, summary, saved_files):
    """Resolve one canonical project and merge its buildings and metro."""
    from api_v1.serializers import RealEstateComplexWriteSerializer

    existing = RealEstateComplex.objects.filter(source_key=row['key']).first()
    matching_names = {
        normalized_name(row['name']),
        normalized_name(row.get('match_name', row['name'])),
    }
    matching_city = normalized_name(row.get('match_city', row['city']))
    matches = [
        candidate for candidate in RealEstateComplex.objects.select_related(
            'district__city',
        )
        if normalized_name(candidate.name) in matching_names
        and normalized_name(candidate.district.city.name) == matching_city
    ]
    if len(matches) > 1 or (existing and matches and existing.pk != matches[0].pk):
        raise JsonImportError(f'Неоднозначное сопоставление ЖК «{row["name"]}».')
    existing = existing or (matches[0] if matches else None)
    if existing and existing.source_key and existing.source_key != row['key']:
        raise JsonImportError(f'ЖК «{row["name"]}» уже привязан к другому ключу.')
    region, _ = Region.objects.get_or_create(
        code=row['region_code'], defaults={'name': row['region']},
    )
    city = _resolve(City, 'name', row['city'], region=region)
    district = _resolve(District, 'name', row['district'], city=city)
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
    if existing and existing.district.city_id == city.pk:
        for entry in existing.metro_availability.all():
            metro_rows[entry.metro_id] = {
                'id': entry.pk, 'metroId': entry.metro_id,
                'transportAccessibilityTypeId': entry.transport_accessibility_type_id,
                'walkingTimeMinutes': entry.walking_time_minutes,
                'isActive': entry.is_active,
            }
    seen_stations = set()
    for availability in row['metro']:
        line = _resolve(
            MetroLine, 'line', availability['line'], city=city,
            defaults={'line_color': availability['color']},
        )
        station = _resolve(
            Metro, 'station', availability['station'], metro_line=line,
        )
        if station.pk in seen_stations:
            raise JsonImportError(f'Станция метро повторяется: {availability["station"]}.')
        seen_stations.add(station.pk)
        mode = _resolve(TransportAccessibilityType, 'name', availability['mode'])
        metro_rows[station.pk] = {
            **metro_rows.get(station.pk, {}), 'metroId': station.pk,
            'transportAccessibilityTypeId': mode.pk,
            'walkingTimeMinutes': availability['minutes'], 'isActive': True,
        }
    attributes = {
        'name': row['name'], 'developerId': developer.pk,
        'districtId': district.pk, 'realEstateClassId': estate_class.pk,
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
    writer.is_valid(raise_exception=True)
    complex_object = writer.save()
    complex_object.source_key = row['key']
    complex_object.save(update_fields=['source_key'])
    before_photos = complex_object.photos.count()
    add_complex_photos(
        complex_object, row['photo_files'], row['primary_photo'], saved_files,
    )
    summary['created' if existing is None else 'updated'] += 1
    summary['photos'] += complex_object.photos.count() - before_photos
    summary['buildings'] += len(row['buildings'])
    summary['metro'] += len(row['metro'])
