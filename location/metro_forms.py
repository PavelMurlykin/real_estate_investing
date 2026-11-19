"""Canonical metro editors for the fallback catalog and Django admin."""

from django import forms

from property.location_context import locality_filter

from .models import Location, Metro, MetroLine, MetroSystem
from .presentation import geographic_label


class MetroGeographyForm(forms.ModelForm):
    """Offer a bounded locality selector while validating the complete catalog."""

    def __init__(self, *args, **kwargs):
        """Keep the selected locality even outside the first page."""
        super().__init__(*args, **kwargs)
        if 'location' not in self.fields:
            return
        field = self.fields['location']
        field.label = 'Населённый пункт станции' if self._meta.model is Metro else 'Центр системы'
        field.queryset = Location.objects.filter(locality_filter()).select_related(
            'location_type', 'parent', 'region',
        )
        if field.widget.__class__.__module__.startswith('django.contrib.admin'):
            return
        value = self.data.get('location') if self.is_bound else self.initial.get('location')
        choices = {row.pk: row for row in field.queryset[:50]}
        if str(value or '').isdecimal() and len(str(value)) <= 19:
            choices.update({row.pk: row for row in field.queryset.filter(pk=value)})
        field.widget = forms.Select(attrs={
            'class': 'form-control',
            'data-remote-options': '/api/v1/catalog-options/locations/?category=locality',
        })
        field.widget.choices = [('', 'Не указано')] + [
            (row.pk, geographic_label(row)) for row in choices.values()
        ]


class MetroSystemForm(MetroGeographyForm):
    """Maintain the network center without creating a legacy city."""

    class Meta:
        """Whitelist canonical system fields."""

        model = MetroSystem
        fields = ('name', 'location', 'is_active')

    def clean_location(self):
        """Require an explicit center for new and edited systems."""
        value = self.cleaned_data.get('location')
        if value is None:
            raise forms.ValidationError('Выберите центр системы.')
        return value


class MetroLineForm(forms.ModelForm):
    """Maintain line identity and color in an operating network."""

    class Meta:
        """Keep legacy city references out of new writes."""

        model = MetroLine
        fields = ('line', 'line_color', 'system', 'is_active')

    def clean_system(self):
        """Require a network and prevent moving a line with stations."""
        system = self.cleaned_data.get('system')
        if system is None:
            raise forms.ValidationError('Выберите систему метро.')
        if self.instance.pk and system.pk != self.instance.system_id:
            if self.instance.metro_set.exists() or self.instance.stations.exists():
                raise forms.ValidationError('У линии есть станции. Сохраните её систему.')
        return system


class MetroForm(MetroGeographyForm):
    """Preserve a primary line and all memberships across station edits."""

    class Meta:
        """Expose geography independently of network membership."""

        model = Metro
        fields = ('station', 'metro_line', 'lines', 'location', 'location_is_inferred', 'is_active')

    def __init__(self, *args, **kwargs):
        """Preload network labels for both primary and additional lines."""
        super().__init__(*args, **kwargs)
        for name in ('metro_line', 'lines'):
            if name in self.fields:
                self.fields[name].queryset = MetroLine.objects.select_related('system')

    def clean(self):
        """Validate station lines without restricting nearby real estate."""
        cleaned = super().clean()
        primary = cleaned.get('metro_line')
        lines = list(cleaned.get('lines', []))
        if primary:
            if any(line.system_id != primary.system_id for line in lines):
                self.add_error('lines', 'Все линии станции должны относиться к одной системе.')
            cleaned['lines'] = list({line.pk: line for line in [*lines, primary]}.values())
        if 'location' in self.fields and not cleaned.get('location_is_inferred') and not cleaned.get('location'):
            self.add_error('location', 'Укажите населённый пункт станции.')
        return cleaned
