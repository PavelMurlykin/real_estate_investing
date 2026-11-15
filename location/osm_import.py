"""Import bounded Russian location dictionaries from the public Overpass API."""

import json
import logging
import re
from contextlib import contextmanager
from dataclasses import dataclass, field
from http.client import HTTPException
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.db import IntegrityError, connection, transaction
from django.db.models import Q
from django.utils import timezone

from .models import City, District, Metro, MetroLine, Region

logger = logging.getLogger(__name__)

OVERPASS_ENDPOINTS = (
    'https://maps.mail.ru/osm/tools/overpass/api/interpreter',
    'https://overpass.private.coffee/api/interpreter',
)
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
QUERY_HEADER = '[out:json][timeout:15][maxsize:67108864];'
SOURCE_URL = 'https://www.openstreetmap.org/copyright'
IMPORT_LOCK_IDENTIFIER = 77391042


class LocationImportError(Exception):
    """Report an unavailable, incomplete, or conflicting location import."""


@dataclass(frozen=True)
class LocationRecord:
    """Represent a validated source row before entering a transaction."""

    source_identifier: str
    name: str
    attributes: dict = field(default_factory=dict)

    def __post_init__(self):
        """Reject source values that cannot fit the persistent dictionary."""
        if not self.source_identifier or len(self.source_identifier) > 200:
            raise LocationImportError('Неверная длина идентификатора источника.')


@contextmanager
def import_guard():
    """Serialize extraction and loading across all workers without a transaction."""
    with connection.cursor() as cursor:
        cursor.execute(
            'SELECT pg_try_advisory_lock(%s)', [IMPORT_LOCK_IDENTIFIER],
        )
        acquired = cursor.fetchone()[0]
    if not acquired:
        raise LocationImportError('Другой импорт ещё выполняется. Повторите позже.')
    try:
        yield
    finally:
        with connection.cursor() as cursor:
            cursor.execute(
                'SELECT pg_advisory_unlock(%s)', [IMPORT_LOCK_IDENTIFIER],
            )


def validate_elements(elements):
    """Reject malformed tags or relation members before source normalization."""
    for element in elements:
        source_identifier(element)
        tags = element_tags(element)
        if not all(isinstance(value, str) for value in tags.values()):
            raise ValueError('Malformed Overpass tags')
        members = element.get('members', [])
        if not isinstance(members, list) or not all(
            isinstance(member, dict)
            and member.get('type') in ('node', 'way', 'relation')
            and type(member.get('ref')) is int
            and member['ref'] > 0
            for member in members
        ):
            raise ValueError('Malformed Overpass members')


def download_overpass(query):
    """Use two fixed HTTPS endpoints with bounded reads and timeouts."""
    parameters = urlencode({'data': QUERY_HEADER + query})
    for endpoint in OVERPASS_ENDPOINTS:
        request = Request(
            f'{endpoint}?{parameters}',
            headers={
                'Accept': 'application/json',
                'User-Agent': 'real-estate-investing/1.0 '
                '(+https://github.com/PavelMurlykin/real_estate_investing)',
            },
        )
        try:
            with urlopen(request, timeout=20) as response:
                raw_response = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw_response) > MAX_RESPONSE_BYTES:
                raise ValueError('Response exceeds size limit')
            payload = json.loads(raw_response)
            if (
                not isinstance(payload, dict)
                or payload.get('remark')
                or not isinstance(payload.get('elements'), list)
                or not all(isinstance(row, dict) for row in payload['elements'])
            ):
                raise ValueError('Incomplete Overpass response')
            validate_elements(payload['elements'])
            return payload['elements']
        except (
            OSError, URLError, HTTPException, ValueError, LocationImportError,
        ) as error:
            logger.warning('Overpass unavailable at %s: %s', endpoint, error)
    raise LocationImportError(
        'OpenStreetMap временно недоступен или вернул неполные данные. '
        'Изменения не сохранены. Повторите импорт позже.'
    )


def source_identifier(element):
    """Validate and return an OSM identity including its element type."""
    element_type = element.get('type')
    identifier = element.get('id')
    if (
        element_type not in ('node', 'way', 'relation')
        or type(identifier) is not int or identifier <= 0
    ):
        raise LocationImportError('Источник вернул неверный идентификатор.')
    return f'{element_type}/{identifier}'


def source_name(tags):
    """Normalize a Russian name without silently truncating source data."""
    value = tags.get('name:ru') or tags.get('name')
    if not isinstance(value, str):
        raise LocationImportError('В источнике отсутствует название локации.')
    name = ' '.join(value.split())
    if not name or len(name) > 100:
        raise LocationImportError('Некорректная длина названия в источнике.')
    return name


def element_tags(element):
    """Reject malformed source tags before normalization."""
    tags = element.get('tags', {})
    if not isinstance(tags, dict):
        raise LocationImportError('Источник вернул неверный формат тегов.')
    return tags


def russian_region(element):
    """Recognize only administrative regions explicitly coded for Russia."""
    tags = element_tags(element)
    return (
        element.get('type') == 'relation'
        and tags.get('admin_level') == '4'
        and isinstance(tags.get('ISO3166-2'), str)
        and re.fullmatch(r'RU-[A-Z0-9]{2,3}', tags['ISO3166-2'])
    )


def build_query(dictionary, region=None, city=None):
    """Constrain requests to Russian regions and an explicit city boundary."""
    if dictionary == 'regions':
        return 'rel["admin_level"="4"]["ISO3166-2"~"^RU-"];out tags;'
    match = re.fullmatch(r'relation/(\d+)', region.source_identifier or '')
    if not match:
        raise LocationImportError('Сначала импортируйте регионы России.')
    query = (
        f'rel({match[1]})["admin_level"="4"]'
        '["ISO3166-2"~"^RU-"]->.region;'
        '.region map_to_area->.regionArea;'
    )
    if dictionary == 'cities':
        return query + (
            '(nwr(area.regionArea)["place"~"^(city|town)$"];'
            '.region;);out body;'
        )
    # Federal cities use the same boundary as their region.
    if city.source_identifier == region.source_identifier:
        query += '.region->.boundary;'
    elif city.source_identifier.startswith('relation/'):
        identifier = city.source_identifier.removeprefix('relation/')
        if not identifier.isdecimal():
            raise LocationImportError('Неверная граница города в источнике.')
        query += f'rel({identifier})(area.regionArea)->.boundary;'
    else:
        name = json.dumps(city.name, ensure_ascii=False)
        query += (
            f'(rel(area.regionArea)["boundary"="administrative"]["name"={name}];'
            f'rel(area.regionArea)["boundary"="administrative"]["name:ru"={name}];'
            f'rel(area.regionArea)["boundary"="administrative"]["short_name"={name}];'
            ')->.boundary;'
        )
    query += '.boundary map_to_area->.cityArea;'
    if dictionary == 'districts':
        query += (
            'rel(area.cityArea)["boundary"="administrative"]'
            '["admin_level"~"^(5|6|8|9|10)$"]->.items;'
            '(.region;.boundary;.items;);out body;'
        )
    elif dictionary == 'metro':
        query += (
            'nwr(area.cityArea)["railway"~"^(station|halt|stop)$"]->.stops;'
            '(rel(bn.stops)["route"="subway"];'
            'rel(bw.stops)["route"="subway"];'
            'rel(br.stops)["route"="subway"];)->.routes;'
            'rel(br.routes)["route_master"="subway"]->.masters;'
            '(.region;.boundary;.stops;.routes;.masters;);out body;'
        )
    else:
        raise LocationImportError('Неизвестный справочник импорта.')
    return query


def normalize_locations(
    elements, dictionary, region=None, city=None, city_level=4,
):
    """Normalize regions, city places and actual urban subdivisions."""
    records = {}
    city_references = {}
    ambiguous_cities = set()
    skipped = 0
    # A federal city can also have a separate settlement relation in OSM.
    # Its Russian region boundary is the canonical city scope, including suburbs.
    if dictionary == 'cities':
        for element in elements:
            tags = element_tags(element)
            if (
                russian_region(element)
                and source_identifier(element) == region.source_identifier
                and tags['ISO3166-2'] in ('RU-MOW', 'RU-SPE', 'RU-SEV')
            ):
                name = source_name(tags)
                records[name.casefold()] = LocationRecord(
                    region.source_identifier, name, {'region_id': region.pk},
                )
    for element in elements:
        tags = element_tags(element)
        if dictionary == 'regions':
            if not russian_region(element):
                skipped += 1
                continue
            attributes = {'code': tags['ISO3166-2']}
            reference = tags.get('ref', '')
            if isinstance(reference, str) and re.fullmatch(r'\d{2,3}', reference):
                attributes['legacy_code'] = reference
        elif dictionary == 'cities':
            is_federal_city = (
                russian_region(element)
                and source_identifier(element) == region.source_identifier
                and tags['ISO3166-2'] in ('RU-MOW', 'RU-SPE', 'RU-SEV')
            )
            if tags.get('place') not in ('city', 'town') and not is_federal_city:
                continue
            attributes = {'region_id': region.pk}
        else:
            if (
                element.get('type') != 'relation'
                or tags.get('boundary') != 'administrative'
                or tags.get('admin_level') not in ('5', '6', '8', '9', '10')
                or russian_region(element)
                or int(tags['admin_level']) <= city_level
            ):
                continue
            # Districts must describe urban units, never rural municipalities.
            if tags.get('place') in ('city', 'town', 'village', 'hamlet'):
                continue
            attributes = {'city_id': city.pk}
        record = LocationRecord(
            source_identifier(element), source_name(tags), attributes,
        )
        key = record.name.casefold()
        if key in ambiguous_cities:
            skipped += 1
            continue
        previous = records.get(key)
        if previous:
            if dictionary != 'cities':
                raise LocationImportError(
                    f'Неоднозначные одноимённые записи: {record.name}.'
                )
            if previous.source_identifier == region.source_identifier:
                continue
            # One city may have a label node, a place polygon and a boundary.
            # Prefer its boundary, then polygon, without merging homonyms.
            priorities = {'node': 0, 'way': 1, 'relation': 2}
            previous_type = previous.source_identifier.split('/')[0]
            current_type = record.source_identifier.split('/')[0]
            previous_reference = city_references.get(key)
            current_reference = tags.get('wikidata')
            conflicting_references = (
                previous_reference and current_reference
                and previous_reference != current_reference
            )
            same_priority = priorities[previous_type] == priorities[current_type]
            if conflicting_references or (
                same_priority
                and previous.source_identifier != record.source_identifier
                and not (previous_reference and previous_reference == current_reference)
            ):
                records.pop(key)
                ambiguous_cities.add(key)
                skipped += 2
                continue
            if priorities[previous_type] >= priorities[current_type]:
                continue
        records[key] = record
        city_references[key] = tags.get('wikidata')
    if dictionary in ('regions', 'cities') and not records:
        raise LocationImportError('Источник не вернул локации. Изменений нет.')
    return list(records.values()), skipped


def validate_scope(elements, region, city=None):
    """Require Russian region and one unambiguous urban boundary in response."""
    regions = [element for element in elements if russian_region(element)]
    if not any(
        source_identifier(element) == region.source_identifier
        for element in regions
    ):
        raise LocationImportError('Выбранный регион не подтверждён как Россия.')
    if city is None:
        return set()
    if city.source_identifier == region.source_identifier:
        return {region.source_identifier}
    boundaries = {
        source_identifier(element)
        for element in elements
        if element.get('type') == 'relation'
        and element_tags(element).get('boundary') == 'administrative'
        and (
            source_identifier(element) == city.source_identifier
            or city.name.casefold() in {
                str(element_tags(element).get(key, '')).casefold()
                for key in ('name', 'name:ru', 'short_name')
            }
        )
    }
    if len(boundaries) != 1:
        raise LocationImportError(
            'В OpenStreetMap не найдена однозначная граница города. '
            'Районы и метро не импортированы.'
        )
    return boundaries


def normalize_metro(elements, city):
    """Group directional routes into lines and transfer stops into stations."""
    by_identity = {source_identifier(row): row for row in elements}
    masters = {}
    for element in elements:
        if element_tags(element).get('route_master') == 'subway':
            for member in element.get('members', []):
                if member.get('type') == 'relation':
                    masters[f'relation/{member["ref"]}'] = element
    lines = {}
    stations = {}
    skipped = 0
    for route in elements:
        tags = element_tags(route)
        if tags.get('route') != 'subway':
            continue
        master = masters.get(source_identifier(route))
        line_tags = element_tags(master) if master else tags
        reference = line_tags.get('ref') or tags.get('ref')
        if not reference:
            skipped += 1
            continue
        line_identity = f'{city.source_identifier}/subway/{reference}'
        name = source_name(line_tags)
        # Direction suffixes belong to routes, not to the line name.
        name = re.split(r'\s*[:：]\s*', name, maxsplit=1)[0].strip()
        name = re.sub(r'\s+линия$', '', name, flags=re.IGNORECASE)
        color = line_tags.get('colour') or tags.get('colour') or '#777777'
        if not isinstance(color, str) or not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
            color = '#777777'
        lines.setdefault(line_identity, LocationRecord(
            line_identity, name, {'city_id': city.pk, 'line_color': color},
        ))
        for member in route.get('members', []):
            identity = f'{member.get("type")}/{member.get("ref")}'
            stop = by_identity.get(identity)
            if stop is None:
                continue
            stop_tags = element_tags(stop)
            if stop_tags.get('railway') not in ('station', 'halt', 'stop'):
                continue
            if not (stop_tags.get('name:ru') or stop_tags.get('name')):
                skipped += 1
                continue
            station_name = source_name(stop_tags)
            record = LocationRecord(
                f'{line_identity}/{identity}', station_name,
                {'line_source_identifier': line_identity},
            )
            key = (line_identity, station_name.casefold())
            previous = stations.get(key)
            if previous is None or record.source_identifier < previous.source_identifier:
                stations[key] = record
    # Exclude routes without any station in the selected city.
    used_lines = {row.attributes['line_source_identifier'] for row in stations.values()}
    return (
        [row for key, row in lines.items() if key in used_lines],
        list(stations.values()), skipped,
    )


def upsert_records(model, records, parent_field=None, parent_identifier=None):
    """Match stable source IDs, adopt natural keys, then bulk write changes."""
    queryset = model.objects.all()
    if parent_field:
        queryset = queryset.filter(
            Q(**{parent_field: parent_identifier})
            | Q(source_identifier__in=[row.source_identifier for row in records])
        )
    existing = list(queryset)
    by_source = {row.source_identifier: row for row in existing if row.source_identifier}
    name_field = 'station' if model is Metro else 'line' if model is MetroLine else 'name'
    by_name = {}
    for row in existing:
        if parent_field and getattr(row, parent_field) != parent_identifier:
            continue
        key = getattr(row, name_field).casefold()
        if key in by_name:
            raise LocationImportError('Сначала устраните дубли названий в справочнике.')
        by_name[key] = row
    by_code = {row.code: row for row in existing} if model is Region else {}
    created = []
    updated = []
    unchanged = 0
    result = {}
    timestamp = timezone.now()
    changed_fields = {name_field, 'source_identifier', 'updated_at'}
    for record in records:
        row = by_source.get(record.source_identifier)
        natural_match = by_name.get(record.name.casefold())
        if row and natural_match and row.pk != natural_match.pk:
            raise LocationImportError(f'Конфликт переименования: {record.name}.')
        if row is None:
            row = natural_match
        if row is None and model is Region:
            row = by_code.get(record.attributes['code']) or by_code.get(
                record.attributes.get('legacy_code'),
            )
        if row and row.source_identifier not in (None, record.source_identifier):
            raise LocationImportError(f'Конфликт источника: {record.name}.')
        attributes = {
            key: value for key, value in record.attributes.items()
            if key != 'legacy_code'
        }
        if model is Region and row:
            attributes['code'] = row.code
        attributes.update({
            name_field: record.name,
            'source_identifier': record.source_identifier,
        })
        changed_fields.update(attributes)
        if row is None:
            row = model(**attributes)
            created.append(row)
        elif any(getattr(row, key) != value for key, value in attributes.items()):
            for key, value in attributes.items():
                setattr(row, key, value)
            row.updated_at = timestamp
            updated.append(row)
        else:
            unchanged += 1
        result[record.source_identifier] = row
    if created:
        model.objects.bulk_create(created, batch_size=500)
    if updated:
        model.objects.bulk_update(updated, sorted(changed_fields), batch_size=500)
    return result, {
        'created': len(created), 'updated': len(updated), 'unchanged': unchanged,
    }


def import_locations(dictionary, region=None, city=None):
    """Prevent simultaneous external imports before downloading any data."""
    with import_guard():
        return _import_locations(dictionary, region, city)


def _import_locations(dictionary, region=None, city=None):
    """Fetch and normalize first, then atomically add and refresh locations."""
    elements = download_overpass(build_query(dictionary, region, city))
    boundaries = validate_scope(elements, region, city) if region else set()
    if dictionary == 'metro':
        lines, records, skipped = normalize_metro(elements, city)
    else:
        city_level = next((
            int(element_tags(row).get('admin_level', '4'))
            for row in elements if source_identifier(row) in boundaries
        ), 4)
        records, skipped = normalize_locations(
            [row for row in elements if source_identifier(row) not in boundaries],
            dictionary, region, city, city_level,
        )
    try:
        with transaction.atomic():
            if dictionary == 'metro':
                line_objects, line_counts = upsert_records(
                    MetroLine, lines, 'city_id', city.pk,
                )
                counts = {'created': 0, 'updated': 0, 'unchanged': 0}
                # Each line is one bounded batch, never one query per station.
                for line_identity, line_object in line_objects.items():
                    station_records = [
                        LocationRecord(row.source_identifier, row.name, {
                            'metro_line_id': line_object.pk,
                        })
                        for row in records
                        if row.attributes['line_source_identifier'] == line_identity
                    ]
                    _, line_station_counts = upsert_records(
                        Metro, station_records, 'metro_line_id', line_object.pk,
                    )
                    for key in counts:
                        counts[key] += line_station_counts[key]
            else:
                model = {'regions': Region, 'cities': City, 'districts': District}[dictionary]
                parent_field = {'cities': 'region_id', 'districts': 'city_id'}.get(dictionary)
                parent_identifier = (
                    region.pk if dictionary == 'cities'
                    else city.pk if city else None
                )
                _, counts = upsert_records(model, records, parent_field, parent_identifier)
                line_counts = {'created': 0, 'updated': 0, 'unchanged': 0}
    except IntegrityError as error:
        raise LocationImportError(
            'Конфликт уникальных записей. Изменения отменены; проверьте справочник.'
        ) from error
    result = {
        **counts, 'skipped': skipped, 'lines': line_counts,
        'source': 'OpenStreetMap', 'sourceUrl': SOURCE_URL,
    }
    logger.info(
        'Location import dictionary=%s region=%s city=%s summary=%s',
        dictionary, region.pk if region else None,
        city.pk if city else None, result,
    )
    return result
