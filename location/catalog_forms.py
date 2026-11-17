"""Bounded native editors for canonical administrative location dictionaries."""

from django import forms

from .models import Location, LocationType
from .presentation import geographic_label


class LocationCatalogForm(forms.Form):
    """Validate the same canonical fields as the API without loading Russia's tree."""

    name = forms.CharField(label='Название', max_length=255)
    typeId = forms.ModelChoiceField(label='Тип', queryset=LocationType.objects.none())
    parentId = forms.ModelChoiceField(
        label='Родительская территория', queryset=Location.objects.all(), required=False,
    )
    isActive = forms.BooleanField(label='Активно', required=False, initial=True)

    def __init__(self, category, data=None, instance=None):
        """Load only the selected parent and the small type dictionary."""
        initial = {
            'name': instance.name, 'typeId': instance.location_type_id,
            'parentId': instance.parent_id, 'isActive': instance.is_active,
        } if instance else {'isActive': True}
        super().__init__(data=data, initial=initial)
        self.fields['typeId'].queryset = LocationType.objects.filter(
            category=instance.location_type.category if instance else category,
        ).order_by('name', 'pk')
        if category == 'region' or (
            instance and instance.location_type.category == 'region'
        ):
            self.fields['parentId'].widget = forms.HiddenInput()
        else:
            from property.location_form_fields import selected_identifier
            identifier = selected_identifier((data or initial).get('parentId'))
            parent = Location.objects.select_related(
                'parent', 'region', 'location_type',
            ).filter(pk=identifier).first() if identifier else None
            self.fields['parentId'].widget = forms.Select(attrs={
                'class': 'form-select', 'data-remote-options': '/api/v1/catalog-options/locations/',
            }, choices=[('', 'Выберите территорию')] + (
                [(parent.pk, geographic_label(parent))] if parent else []
            ))
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                'class', 'form-check-input'
                if isinstance(field.widget, forms.CheckboxInput) else 'form-control',
            )

    def service_values(self):
        """Translate form names into the shared service contract."""
        return {
            'name': self.cleaned_data['name'], 'location_type': self.cleaned_data['typeId'],
            'parent': self.cleaned_data['parentId'], 'is_active': self.cleaned_data['isActive'],
        }


class LocationCatalogFilterForm(forms.Form):
    """Reject invalid IDs and ordering before ORM filtering."""

    q = forms.CharField(required=False, max_length=255, label='Поиск')
    regionId = forms.IntegerField(
        required=False, min_value=1, max_value=9223372036854775807, label='Регион',
    )
    ancestorId = forms.IntegerField(
        required=False, min_value=1, max_value=9223372036854775807,
        label='Административный район',
    )
    typeId = forms.IntegerField(required=False, min_value=1, max_value=9223372036854775807)
    legacyRegionId = forms.IntegerField(required=False, min_value=1, max_value=9223372036854775807)
    status = forms.ChoiceField(required=False, choices=[
        ('', 'Все'), ('active', 'Активные'), ('inactive', 'Неактивные'),
    ])
    ordering = forms.ChoiceField(required=False, choices=[
        ('', 'По названию'), ('name', 'Название: А–Я'), ('-name', 'Название: Я–А'),
        ('region', 'По региону'), ('-region', 'Регион: Я–А'),
        ('type', 'По типу'), ('-type', 'Тип: Я–А'),
    ])
