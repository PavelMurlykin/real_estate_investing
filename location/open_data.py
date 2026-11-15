"""Read openly licensed Russian cities and Wikimedia location catalogs."""

import csv
import io
import json
import logging
import math
import re
import time
from datetime import date
from http.client import HTTPException
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)
CITY_CATALOG_URL = 'https://raw.githubusercontent.com/hflabs/city/master/city.csv'
WIKIDATA_API_URL = 'https://www.wikidata.org/w/api.php'
WIKIPEDIA_API_URL = 'https://ru.wikipedia.org/w/api.php'
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
USER_AGENT = (
    'real-estate-investing/1.0 '
    '(+https://github.com/PavelMurlykin/real_estate_investing)'
)
METRO_SCHEMES = {
    'Москва': 'Московского',
    'Санкт-Петербург': 'Петербургского',
    'Казань': 'Казанского',
    'Екатеринбург': 'Екатеринбургского',
    'Нижний Новгород': 'Нижегородского',
    'Новосибирск': 'Новосибирского',
    'Самара': 'Самарского',
}


class OpenDataError(Exception):
    """Report an unavailable or unrecognized public data response."""


def location_key(name, kind=None):
    """Compare explicit names while allowing established type suffixes."""
    value = name.casefold().replace('ё', 'е')
    if kind == 'region':
        value = re.sub(r'\bреспублика\b', '', value)
    elif kind == 'district':
        value = re.sub(r'\bрайон\b', '', value)
    elif kind in ('line', 'metroline'):
        value = re.sub(r'\bлиния\b', '', value)
    return ' '.join(re.findall(r'\w+', value))


def clean_name(value):
    """Validate names without truncation or opaque markup in dictionaries."""
    if not isinstance(value, str):
        raise OpenDataError('Источник вернул запись без названия.')
    value = ' '.join(value.split())
    if not value or len(value) > 100:
        raise OpenDataError('Некорректная длина названия в открытом справочнике.')
    return value


def current_claims(entity, property_identifier):
    """Exclude deprecated, ended and future claims, respecting preferred rank."""
    claims = []
    today = date.today().isoformat()
    for claim in entity.get('claims', {}).get(property_identifier, []):
        if claim.get('rank') == 'deprecated':
            continue
        qualifiers = claim.get('qualifiers', {})
        ended = any(
            value.get('datavalue', {}).get('value', {}).get('time', '')[1:11]
            <= today
            for value in qualifiers.get('P582', [])
        )
        future = any(
            value.get('datavalue', {}).get('value', {}).get('time', '')[1:11]
            > today
            for value in qualifiers.get('P580', [])
        )
        if not ended and not future:
            claims.append(claim)
    preferred = (
        [] if property_identifier in ('P150', 'P31') else
        [claim for claim in claims if claim.get('rank') == 'preferred']
    )
    return [
        claim['mainsnak']['datavalue']['value']
        for claim in preferred or claims
        if 'datavalue' in claim.get('mainsnak', {})
    ]


def entity_references(entity, property_identifier):
    """Return validated item references from current structured claims."""
    return {
        value['id'] for value in current_claims(entity, property_identifier)
        if isinstance(value, dict)
        and re.fullmatch(r'Q\d+', value.get('id', ''))
    }


class OpenLocationSource:
    """Fetch small read-only API batches with bounded time and response sizes."""

    def __init__(self):
        """Limit one user import to less than the application worker timeout."""
        self.deadline = time.monotonic() + 45
        self.entities = {}
        self.skipped = 0

    def download(self, endpoint, parameters=None):
        """Read only fixed providers; retry transient errors once with backoff."""
        if endpoint not in (CITY_CATALOG_URL, WIKIDATA_API_URL, WIKIPEDIA_API_URL):
            raise OpenDataError('Недопустимый источник данных.')
        encoded = urlencode(parameters or {}).encode()
        for attempt in range(2):
            remaining = self.deadline - time.monotonic()
            if remaining <= 0:
                raise OpenDataError('Импорт превысил время ожидания. Повторите позже.')
            request = Request(
                endpoint, data=encoded if parameters else None,
                headers={'User-Agent': USER_AGENT, 'Accept': 'application/json, text/csv'},
            )
            try:
                with urlopen(request, timeout=min(8, remaining)) as response:
                    raw_response = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw_response) > MAX_RESPONSE_BYTES:
                    raise OpenDataError('Ответ источника превысил допустимый размер.')
                try:
                    return raw_response.decode('utf-8-sig')
                except UnicodeError as error:
                    raise OpenDataError('Источник вернул неверную кодировку.') from error
            except HTTPError as error:
                if error.code < 500 or attempt:
                    raise OpenDataError(
                        f'Открытый источник временно недоступен (HTTP {error.code}). '
                        'Изменения не сохранены.'
                    ) from error
            except (OSError, URLError, HTTPException) as error:
                if attempt:
                    raise OpenDataError(
                        'Открытый источник временно недоступен. Изменения не сохранены.'
                    ) from error
            time.sleep(0.5)
        raise OpenDataError('Источник временно недоступен.')

    def api(self, endpoint, parameters):
        """Decode a complete JSON result, including MediaWiki error envelopes."""
        try:
            payload = json.loads(self.download(endpoint, {
                **parameters, 'format': 'json',
            }))
        except (ValueError, UnicodeError) as error:
            raise OpenDataError('Источник вернул неверный формат данных.') from error
        if not isinstance(payload, dict) or payload.get('error'):
            raise OpenDataError('Источник вернул ошибку API. Изменения не сохранены.')
        return payload

    def city_catalog(self):
        """Read the licensed Russian city snapshot with stable FIAS identifiers."""
        rows = []
        reader = csv.DictReader(io.StringIO(self.download(CITY_CATALOG_URL)))
        required = {'country', 'region', 'region_type', 'city', 'fias_id', 'kladr_id'}
        if not required.issubset(reader.fieldnames or []):
            raise OpenDataError('Изменился формат справочника городов HFLabs.')
        for row in reader:
            if row['country'] != 'Россия':
                self.skipped += 1
                continue
            if not re.fullmatch(r'\d{13,}', row['kladr_id'] or ''):
                raise OpenDataError('Неверный код региона в справочнике HFLabs.')
            if not re.fullmatch(
                r'[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}',
                row['fias_id'] or '',
            ):
                raise OpenDataError('Неверный идентификатор города в справочнике HFLabs.')
            region_name = clean_name(row['region'])
            region_type = row['region_type']
            if region_type == 'Респ':
                region_name = (
                    f'{region_name} Республика' if region_name.endswith('ая')
                    else f'Республика {region_name}'
                )
            elif region_type in ('обл', 'край', 'АО', 'Аобл'):
                suffix = {
                    'обл': 'область', 'край': 'край',
                    'АО': 'автономный округ', 'Аобл': 'автономная область',
                }[region_type]
                region_name = f'{region_name} {suffix}'
            row['region_name'] = clean_name(region_name)
            row['region_code'] = row['kladr_id'][:2]
            row['city_name'] = clean_name(row['city'] or row.get('settlement') or row['region'])
            rows.append(row)
        if not rows:
            raise OpenDataError('Справочник HFLabs не содержит городов России.')
        return rows

    def get_entities(self, identifiers):
        """Read 50 items per request and reject missing or partial responses."""
        missing = sorted(set(identifiers) - self.entities.keys())
        if not all(re.fullmatch(r'Q\d+', identifier) for identifier in missing):
            raise OpenDataError('Некорректный идентификатор Wikidata.')
        for offset in range(0, len(missing), 50):
            batch = missing[offset:offset + 50]
            payload = self.api(WIKIDATA_API_URL, {
                'action': 'wbgetentities', 'ids': '|'.join(batch),
                'props': 'labels|claims', 'languages': 'ru',
            })
            entities = payload.get('entities', {})
            if not isinstance(entities, dict) or any(
                not isinstance(entities.get(identifier), dict)
                or 'missing' in entities[identifier]
                for identifier in batch
            ):
                raise OpenDataError('Wikidata вернула неполный ответ.')
            self.entities.update(entities)
        return {identifier: self.entities[identifier] for identifier in identifiers}

    def resolve_city(self, city_row):
        """Resolve Russian homonyms by country and the city catalog coordinates."""
        payload = self.api(WIKIDATA_API_URL, {
            'action': 'wbsearchentities', 'search': city_row['city_name'],
            'language': 'ru', 'limit': 10, 'type': 'item',
        })
        search_results = payload.get('search')
        if not isinstance(search_results, list) or any(
            not isinstance(row, dict) or not isinstance(row.get('id'), str)
            for row in search_results
        ):
            raise OpenDataError('Wikidata вернула неполный ответ поиска.')
        identifiers = [row['id'] for row in search_results]
        candidates = self.get_entities(identifiers)
        classes = self.get_entities(set().union(*[
            entity_references(entity, 'P31') for entity in candidates.values()
        ]))
        city_classes = {
            identifier for identifier, entity in classes.items()
            if 'город' in entity.get('labels', {}).get('ru', {}).get('value', '').casefold()
            and not any(word in entity.get('labels', {}).get('ru', {}).get('value', '').casefold()
                        for word in ('округ', 'поселение', 'агломерация'))
        }
        matches = []
        latitude = float(city_row['geo_lat'])
        longitude = float(city_row['geo_lon'])
        for entity in candidates.values():
            if not entity_references(entity, 'P31') & city_classes:
                continue
            label = entity.get('labels', {}).get('ru', {}).get('value', '')
            if location_key(label) != location_key(city_row['city_name']):
                continue
            if 'Q159' not in entity_references(entity, 'P17'):
                continue
            for coordinate in current_claims(entity, 'P625'):
                if not isinstance(coordinate, dict):
                    continue
                distance = math.hypot(
                    coordinate.get('latitude', 1000) - latitude,
                    (coordinate.get('longitude', 1000) - longitude)
                    * math.cos(math.radians(latitude)),
                ) * 111
                if distance <= 25:
                    matches.append(entity)
                    break
        if len(matches) != 1:
            raise OpenDataError('В Wikidata не найден однозначный российский город.')
        return matches[0]

    def districts(self, city_row):
        """Read current urban districts directly from structured city claims."""
        city = self.resolve_city(city_row)
        identifiers = entity_references(city, 'P150')
        if not identifiers:
            return []
        districts = self.get_entities(identifiers)
        class_identifiers = set().union(*[
            entity_references(entity, 'P31') for entity in districts.values()
        ])
        classes = self.get_entities(class_identifiers)
        district_classes = {
            identifier for identifier, entity in classes.items()
            if 'район' in entity.get('labels', {}).get('ru', {}).get('value', '').casefold()
            and 'муниципаль' not in entity.get(
                'labels', {},
            ).get('ru', {}).get('value', '').casefold()
        }
        result = []
        for identifier, entity in districts.items():
            if not entity_references(entity, 'P31') & district_classes:
                continue
            if current_claims(entity, 'P576'):
                continue
            countries = entity_references(entity, 'P17')
            if countries and 'Q159' not in countries:
                continue
            name = entity.get('labels', {}).get('ru', {}).get('value')
            result.append((f'wikidata/{identifier}', clean_name(name)))
        return result

    def station_pages(self, titles):
        """Resolve redirects to stable page IDs so renames preserve station keys."""
        titles = sorted(set(titles))
        result = {}
        for offset in range(0, len(titles), 50):
            batch = titles[offset:offset + 50]
            payload = self.api(WIKIPEDIA_API_URL, {
                'action': 'query', 'titles': '|'.join(batch),
                'redirects': 1, 'formatversion': 2,
            })
            query = payload.get('query', {})
            pages = query.get('pages', [])
            if not isinstance(pages, list) or any(
                not isinstance(page, dict) or page.get('missing')
                or not isinstance(page.get('pageid'), int)
                or not isinstance(page.get('title'), str)
                for page in pages
            ):
                raise OpenDataError('Википедия вернула неполный список станций.')
            by_title = {page['title']: page for page in pages}
            redirects = {
                row['from']: row['to']
                for row in query.get('normalized', []) + query.get('redirects', [])
            }
            for title in batch:
                resolved = title
                seen = set()
                while resolved in redirects and resolved not in seen:
                    seen.add(resolved)
                    resolved = redirects[resolved]
                if resolved not in by_title:
                    raise OpenDataError('Википедия вернула неполный список станций.')
                result[title] = by_title[resolved]
        return result

    def regional_metro(self, adjective):
        """Read regional station catalogs and operating lines from Wikimedia."""
        payload = self.api(WIKIPEDIA_API_URL, {
            'action': 'query', 'list': 'categorymembers', 'cmnamespace': 0,
            'cmtitle': f'Категория:Станции {adjective} метрополитена', 'cmlimit': 500,
        })
        members = payload.get('query', {}).get('categorymembers')
        if not isinstance(members, list) or not members or payload.get('continue'):
            raise OpenDataError('Недоступен полный открытый каталог станций города.')
        identifiers = set()
        for offset in range(0, len(members), 50):
            batch = members[offset:offset + 50]
            if any(not isinstance(member.get('pageid'), int) for member in batch):
                raise OpenDataError('Неверный формат каталога станций.')
            payload = self.api(WIKIPEDIA_API_URL, {
                'action': 'query', 'pageids': '|'.join(str(row['pageid']) for row in batch),
                'prop': 'pageprops', 'ppprop': 'wikibase_item', 'formatversion': 2,
            })
            pages = payload.get('query', {}).get('pages', [])
            if len(pages) != len(batch) or any(page.get('missing') for page in pages):
                raise OpenDataError('Википедия вернула неполный каталог станций.')
            identifiers.update(
                page['pageprops']['wikibase_item'] for page in pages
                if page.get('pageprops', {}).get('wikibase_item')
            )
        entities = self.get_entities(identifiers)
        line_identifiers = set().union(*[
            entity_references(entity, 'P81') for entity in entities.values()
        ])
        line_entities = self.get_entities(line_identifiers)
        lines, stations = {}, []
        for identifier, entity in entities.items():
            countries = entity_references(entity, 'P17')
            statuses = entity_references(entity, 'P5817')
            opening = current_claims(entity, 'P1619')
            opened = any(
                isinstance(value, dict) and value.get('time') and value['time'][1:11]
                <= date.today().isoformat() for value in opening
            )
            if (
                countries and 'Q159' not in countries
                or current_claims(entity, 'P576')
                or statuses and 'Q55654238' not in statuses
                or not opened and 'Q55654238' not in statuses
            ):
                self.skipped += 1
                continue
            for line_identifier in entity_references(entity, 'P81'):
                line = line_entities[line_identifier]
                line_countries = entity_references(line, 'P17')
                if line_countries and 'Q159' not in line_countries:
                    continue
                source_identifier = f'wikidata/{line_identifier}'
                colors = current_claims(line, 'P465')
                color = colors[0] if colors else '777777'
                if not isinstance(color, str) or not re.fullmatch(r'[0-9A-Fa-f]{6}', color):
                    color = '777777'
                lines[source_identifier] = (
                    source_identifier,
                    clean_name(line.get('labels', {}).get('ru', {}).get('value')),
                    f'#{color}',
                )
                name = clean_name(entity.get('labels', {}).get('ru', {}).get('value'))
                stations.append((
                    f'wikidata/{identifier}/line/{line_identifier}', name, source_identifier,
                ))
        if not lines or not stations:
            raise OpenDataError('В каталоге не найдены действующие станции метро.')
        return list(lines.values()), stations

    def metro(self, city_row):
        """Read active stations and lines from versioned Wikipedia JSON schemes."""
        city_name = city_row['city_name']
        adjective = METRO_SCHEMES.get(city_name)
        if adjective is None:
            return [], []
        if city_name not in ('Москва', 'Санкт-Петербург'):
            return self.regional_metro(adjective)
        title = f'Шаблон:Интерактивная схема {adjective} метрополитена/data.json'
        payload = self.api(WIKIPEDIA_API_URL, {
            'action': 'query', 'titles': title, 'prop': 'revisions',
            'rvprop': 'content', 'rvslots': 'main', 'formatversion': 2,
        })
        pages = payload.get('query', {}).get('pages', [])
        if len(pages) != 1 or pages[0].get('missing'):
            raise OpenDataError('Открытая JSON-схема метро выбранного города недоступна.')
        try:
            raw = pages[0]['revisions'][0]['slots']['main']['content']
            scheme = json.loads(raw)
            raw_lines = scheme['lines']
        except (KeyError, IndexError, TypeError, ValueError) as error:
            raise OpenDataError('Изменился формат JSON-схемы метро.') from error
        if not isinstance(raw_lines, list) or not raw_lines:
            raise OpenDataError('Схема метро не содержит линий.')
        lines, stations = [], []
        line_identities = {}
        for line in sorted(
            raw_lines, key=lambda item: not str(item.get('number', '')).isdecimal(),
        ):
            number = str(line.get('number', ''))
            if line.get('future') or not re.fullmatch(r'\d+[АаAa]?', number):
                continue
            line_name = re.sub(r'\s+линия(?:\s*\(.*\))?$', '', line.get('article', ''))
            line_name = clean_name(re.sub(r'\s*\(.*\)$', '', line_name))
            line_identity = f'wikipedia/{city_row["fias_id"]}/line/{number}'
            line_key = location_key(line_name, 'line')
            line_identity = line_identities.setdefault(line_key, line_identity)
            color = line.get('color', {})
            fill = color.get('fillStyle', '') if isinstance(color, dict) else color
            components = re.match(r'rgba?\(\s*(\d+),\s*(\d+),\s*(\d+)', fill)
            line_color = '#777777'
            if components and all(int(value) <= 255 for value in components.groups()):
                line_color = '#' + ''.join(f'{int(value):02X}' for value in components.groups())
            elif re.fullmatch(r'#[0-9A-Fa-f]{6}', fill):
                line_color = fill
            line_stations = []
            for station in line.get('stations', []):
                if station.get('future'):
                    self.skipped += 1
                    continue
                article = station.get('article')
                if not isinstance(article, str) or not article:
                    raise OpenDataError('В схеме метро отсутствует название станции.')
                line_stations.append((article, line_identity))
            if line_stations:
                if not any(identifier == line_identity for identifier, _, _ in lines):
                    lines.append((line_identity, line_name, line_color))
                stations.extend(line_stations)
        if not lines or not stations:
            raise OpenDataError('В открытой схеме не найдены действующие станции метро.')
        pages = self.station_pages([article for article, _ in stations])
        return lines, [
            (
                f'{line_identifier}/station/{pages[article]["pageid"]}',
                clean_name(re.sub(r'\s*\(.*\)$', '', pages[article]['title'])),
                line_identifier,
            )
            for article, line_identifier in stations
        ]
