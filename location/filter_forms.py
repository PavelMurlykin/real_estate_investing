"""Render bounded canonical location controls for fallback catalog pages."""

import json

from django import forms

from property.location_form_fields import selected_identifier
from .models import Location
from .presentation import geographic_label


class LocationFilterForm(forms.Form):
    """Search geography remotely and render only the selected values initially."""

    regionLocationId = forms.ModelChoiceField(
        label='Регион', queryset=Location.objects.none(), required=False,
    )
    districtLocationId = forms.ModelChoiceField(
        label='Административный район', queryset=Location.objects.none(), required=False,
    )
    localityId = forms.ModelChoiceField(
        label='Населённый пункт', queryset=Location.objects.none(), required=False,
    )

    def __init__(self, parameters, identifier):
        """Keep the full Russian catalog outside of the HTML payload."""
        super().__init__(initial=parameters, auto_id=f'{identifier}_%s')
        identifiers = [selected_identifier(parameters.get(name)) for name in self.fields]
        locations = {location.pk: location for location in Location.objects.filter(
            pk__in=[value for value in identifiers if value],
        ).select_related('parent', 'region', 'location_type')}
        for name, category, filters in (
            ('regionLocationId', 'region', {}),
            ('districtLocationId', 'district', {'regionId': f'{identifier}_regionLocationId'}),
            ('localityId', 'locality', {
                'regionId': f'{identifier}_regionLocationId',
                'relatedToId': f'{identifier}_districtLocationId',
            }),
        ):
            field = self.fields[name]
            field.queryset = Location.objects.all()
            field.widget = forms.Select(attrs={
                'class': 'form-select', 'data-catalog-filter-control': '',
                'data-remote-options': f'/api/v1/catalog-options/locations/?category={category}',
                'data-remote-filters': json.dumps(filters),
            })
            location = locations.get(selected_identifier(parameters.get(name)))
            field.widget.choices = [('', 'Все')] + (
                [(location.pk, geographic_label(location))] if location else []
            )
