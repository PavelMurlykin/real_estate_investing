"""Resolve imported metro against operating networks, retaining all memberships."""

from core.json_import import JsonImportError
from location.models import Metro, MetroLine, MetroSystem
from location.open_data import location_key


class ImportMetroResolver:
    """Preload the small Russian metro catalog once for the whole JSON file."""

    def __init__(self, locations):
        """Defer metro queries when the input has no station rows."""
        self.locations = locations
        self.systems = None
        self.lines = None
        self.stations = None

    def _load(self):
        """Load network centers and memberships without per-station reads."""
        if self.systems is not None:
            return
        self.systems = list(MetroSystem.objects.select_related('location'))
        self.lines = list(MetroLine.objects.select_related('system'))
        self.stations = list(Metro.objects.select_related('metro_line').prefetch_related('lines'))
        self.memberships = {station.pk: {station.metro_line_id, *(line.pk for line in station.lines.all())}
                            for station in self.stations}

    def _system(self, row):
        """Resolve an explicitly selected network without creating a city."""
        if 'system_id' in row:
            matches = [system for system in self.systems if system.pk == row['system_id']]
        else:
            center = self.locations.reference(row['system_location'])
            matches = [system for system in self.systems if system.location_id == center.pk]
        if len(matches) != 1 or not matches[0].location_id:
            raise JsonImportError('Система метро не найдена однозначно или не имеет центра. Проверьте справочник метро.')
        return matches[0]

    def _memberships(self, station):
        """Include the preserved primary line even for an old unmigrated row."""
        return self.memberships[station.pk]

    def resolve(self, row, territory):
        """Adopt existing stations or add natural keys inside a known network."""
        self._load()
        if 'station_id' in row or 'station_source_identifier' in row:
            matches = [station for station in self.stations if (
                station.pk == row['station_id'] if 'station_id' in row
                else station.source_identifier == row['station_source_identifier']
            )]
            if len(matches) != 1:
                raise JsonImportError('Станция метро по указанной ссылке не найдена.')
            return matches[0]

        explicit = bool({'system_id', 'system_location'}.intersection(row))
        system = self._system(row) if explicit else None
        lines = [line for line in self.lines if location_key(line.line, 'line') == location_key(row['line'], 'line')
                 and (system is None or line.system_id == system.pk)]
        line_identifiers = {line.pk for line in lines}
        stations = [station for station in self.stations
                    if location_key(station.station) == location_key(row['station'])
                    and self._memberships(station).intersection(line_identifiers)]
        regional_systems = [candidate for candidate in self.systems
                            if candidate.location_id and candidate.location.region_id == territory.locality.region_id]
        regional_identifiers = {candidate.pk for candidate in regional_systems}
        if not explicit and len(stations) > 1:
            regional_lines = {line.pk for line in lines if line.system_id in regional_identifiers}
            stations = [station for station in stations if self._memberships(station).intersection(regional_lines)]
        if len(stations) == 1:
            return stations[0]
        if len(stations) > 1:
            raise JsonImportError('Неоднозначная станция метро. Укажите station_id или систему в версии 2.')

        if not explicit:
            regional_lines = [line for line in lines if line.system_id in regional_identifiers]
            if regional_lines:
                lines = regional_lines
            if len(lines) == 1:
                system = next((candidate for candidate in self.systems if candidate.pk == lines[0].system_id), None)
            elif len(lines) == 0 and len(regional_systems) == 1:
                system = regional_systems[0]
            else:
                raise JsonImportError('Система метро старого файла неоднозначна. Выберите систему в версии 2.')
        if system is None or not system.location_id or len(lines) > 1:
            raise JsonImportError('Проверьте систему и линию в справочнике метро.')
        if lines:
            line = lines[0]
        else:
            if 'color' not in row:
                raise JsonImportError('Для новой линии метро укажите color в формате #RRGGBB.')
            line = MetroLine.objects.create(line=row['line'], line_color=row['color'], system=system)
            self.lines.append(line)
        station = Metro.objects.create(station=row['station'], metro_line=line)
        station.lines.add(line)
        # Keep the in-memory index current for following rows in the same file.
        self.memberships[station.pk] = {line.pk}
        self.stations.append(station)
        return station
