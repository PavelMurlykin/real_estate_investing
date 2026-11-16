"""Shared display labels for canonical geographic choices."""


def geographic_label(location):
    """Disambiguate homonyms with type, parent and subject."""
    parts = [f'{location.location_type.abbreviation} {location.name}'.strip()]
    if location.parent_id and location.parent_id != location.region_id:
        parts.append(location.parent.name)
    if location.region_id and location.region_id != location.pk:
        parts.append(location.region.name)
    return ' · '.join(parts)
