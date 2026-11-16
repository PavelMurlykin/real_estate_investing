"""Read a pinned official GAR snapshot with bounded, verified ZIP range requests."""

import io
import json
import re
import struct
import time
import urllib.request
import xml.etree.ElementTree as ET
import zipfile
import zlib
from pathlib import Path
from urllib.parse import urlparse


METADATA_URL = 'https://fias.nalog.ru/WebServices/Public/GetLastDownloadFileInfo'


class GarSourceError(Exception):
    """Report an incomplete official snapshot without accepting partial records."""


def validate_source_url(url):
    """Validate initial URLs and redirects before opening any connection."""
    parsed = urlparse(url)
    if parsed.scheme != 'https' or parsed.hostname not in {
        'fias.nalog.ru', 'fias-file.nalog.ru',
    } or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise GarSourceError('Недопустимый адрес источника ГАР.')


class OfficialRedirect(urllib.request.HTTPRedirectHandler):
    """Prevent redirects from reaching hosts outside the official distribution."""

    def redirect_request(self, request, response, code, message, headers, url):
        """Apply the host policy before urllib follows a redirect."""
        validate_source_url(url)
        return super().redirect_request(request, response, code, message, headers, url)


def request(url, headers=None, method=None):
    """Restrict remote access to the official HTTPS distribution hosts."""
    validate_source_url(url)
    opener = urllib.request.build_opener(OfficialRedirect())
    response = opener.open(urllib.request.Request(
        url, headers={'User-Agent': 'RealEstateLocations/1.0', **(headers or {})},
        method=method,
    ), timeout=90)
    if urlparse(response.url).hostname not in {'fias.nalog.ru', 'fias-file.nalog.ru'}:
        response.close()
        raise GarSourceError('Недопустимое перенаправление источника ГАР.')
    return response


def latest_snapshot():
    """Resolve the free public metadata API once for an entire import job."""
    try:
        with request(METADATA_URL) as response:
            metadata = json.loads(response.read(1024 * 1024))
        return str(int(metadata['VersionId'])), metadata['GarXMLFullURL']
    except (OSError, ValueError, KeyError) as error:
        raise GarSourceError('Не удалось получить версию ГАР ФНС. Повторите импорт.') from error


class RemoteArchive(io.RawIOBase):
    """Expose only ZIP metadata; large members are downloaded in one range each."""

    def __init__(self, url):
        """Pin archive size and entity tag before reading its central directory."""
        self.url = url
        with request(url, method='HEAD') as response:
            self.length = int(response.headers['Content-Length'])
            self.etag = response.headers.get('ETag', '')
        self.position = 0

    def seekable(self):
        """Allow zipfile to seek through the remote central directory."""
        return True

    def seek(self, offset, whence=0):
        """Move the metadata cursor without performing a network request."""
        self.position = (offset if whence == 0 else self.position + offset
                         if whence == 1 else self.length + offset)
        return self.position

    def tell(self):
        """Return the current metadata offset."""
        return self.position

    def open_range(self, start, size):
        """Reject servers ignoring ranges and snapshots changed during download."""
        end = start + size - 1
        headers = {'Range': f'bytes={start}-{end}'}
        if self.etag:
            headers['If-Match'] = self.etag
        response = request(self.url, headers)
        if (response.status != 206 or response.headers.get('Content-Range')
                != f'bytes {start}-{end}/{self.length}'):
            response.close()
            raise GarSourceError('ГАР вернул неполный диапазон архива.')
        return response

    def read(self, size=-1):
        """Fetch only a bounded metadata range."""
        size = min(size if size >= 0 else self.length, self.length - self.position)
        if size <= 0:
            return b''
        if size > 4 * 1024 * 1024:
            raise GarSourceError('Превышен размер запроса метаданных ZIP.')
        with self.open_range(self.position, size) as response:
            data = response.read(size + 1)
        if len(data) != size:
            raise GarSourceError('Архив ГАР загружен не полностью.')
        self.position += size
        return data


def xml_rows(chunks, tag):
    """Parse bounded self-closing GAR records, including chunk boundary splits."""
    pattern = re.compile(rb'<' + tag.encode() + rb'\s[^>]*?/>')
    pending = b''
    for chunk in chunks:
        pending += chunk
        last = 0
        for match in pattern.finditer(pending):
            yield match.group()
            last = match.end()
        pending = pending[last:]
        if len(pending) > 2 * 1024 * 1024:
            raise GarSourceError('Неожиданный формат XML ГАР.')
    if pending.strip().split(b'>')[-1].strip():
        raise GarSourceError('XML ГАР оборван.')


class GarSource:
    """Cache validated regional extracts, never the 58 GB national archive."""

    def __init__(self, version, url, cache_directory, heartbeat=lambda: None):
        """Open one pinned snapshot and its version-specific cache directory."""
        if not re.fullmatch(r'\d{8}', version):
            raise GarSourceError('Неизвестная версия ГАР.')
        self.version = version
        self.directory = Path(cache_directory) / version
        self.directory.mkdir(parents=True, exist_ok=True)
        self.heartbeat = heartbeat
        self.remote = RemoteArchive(url)
        self.archive = zipfile.ZipFile(self.remote)
        self.entries = {entry.filename: entry for entry in self.archive.infolist()}
        self.types = {}

    def regions(self):
        """Use subjects in the official extract, excluding foreign Baikonur (99)."""
        return sorted({name[:2] for name in self.entries
                       if re.match(r'\d{2}/AS_ADDR_OBJ_\d', name)
                       and name[:2] != '99'})

    def member(self, prefix):
        matches = [entry for name, entry in self.entries.items()
                   if re.match(re.escape(prefix) + r'\d', name)]
        if len(matches) != 1:
            raise GarSourceError(f'В архиве отсутствует раздел {prefix}.')
        return matches[0]

    def chunks(self, entry):
        """Retry downloads atomically and verify decompression, size and CRC."""
        if entry.compress_type != zipfile.ZIP_DEFLATED:
            raise GarSourceError('Неизвестное сжатие архива ГАР.')
        path = self.directory / (entry.filename.replace('/', '_') + '.deflate')
        if not path.exists() or path.stat().st_size != entry.compress_size:
            partial = path.with_suffix('.part')
            self.remote.seek(entry.header_offset)
            header = self.remote.read(30)
            if header[:4] != b'PK\x03\x04':
                raise GarSourceError('Повреждён заголовок ZIP ГАР.')
            name_length, extra_length = struct.unpack('<HH', header[26:30])
            offset = entry.header_offset + 30 + name_length + extra_length
            for attempt in range(3):
                try:
                    with self.remote.open_range(offset, entry.compress_size) as response, partial.open('wb') as output:
                        remaining = entry.compress_size
                        while remaining:
                            data = response.read(min(1024 * 1024, remaining))
                            if not data:
                                raise GarSourceError('Загрузка раздела ГАР прервана.')
                            output.write(data)
                            remaining -= len(data)
                            self.heartbeat()
                    partial.replace(path)
                    break
                except (OSError, GarSourceError):
                    if attempt == 2:
                        raise
                    time.sleep(attempt + 1)
        decoder, checksum, length = zlib.decompressobj(-15), 0, 0
        try:
            with path.open('rb') as source:
                while compressed := source.read(64 * 1024):
                    data = decoder.decompress(compressed)
                    checksum = zlib.crc32(data, checksum)
                    length += len(data)
                    self.heartbeat()
                    yield data
            tail = decoder.flush()
            checksum = zlib.crc32(tail, checksum)
            length += len(tail)
            if tail:
                yield tail
            if not decoder.eof or checksum != entry.CRC or length != entry.file_size:
                raise GarSourceError('Контрольная сумма раздела ГАР не совпала.')
        except (zlib.error, GarSourceError):
            path.unlink(missing_ok=True)
            raise GarSourceError('Раздел ГАР повреждён; повторите импорт.')

    def load_types(self):
        """Keep historic abbreviations because current objects may still use them."""
        for raw in xml_rows(self.chunks(self.member('AS_ADDR_OBJ_TYPES_')), 'ADDRESSOBJECTTYPE'):
            row = ET.fromstring(raw).attrib
            self.types[(row['LEVEL'], row['SHORTNAME'])] = row['NAME']

    def extract_region(self, code):
        """Resolve administrative paths for every current city, village and settlement."""
        path = self.directory / f'{code}.json'
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        if not self.types:
            self.load_types()
        records = {}
        for raw in xml_rows(self.chunks(self.member(f'{code}/AS_ADDR_OBJ_')), 'OBJECT'):
            if b'ISACTUAL="1"' not in raw or b'ISACTIVE="1"' not in raw:
                continue
            row = ET.fromstring(raw).attrib
            if row['LEVEL'] not in {'1', '2', '5', '6'}:
                continue
            records[row['OBJECTID']] = {
                'id': row['OBJECTID'], 'guid': row['OBJECTGUID'], 'name': row['NAME'],
                'level': row['LEVEL'], 'type': row['TYPENAME'],
                'typeName': self.types.get((row['LEVEL'], row['TYPENAME']), row['TYPENAME']),
            }
        if not records:
            path.write_text('[]', encoding='utf-8')
            return []
        for raw in xml_rows(self.chunks(self.member(f'{code}/AS_ADM_HIERARCHY_')), 'ITEM'):
            identifier = re.search(rb' OBJECTID="(\d+)"', raw).group(1).decode()
            if identifier not in records or b'ISACTIVE="1"' not in raw:
                continue
            row = ET.fromstring(raw).attrib
            records[identifier]['path'] = row['PATH'].split('.')
        roots = [row for row in records.values() if row['level'] == '1']
        if not records:
            result = []
            path.write_text('[]', encoding='utf-8')
            return result
        if len(roots) != 1 or any('path' not in row for row in records.values()):
            raise GarSourceError(f'Неполная административная иерархия ГАР: {code}.')
        for row in records.values():
            ancestors = [identifier for identifier in row['path'][:-1] if identifier in records]
            row['parent'] = ancestors[-1] if ancestors else None
            row['region'] = roots[0]['id']
            if row['level'] != '1' and row['parent'] is None:
                raise GarSourceError(f'Не определён регион населённого пункта: {row["name"]}.')
        result = list(records.values())
        partial = path.with_suffix('.tmp')
        partial.write_text(json.dumps(result, ensure_ascii=False), encoding='utf-8')
        partial.replace(path)
        return result
