from django import forms
from .models import Property, Developer, RealEstateComplex, RealEstateComplexBuilding, ApartmentLayout, ApartmentDecoration, City

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
            'apartment_number', 'building', 'decoration', 'layout',
            'area', 'floor', 'property_cost'
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
            'area': 'Площадь, м²',
            'floor': 'Этаж',
            'property_cost': 'Стоимость, руб.',
        }
