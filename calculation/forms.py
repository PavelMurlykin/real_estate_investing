# calculation/forms.py
from django import forms

from property.models import Property

DISCOUNT_MARKUP_CHOICES = [
    ('discount', 'Скидка'),
    ('markup', 'Удорожание'),
]


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

    # Новые поля из модели MortgageCalculation
    initial_payment_percent = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label="Первоначальный взнос, %",
        required=True
    )

    initial_payment_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Дата первоначального взноса",
        required=True
    )

    mortgage_term = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        }),
        label="Срок ипотеки, годы",
        required=True
    )

    annual_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label="Годовая ставка, %",
        required=True
    )

    has_grace_period = forms.BooleanField(
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        label="Наличие льготного периода",
        required=False
    )

    grace_period_term = forms.IntegerField(
        widget=forms.NumberInput(attrs={
            'class': 'form-control'
        }),
        label="Срок льготного периода, годы",
        required=False
    )

    grace_period_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label="Годовая ставка на срок льготного периода, %",
        required=False
    )

    discount_markup_type = forms.ChoiceField(
        choices=DISCOUNT_MARKUP_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        label="Тип изменения цены",
        initial='discount'
    )

    discount_markup_value = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01'
        }),
        label="Значение изменения цены, %",
        initial=0
    )
