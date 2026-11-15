"""Shared validation for API and fallback location imports."""

from django import forms

from .models import City, Region


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

    def clean(self):
        """Validate hierarchy before any external network or database writes."""
        cleaned = super().clean()
        dictionary = cleaned.get('dictionary')
        if dictionary == 'regions':
            if cleaned.get('regionId') or cleaned.get('cityId'):
                raise forms.ValidationError('Для регионов родитель не нужен.')
            return cleaned
        if dictionary not in ('cities', 'districts', 'metro'):
            return cleaned
        region = Region.objects.filter(pk=cleaned.get('regionId')).first()
        if region is None:
            self.add_error(
                'regionId', 'Выберите регион России.',
            )
            return cleaned
        cleaned['region'] = region
        if dictionary == 'cities':
            if cleaned.get('cityId'):
                self.add_error('cityId', 'Для городов выберите только регион.')
            return cleaned
        city = City.objects.filter(
            pk=cleaned.get('cityId'), region=region,
        ).first()
        if city is None:
            self.add_error(
                'cityId', 'Выберите город этого региона.',
            )
        else:
            cleaned['city'] = city
        return cleaned
