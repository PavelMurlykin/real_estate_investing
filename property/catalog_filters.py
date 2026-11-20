"""Normalize fallback catalog filters without mixing canonical and legacy IDs."""

import json

from django import forms

from location.filter_forms import LocationFilterForm
from location.models import LocationCompatibilityEntry
from .location_form_fields import selected_identifier
from .models import RealEstateComplex, RealEstateComplexBuilding


def catalog_location_parameters(parameters):
    """Retain old city URLs while validating canonical IDs before ORM access."""
    result = {name: selected_identifier(parameters.get(name)) or '' for name in (
        'regionLocationId', 'districtLocationId', 'localityId', 'locationId',
    )}
    result['city'] = selected_identifier(
        parameters.get('filter_city') or parameters.get('cityId') or parameters.get('city'),
    ) or ''
    return result


def catalog_location_form(parameters, identifier='catalog_location'):
    """Show the explicit mapped locality for an old city URL when available."""
    initial = dict(parameters)
    if parameters.get('city') and not initial.get('localityId'):
        initial['localityId'] = LocationCompatibilityEntry.objects.filter(
            model_name='city', legacy_id=parameters['city'],
        ).values_list('location_id', flat=True).first() or ''
    return LocationFilterForm(initial, identifier)


def property_relation_filters(parameters):
    """Render selected project/building labels and search all other options remotely."""
    parent_fields = {
        'regionLocationId': 'catalog_location_regionLocationId',
        'districtLocationId': 'catalog_location_districtLocationId',
        'localityId': 'catalog_location_localityId',
        'locationId': 'catalog_location_locationId',
    }
    widgets = {}
    for name, model, dictionary, filters in (
        ('complex', RealEstateComplex, 'complexes', {
            **parent_fields, 'developerId': 'catalog_developer',
        }),
        ('building', RealEstateComplexBuilding, 'buildings', {
            **parent_fields, 'realEstateComplexId': 'catalog_complex',
        }),
    ):
        selected = selected_identifier(parameters.get(name))
        row = model.objects.filter(pk=selected).first() if selected else None
        label = row.name if name == 'complex' and row else row.number if row else ''
        widget = forms.Select(attrs={
            'id': f'catalog_{name}', 'class': 'form-select',
            'data-catalog-filter-control': '',
            'data-remote-options': f'/api/v1/catalog-options/{dictionary}/',
            'data-remote-filters': json.dumps(filters),
        }, choices=[('', 'Все')] + ([(row.pk, label)] if row else []))
        widgets[f'{name}_filter_widget'] = widget.render(f'filter_{name}', selected)
    return widgets
