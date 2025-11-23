# calculation/forms.py
from django import forms

from property.models import Property


class CalculationForm(forms.Form):
    property = forms.ModelChoiceField(
        queryset=Property.objects.all(),
        widget=forms.Select(attrs={
            'class': 'form-control',
        }),
        label="Объект недвижимости",
        required=True
    )

    property_cost = forms.DecimalField(
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label="Стоимость объекта, руб.",
        required=True
    )
