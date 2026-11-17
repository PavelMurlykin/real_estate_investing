"""Canonical territory controls shared by both native calculators."""

import json
from types import SimpleNamespace

from django import forms

from location.models import LegacyLocationMapping
from property.location_form_fields import configure_property_location_fields
from property.location_filters import apply_location_scopes
from property.models import RealEstateComplexBuilding


LOCATION_FIELDS = {
    'region_location': 'OBJECT_REGION_LOCATION',
    'district_location': 'OBJECT_DISTRICT_LOCATION',
    'locality': 'OBJECT_LOCALITY',
    'developer': 'OBJECT_DEVELOPER',
    'complex': 'OBJECT_COMPLEX',
    'building': 'OBJECT_BUILDING',
}


def configure_calculator_locations(form):
    """Reuse bounded property selectors without changing legacy POST names."""
    adapter = SimpleNamespace(
        fields={name: form.fields[field] for name, field in LOCATION_FIELDS.items()
                if field in form.fields},
        initial={name: form.initial[field] for name, field in LOCATION_FIELDS.items()
                 if field in form.initial},
        data={name: form.data[field] for name, field in LOCATION_FIELDS.items()
              if field in form.data},
        is_bound=form.is_bound,
    )
    identifiers = {
        'id_developer': 'developer-select', 'id_complex': 'complex-select',
        'id_building': 'id_building',
        **{f'id_{name}': f'id_{field}' for name, field in LOCATION_FIELDS.items()
           if name in {'region_location', 'district_location', 'locality'}},
    }
    configure_property_location_fields(adapter)
    for name, field_name in LOCATION_FIELDS.items():
        field = adapter.fields[name]
        attributes = field.widget.attrs
        attributes['id'] = identifiers[f'id_{name}']
        filters = json.loads(attributes['data-remote-filters'])
        attributes['data-remote-filters'] = json.dumps({
            parameter: identifiers[parent] for parameter, parent in filters.items()
        })
        if attributes.get('data-required-parent'):
            attributes['data-required-parent'] = identifiers[attributes['data-required-parent']]
        form.fields[field_name] = field
        if form.is_bound and name in adapter.data:
            form.data[field_name] = adapter.data[name]
        elif name in adapter.initial:
            form.initial[field_name] = adapter.initial[name]
    for name in ['OBJECT_CITY', 'OBJECT_DISTRICT']:
        form.fields[name].widget = forms.HiddenInput()


def validate_calculator_locations(form, cleaned_data):
    """Validate every submitted scope against the effective building territory."""
    selected_property = cleaned_data.get('PROPERTY')
    building = cleaned_data.get('OBJECT_BUILDING')
    if selected_property:
        building = selected_property.building
    scopes = {
        parameter: cleaned_data[field].pk
        for field, parameter in [
            ('OBJECT_REGION_LOCATION', 'regionLocationId'),
            ('OBJECT_DISTRICT_LOCATION', 'districtLocationId'),
            ('OBJECT_LOCALITY', 'localityId'),
        ] if cleaned_data.get(field)
    }
    if building and scopes and not apply_location_scopes(
        RealEstateComplexBuilding.objects.filter(pk=building.pk), scopes,
        buildings=True, prefix='',
    ).exists():
        form.add_error('OBJECT_BUILDING', 'Корпус не относится к выбранной территории.')
    if building:
        complex_object = building.real_estate_complex
        for field_name, expected in [
            ('OBJECT_COMPLEX', complex_object.pk),
            ('OBJECT_DEVELOPER', complex_object.developer_id),
        ]:
            if cleaned_data.get(field_name) and cleaned_data[field_name].pk != expected:
                form.add_error(field_name, 'Выбранная запись не соответствует корпусу.')


def financial_region_identifier(region_location_id):
    """Resolve a canonical region to its unique legacy financial identifier."""
    identifiers = list(LegacyLocationMapping.objects.filter(
        model_name='region', location_id=region_location_id,
    ).values_list('legacy_id', flat=True).distinct()[:2])
    return identifiers[0] if len(identifiers) == 1 else None
