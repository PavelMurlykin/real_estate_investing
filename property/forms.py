from django import forms
from .models import Property

class PropertyForm(forms.ModelForm):
    class Meta:
        model = Property
        fields = '__all__'
        widgets = {
            'developer': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.Select(attrs={'class': 'form-control'}),
            'complex_name': forms.TextInput(attrs={'class': 'form-control'}),
            'complex_class': forms.Select(attrs={'class': 'form-control'}),
            'building': forms.TextInput(attrs={'class': 'form-control'}),
            'apartment_number': forms.TextInput(attrs={'class': 'form-control'}),
            'layout': forms.TextInput(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'floor': forms.NumberInput(attrs={'class': 'form-control'}),
            'property_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }