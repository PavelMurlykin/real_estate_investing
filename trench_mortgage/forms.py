from django import forms
from .models import TrenchMortgageCalculation, Trench
from mortgage.models import Property

class TrenchMortgageForm(forms.Form):
    PROPERTY = forms.ModelChoiceField(
        queryset=Property.objects.all(),
        label="Выберите объект",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    DISCOUNT_MARKUP_TYPE = forms.ChoiceField(
        choices=[('discount', 'Скидка'), ('markup', 'Удорожание')],
        label='Тип изменения цены',
        widget=forms.RadioSelect,
        initial='discount'
    )
    DISCOUNT_MARKUP_VALUE = forms.DecimalField(
        label='Значение, %',
        min_value=0,
        max_digits=5,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'})
    )
    INITIAL_PAYMENT_PERCENT = forms.DecimalField(
        label='Первоначальный взнос, %',
        min_value=0,
        max_value=100,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'})
    )
    INITIAL_PAYMENT_DATE = forms.DateField(
        label='Дата первоначального взноса',
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )
    MORTGAGE_TERM = forms.IntegerField(
        label='Срок кредита, лет',
        min_value=1,
        max_value=50,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    TRENCH_COUNT = forms.IntegerField(
        label='Количество траншей',
        min_value=1,
        max_value=10,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )

class TrenchForm(forms.Form):
    trench_date = forms.DateField(
        label='Дата транша',
        widget=forms.DateInput(attrs={'class': 'form-input', 'type': 'date'})
    )
    trench_percent = forms.DecimalField(
        label='Сумма транша, %',
        min_value=0,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'})
    )
    annual_rate = forms.DecimalField(
        label='Годовая ставка, %',
        min_value=0,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'})
    )