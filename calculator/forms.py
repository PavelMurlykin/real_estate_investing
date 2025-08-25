from django import forms
from datetime import datetime, date
import re


class MortgageForm(forms.Form):
    PROPERTY_COST = forms.DecimalField(
        label='Стоимость объекта, руб.',
        min_value=0,
        max_digits=15,
        decimal_places=2,
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
        label='Дата первоначального взноса (ДД.ММ.ГГГГ)',
        widget=forms.DateInput(attrs={
            'class': 'form-input',
            'type': 'text',
            'placeholder': 'ДД.ММ.ГГГГ'
        }),
        input_formats=['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'],
        initial=date.today  # Сегодняшняя дата по умолчанию
    )
    MORTGAGE_TERM = forms.IntegerField(  # Целое число
        label='Срок ипотеки, годы',
        min_value=1,
        max_value=50,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    ANNUAL_RATE = forms.DecimalField(
        label='Годовая ставка, %',
        min_value=0,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'})
    )
    HAS_GRACE_PERIOD = forms.ChoiceField(
        label='Наличие льготного периода',
        choices=[('нет', 'Нет'), ('да', 'Да')],
        widget=forms.RadioSelect,
        initial='нет'
    )
    GRACE_PERIOD_TERM = forms.IntegerField(  # Целое число
        label='Срок льготного периода, годы',
        min_value=0,
        max_value=50,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input'})
    )
    GRACE_PERIOD_RATE = forms.DecimalField(
        label='Годовая ставка на срок действия льготного периода, %',
        min_value=0,
        max_digits=5,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-input', 'step': '0.01'})
    )

    def clean_INITIAL_PAYMENT_DATE(self):
        date_str = self.cleaned_data['INITIAL_PAYMENT_DATE']
        if isinstance(date_str, str):
            try:
                date = datetime.strptime(date_str, '%d.%m.%Y').date()
                return date
            except ValueError:
                try:
                    date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    return date
                except ValueError:
                    raise forms.ValidationError('Неверный формат даты. Используйте ДД.ММ.ГГГГ')
        return date_str

    def clean(self):
        cleaned_data = super().clean()
        has_grace_period = cleaned_data.get('HAS_GRACE_PERIOD')
        grace_period_term = cleaned_data.get('GRACE_PERIOD_TERM')
        grace_period_rate = cleaned_data.get('GRACE_PERIOD_RATE')
        mortgage_term = cleaned_data.get('MORTGAGE_TERM')

        if has_grace_period == 'да':
            if grace_period_term is None:
                self.add_error('GRACE_PERIOD_TERM', 'Это поле обязательно при наличии льготного периода')
            if grace_period_rate is None:
                self.add_error('GRACE_PERIOD_RATE', 'Это поле обязательно при наличии льготного периода')

            if grace_period_term and mortgage_term and grace_period_term >= mortgage_term:
                self.add_error('GRACE_PERIOD_TERM', 'Срок льготного периода должен быть меньше общего срока ипотеки')

        return cleaned_data