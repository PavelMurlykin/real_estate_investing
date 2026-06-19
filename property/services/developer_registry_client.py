"""Client for the DOM.RF developer registry source."""

import json
import os
from dataclasses import dataclass
from urllib import error, parse, request


DEFAULT_DEVELOPER_REGISTRY_API_URL = (
    'https://xn--80az8a.xn--d1aqf.xn--p1ai/'
    '%D1%81%D0%B5%D1%80%D0%B2%D0%B8%D1%81%D1%8B/'
    'api/erz/developers'
)
DEFAULT_DEVELOPER_REGISTRY_REGIONS = ('77', '78')
DEFAULT_DEVELOPER_REGISTRY_PAGE_SIZE = 100
DEFAULT_DEVELOPER_REGISTRY_TIMEOUT_SECONDS = 30
DEFAULT_DEVELOPER_REGISTRY_USER_AGENT = (
    'real-estate-investing-developer-registry-importer/1.0'
)
DEVELOPER_REGISTRY_DETAIL_ID_ALIASES = (
    'id',
    'developerId',
    'devId.devId',
    'devId',
    'erzId',
)


class DeveloperRegistryClientError(Exception):
    """Raised when developer registry data cannot be fetched."""


@dataclass(frozen=True)
class DeveloperRegistrySourceItem:
    """Raw source item with its construction region filter."""

    region_code: str
    payload: dict


class DomRfDeveloperRegistryClient:
    """Fetch developer registry rows from DOM.RF."""

    def __init__(
        self,
        api_url=None,
        detail_api_url=None,
        page_size=DEFAULT_DEVELOPER_REGISTRY_PAGE_SIZE,
        timeout_seconds=DEFAULT_DEVELOPER_REGISTRY_TIMEOUT_SECONDS,
        user_agent=DEFAULT_DEVELOPER_REGISTRY_USER_AGENT,
    ):
        """Store HTTP client settings."""
        self.api_url = (
            api_url
            or os.getenv('DOM_RF_DEVELOPER_REGISTRY_API_URL')
            or DEFAULT_DEVELOPER_REGISTRY_API_URL
        )
        self.detail_api_url = (
            detail_api_url
            or os.getenv('DOM_RF_DEVELOPER_REGISTRY_DETAIL_API_URL')
            or ''
        )
        self.page_size = page_size
        self.timeout_seconds = timeout_seconds
        self.user_agent = user_agent

    def fetch_developers(self, region_codes=None, limit=None):
        """Yield raw developer rows for the requested construction regions."""
        selected_regions = (
            tuple(region_codes)
            if region_codes
            else DEFAULT_DEVELOPER_REGISTRY_REGIONS
        )
        yielded_count = 0

        for region_code in selected_regions:
            for source_item in self.fetch_region_developers(region_code):
                yield source_item
                yielded_count += 1
                if limit and yielded_count >= limit:
                    return

    def fetch_region_developers(self, region_code):
        """Yield raw developer rows for one construction region."""
        offset = 0

        while True:
            payload = self.fetch_page(region_code, offset)
            rows = extract_rows_from_payload(payload)
            if not rows:
                return

            for row in rows:
                if isinstance(row, dict):
                    row = self.enrich_row_with_detail(row)
                    yield DeveloperRegistrySourceItem(
                        region_code=str(region_code),
                        payload=row,
                    )

            total_count = extract_total_count_from_payload(payload)
            offset += len(rows)
            if total_count is not None and offset >= total_count:
                return
            if len(rows) < self.page_size:
                return

    def fetch_page(self, region_code, offset):
        """Fetch one JSON page from the DOM.RF registry API."""
        query = parse.urlencode(
            {
                'regionHD': region_code,
                'offset': offset,
                'limit': self.page_size,
            }
        )
        url = f'{self.api_url}?{query}'
        http_request = request.Request(
            url,
            headers={
                'Accept': 'application/json',
                'User-Agent': self.user_agent,
            },
        )

        try:
            with request.urlopen(
                http_request,
                timeout=self.timeout_seconds,
            ) as response:
                content = response.read().decode('utf-8')
        except error.HTTPError as exception:
            raise DeveloperRegistryClientError(
                (
                    'DOM.RF developer registry returned HTTP '
                    f'{exception.code}.'
                )
            ) from exception
        except error.URLError as exception:
            raise DeveloperRegistryClientError(
                f'DOM.RF developer registry is unavailable: {exception.reason}'
            ) from exception

        try:
            return json.loads(content)
        except json.JSONDecodeError as exception:
            raise DeveloperRegistryClientError(
                'DOM.RF developer registry returned invalid JSON.'
            ) from exception

    def enrich_row_with_detail(self, row):
        """Merge row with developer detail payload when detail API is configured."""
        if not self.detail_api_url:
            return row

        developer_id = extract_developer_detail_id(row)
        if not developer_id:
            return row

        detail_payload = self.fetch_detail(developer_id)
        detail_rows = extract_rows_from_payload(detail_payload)
        if detail_rows and isinstance(detail_rows[0], dict):
            return {**row, **detail_rows[0]}
        if isinstance(detail_payload, dict):
            detail_data = detail_payload.get('data', detail_payload)
            if isinstance(detail_data, dict):
                return {**row, **detail_data}
        return row

    def fetch_detail(self, developer_id):
        """Fetch one developer detail payload."""
        if '{developer_id}' in self.detail_api_url:
            url = self.detail_api_url.format(
                developer_id=parse.quote(str(developer_id))
            )
        else:
            query = parse.urlencode({'developerId': developer_id})
            separator = '&' if '?' in self.detail_api_url else '?'
            url = f'{self.detail_api_url}{separator}{query}'

        http_request = request.Request(
            url,
            headers={
                'Accept': 'application/json',
                'User-Agent': self.user_agent,
            },
        )
        try:
            with request.urlopen(
                http_request,
                timeout=self.timeout_seconds,
            ) as response:
                content = response.read().decode('utf-8')
        except error.HTTPError as exception:
            raise DeveloperRegistryClientError(
                (
                    'DOM.RF developer detail returned HTTP '
                    f'{exception.code}.'
                )
            ) from exception
        except error.URLError as exception:
            raise DeveloperRegistryClientError(
                f'DOM.RF developer detail is unavailable: {exception.reason}'
            ) from exception

        try:
            return json.loads(content)
        except json.JSONDecodeError as exception:
            raise DeveloperRegistryClientError(
                'DOM.RF developer detail returned invalid JSON.'
            ) from exception


def extract_rows_from_payload(payload):
    """Extract row list from common DOM.RF API response shapes."""
    if isinstance(payload, list):
        return payload

    for path in (
        ('data', 'list'),
        ('data', 'items'),
        ('data', 'content'),
        ('data', 'result'),
        ('data', 'rows'),
        ('data', 'objects'),
        ('data', 'developers'),
        ('data',),
        ('list',),
        ('items',),
        ('content',),
        ('result',),
        ('rows',),
        ('objects',),
        ('developers',),
    ):
        value = read_payload_path(payload, path)
        if isinstance(value, list):
            return value

    return []


def extract_total_count_from_payload(payload):
    """Extract total row count from common DOM.RF API response shapes."""
    for path in (
        ('data', 'total'),
        ('data', 'totalCount'),
        ('data', 'totalElements'),
        ('data', 'count'),
        ('total',),
        ('totalCount',),
        ('totalElements',),
        ('count',),
    ):
        value = read_payload_path(payload, path)
        if isinstance(value, int):
            return value
        if isinstance(value, str) and value.isdigit():
            return int(value)
    return None


def read_payload_path(payload, path):
    """Read nested dictionary value by key path."""
    value = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def extract_developer_detail_id(row):
    """Return a source developer identifier from a raw row."""
    for alias in DEVELOPER_REGISTRY_DETAIL_ID_ALIASES:
        value = read_payload_path(row, tuple(alias.split('.')))
        if value not in (None, '') and not isinstance(value, dict):
            return value
    return ''
