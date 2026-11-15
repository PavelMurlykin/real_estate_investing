"""Provide small public-source fixtures to service and API integration tests."""

import json
from pathlib import Path

from location.open_data import CITY_CATALOG_URL, WIKIDATA_API_URL, WIKIPEDIA_API_URL


def load_sources():
    """Read representative CSV and structured JSON without external requests."""
    directory = Path(__file__).parent / 'data'
    return {
        'csv': (directory / 'cities.csv').read_text(encoding='utf-8'),
        **json.loads((directory / 'wikimedia.json').read_text(encoding='utf-8')),
    }


def source_reply(sources, endpoint, parameters=None):
    """Emulate only the transport envelopes of fixed public data providers."""
    if endpoint == CITY_CATALOG_URL:
        return sources['csv']
    if endpoint == WIKIDATA_API_URL:
        if parameters['action'] == 'wbsearchentities':
            identifier = 'Q656' if parameters['search'] == 'Санкт-Петербург' else 'Q649'
            return json.dumps({'search': [{'id': identifier}, {'id': 'Q666'}]})
        return json.dumps({'entities': {
            identifier: sources['entities'][identifier]
            for identifier in parameters['ids'].split('|')
        }})
    if endpoint == WIKIPEDIA_API_URL:
        if parameters.get('list') == 'categorymembers':
            return json.dumps({'query': {'categorymembers': [
                {'pageid': row['pageid']} for row in sources['regional_pages']
            ]}})
        if parameters.get('prop') == 'pageprops':
            return json.dumps({'query': {'pages': sources['regional_pages']}})
        if parameters.get('redirects'):
            titles = parameters['titles'].split('|')
            return json.dumps({'query': {'pages': [
                {
                    'pageid': sources.get('page_ids', {}).get(title, index + 100),
                    'title': title,
                }
                for index, title in enumerate(sorted(titles))
            ]}})
        return json.dumps({'query': {'pages': [{
            'revisions': [{'slots': {'main': {'content': json.dumps(sources['metro'])}}}],
        }]}})
    raise AssertionError(f'Unexpected external endpoint: {endpoint}')
