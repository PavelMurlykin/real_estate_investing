from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from .models import (
    City,
    Developer,
    Property,
    RealEstateComplex,
    RealEstateComplexBuilding,
)


class PropertyFilterForm(forms.Form):
    city = forms.ModelChoiceField(
        queryset=City.objects.all(),
        required=False,
        empty_label="Все города",
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Город"
    )
    developer = forms.ModelChoiceField(
        queryset=Developer.objects.all(),
        required=False,
        empty_label="Все застройщики",
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Застройщик"
    )
    complex = forms.ModelChoiceField(
        queryset=RealEstateComplex.objects.all(),
        required=False,
        empty_label="Все ЖК",
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Жилой комплекс"
    )


class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = [
            'apartment_number',
            'building',
            'decoration',
            'layout',
            'area',
            'floor',
            'property_cost',
        ]
        widgets = {
            'apartment_number': forms.TextInput(attrs={'class': 'form-control'}),
            'building': forms.Select(attrs={'class': 'form-control'}),
            'decoration': forms.Select(attrs={'class': 'form-control'}),
            'layout': forms.Select(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'floor': forms.NumberInput(attrs={'class': 'form-control'}),
            'property_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }
        labels = {
            'apartment_number': 'Номер квартиры',
            'building': 'Корпус',
            'decoration': 'Отделка',
            'layout': 'Планировка',
            'area': 'Площадь, м2',
            'floor': 'Этаж',
            'property_cost': 'Стоимость, руб.',
        }


class DeveloperForm(forms.ModelForm):
    class Meta:
        model = Developer
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RealEstateComplexForm(forms.ModelForm):
    class Meta:
        model = RealEstateComplex
        fields = [
            'name',
            'description',
            'map_link',
            'presentation_link',
            'developer',
            'district',
            'real_estate_class',
            'real_estate_type',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'map_link': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'presentation_link': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'developer': forms.Select(attrs={'class': 'form-control'}),
            'district': forms.Select(attrs={'class': 'form-control'}),
            'real_estate_class': forms.Select(attrs={'class': 'form-control'}),
            'real_estate_type': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RealEstateComplexBuildingForm(forms.ModelForm):
    class Meta:
        model = RealEstateComplexBuilding
        fields = [
            'number',
            'address',
            'commissioning_date',
            'key_handover_date',
            'is_active',
        ]
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'commissioning_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'key_handover_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class BaseRealEstateComplexBuildingInlineFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()

        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue

            if form.cleaned_data.get('DELETE') and form.instance.pk and form.instance.property_set.exists():
                form.add_error(
                    None,
                    'Нельзя удалить корпус, к которому привязаны объекты недвижимости.',
                )


RealEstateComplexBuildingFormSet = inlineformset_factory(
    RealEstateComplex,
    RealEstateComplexBuilding,
    form=RealEstateComplexBuildingForm,
    formset=BaseRealEstateComplexBuildingInlineFormSet,
    extra=1,
    can_delete=True,
)
