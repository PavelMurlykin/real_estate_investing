"""Bound canonical search controls without adding geography to apartments."""

import json

from django import forms
from django.db.models import Q

from location.models import Location
from location.presentation import geographic_label
from .form_fields import get_developers_with_company_groups_queryset
from .location_context import building_geography_prefetch, geography_prefetch, locality_filter
from .location_filters import apply_location_scopes
from .models import Developer, RealEstateComplex, RealEstateComplexBuilding


def catalog_label(instance):
    """Use the same labels as public searchable catalog options."""
    if isinstance(instance, Location):
        return geographic_label(instance)
    if isinstance(instance, Developer):
        return instance.get_display_name_with_company_group()
    if isinstance(instance, RealEstateComplexBuilding):
        return instance.number
    return instance.name


def selected_identifier(value):
    """Bound primary keys before using submitted helper values in queries."""
    text = str(value or '')
    return int(text) if len(text) <= 19 and text.isdecimal() and 0 < int(text) <= 9223372036854775807 else None


def configure_property_location_fields(form):
    """Initialize optional filters from effective building geography and page choices."""
    building_id = selected_identifier(
        form.data.get('building') if form.is_bound else form.initial.get('building'),
    )
    building = RealEstateComplexBuilding.objects.select_related(
        'real_estate_complex',
    ).prefetch_related(
        geography_prefetch('real_estate_complex__'), building_geography_prefetch(),
    ).filter(pk=building_id).first() if building_id else None
    defaults = {}
    if building:
        geography = building.geography
        defaults = {
            'region_location': geography.region_location_id,
            'district_location': geography.district_location_id,
            'locality': geography.locality_id,
            'developer': building.real_estate_complex.developer_id,
            'complex': building.real_estate_complex_id,
        }
    if form.is_bound:
        form.data = form.data.copy()
        for name, value in defaults.items():
            if name not in form.data:
                form.data[name] = value or ''
    else:
        form.initial.update(defaults)
    values = {
        name: selected_identifier(form.data.get(name) if form.is_bound else form.initial.get(name))
        for name in ['region_location', 'district_location', 'locality', 'developer', 'complex']
    }
    scopes = {parameter: values[name] for name, parameter in [
        ('region_location', 'regionLocationId'), ('district_location', 'districtLocationId'),
        ('locality', 'localityId'),
    ]}
    locations = Location.objects.select_related('location_type', 'parent', 'region').order_by('name', 'pk')
    definitions = [
        ('region_location', 'Регион', locations.filter(location_type__category='region'),
         'locations/?category=region', {}),
        ('district_location', 'Административный район', locations.filter(location_type__category='district'),
         'locations/?category=district', {'regionId': 'id_region_location'}),
        ('locality', 'Населённый пункт', locations.filter(locality_filter()),
         'locations/?category=locality', {'regionId': 'id_region_location', 'relatedToId': 'id_district_location'}),
        ('developer', 'Застройщик', get_developers_with_company_groups_queryset(), 'developers/', {}),
        ('complex', 'Жилой комплекс', RealEstateComplex.objects.order_by('name', 'pk'),
         'complexes/', {'regionLocationId': 'id_region_location', 'districtLocationId': 'id_district_location',
                        'localityId': 'id_locality', 'developerId': 'id_developer'}),
        ('building', 'Корпус', form.fields['building'].queryset.order_by('number', 'pk'),
         'buildings/', {'regionLocationId': 'id_region_location', 'districtLocationId': 'id_district_location',
                       'localityId': 'id_locality', 'realEstateComplexId': 'id_complex'}),
    ]
    for name, label, queryset, endpoint, filters in definitions:
        field = form.fields.get(name) or forms.ModelChoiceField(queryset=queryset, required=False, label=label)
        form.fields[name] = field
        selected = building_id if name == 'building' else values[name]
        choices = queryset
        if name in {'district_location', 'locality'} and values['region_location']:
            choices = choices.filter(region_id=values['region_location'])
        if name == 'locality' and values['district_location']:
            choices = choices.filter(
                Q(ancestor_links__ancestor_id=values['district_location'])
                | Q(descendant_links__descendant_id=values['district_location']),
            ).distinct()
        if name == 'complex':
            choices = apply_location_scopes(choices, scopes).filter(developer_id=values['developer'])
        if name == 'building':
            choices = apply_location_scopes(choices, scopes, buildings=True, prefix='').filter(
                real_estate_complex_id=values['complex'],
            )
        items = {item.pk: item for item in choices[:50]}
        if selected and selected not in items:
            items.update({item.pk: item for item in queryset.filter(pk=selected)})
        field.widget = forms.Select(attrs={
            'class': 'form-control', 'data-searchable-select': '',
            'data-location-field': name, 'data-remote-options': f'/api/v1/catalog-options/{endpoint}',
            'data-remote-filters': json.dumps(filters),
        })
        field.widget.choices = [('', 'Не выбрано')] + [(item.pk, catalog_label(item)) for item in items.values()]
        if name in {'complex', 'building'}:
            parent = 'developer' if name == 'complex' else 'complex'
            field.widget.attrs['data-required-parent'] = f'id_{parent}'
            if not values[parent]:
                field.widget.attrs['disabled'] = True
