"""Shared validation for API and fallback location imports."""

from django import forms

from .legacy_catalog import LegacyImportScope, legacy_catalog
from .metro_geography import legacy_metro_city
from .models import MetroSystem


class LocationImportForm(forms.Form):
    """Validate selected parents before the source verifies Russian scope."""

    dictionary = forms.ChoiceField(label='Справочник', choices=(
        ('regions', 'Регионы России'),
        ('cities', 'Города региона'),
        ('districts', 'Районы города'),
        ('metro', 'Метро города'),
    ))
    regionId = forms.IntegerField(label='Регион', required=False, min_value=1)
    cityId = forms.IntegerField(label='Город', required=False, min_value=1)
    systemId = forms.ModelChoiceField(
        label='Система метро', required=False,
        queryset=MetroSystem.objects.select_related('location').order_by('name'),
    )

    def clean(self):
        """Validate hierarchy before any external network or database writes."""
        cleaned = super().clean()
        dictionary = cleaned.get('dictionary')
        if dictionary == 'metro' and cleaned.get('systemId'):
            if cleaned.get('regionId') or cleaned.get('cityId'):
                raise forms.ValidationError('Для метро выберите только систему.')
            cleaned['system'] = cleaned['systemId']
            return cleaned
        if cleaned.get('systemId'):
            self.add_error('systemId', 'Система доступна только для импорта метро.')
        if dictionary == 'metro':
            if not cleaned.get('regionId'):
                self.add_error('regionId', 'Выберите регион России.')
            else:
                reference = legacy_metro_city(cleaned['regionId'], cleaned.get('cityId'))
                if reference is None:
                    self.add_error('cityId', 'Выберите город этого региона.')
                else:
                    cleaned['legacy_metro_city'] = reference
            return cleaned
        if dictionary == 'regions':
            if cleaned.get('regionId') or cleaned.get('cityId'):
                raise forms.ValidationError('Для регионов родитель не нужен.')
            return cleaned
        if dictionary not in ('cities', 'districts'):
            return cleaned
        region_id = cleaned.get('regionId')
        region = legacy_catalog('region').filter(legacy_id=region_id).first()
        if region is None:
            self.add_error(
                'regionId', 'Выберите регион России.',
            )
            return cleaned
        cleaned['region'] = LegacyImportScope.from_mapping(region)
        if dictionary == 'cities':
            if cleaned.get('cityId'):
                self.add_error('cityId', 'Для городов выберите только регион.')
            return cleaned
        city_id = cleaned.get('cityId')
        city = legacy_catalog('city').filter(legacy_id=city_id, legacy_region_id=region_id).first()
        if city is None:
            self.add_error(
                'cityId', 'Выберите город этого региона.',
            )
        else:
            cleaned['city'] = LegacyImportScope.from_mapping(city)
        return cleaned
