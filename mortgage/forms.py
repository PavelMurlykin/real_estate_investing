# mortgage/forms.py
from datetime import date, datetime

from django import forms

from property.models import Property


class MortgageForm(forms.Form):
    """Входные параметры для расчета ипотеки."""

    PROPERTY = forms.ModelChoiceField(
        queryset=Property.objects.all(),
        label='Объект недвижимости',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
                'id': 'id_PROPERTY',
                'onchange': 'updatePropertyCost()',
            }
        ),
    )

    PROPERTY_COST = forms.DecimalField(
        label='Базовая стоимость объекта, руб.',
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'step': '0.01',
                'id': 'property_cost_input',
                'oninput': 'handlePropertyCostChange()',
            }
        ),
    )

    DISCOUNT_MARKUP_TYPE = forms.ChoiceField(
        label='Корректировка цены',
        choices=[('discount', 'Скидка'), ('markup', 'Удорожание')],
        widget=forms.RadioSelect(
            attrs={'onchange': 'handleDiscountMarkupTypeChange()'}
        ),
        initial='discount',
    )

    DISCOUNT_MARKUP_VALUE = forms.DecimalField(
        label='Скидка, %',
        min_value=0,
        max_digits=5,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'step': '0.01',
                'id': 'discount_markup_percent',
                'oninput': 'handleDiscountMarkupPercentInput()',
            }
        ),
    )

    DISCOUNT_MARKUP_RUBLES = forms.DecimalField(
        label='Скидка, руб.',
        min_value=0,
        max_digits=15,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'step': '0.01',
                'id': 'discount_markup_rubles',
                'oninput': 'handleDiscountMarkupRublesInput()',
            }
        ),
    )

    DISCOUNT_MARKUP_SOURCE = forms.ChoiceField(
        choices=[('percent', 'percent'), ('rubles', 'rubles')],
        initial='percent',
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'discount_markup_source'}),
    )

    INITIAL_PAYMENT_PERCENT = forms.DecimalField(
        label='Первоначальный взнос, %',
        min_value=0,
        max_value=100,
        max_digits=5,
        decimal_places=2,
        initial=20,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'step': '0.01',
                'id': 'initial_payment_percent',
                'oninput': 'handleInitialPaymentPercentInput()',
            }
        ),
    )

    INITIAL_PAYMENT_RUBLES = forms.DecimalField(
        label='Первоначальный взнос, руб.',
        min_value=0,
        max_digits=15,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'step': '0.01',
                'id': 'initial_payment_rubles',
                'oninput': 'handleInitialPaymentRublesInput()',
            }
        ),
    )

    INITIAL_PAYMENT_SOURCE = forms.ChoiceField(
        choices=[('percent', 'percent'), ('rubles', 'rubles')],
        initial='percent',
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'initial_payment_source'}),
    )

    INITIAL_PAYMENT_DATE = forms.DateField(
        label='Дата первоначального взноса (ДД.ММ.ГГГГ)',
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date',
            },
            format='%Y-%m-%d',
        ),
        input_formats=['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'],
        initial=date.today,
    )

    MORTGAGE_TERM = forms.IntegerField(
        label='Срок ипотеки, годы',
        min_value=1,
        max_value=50,
        initial=30,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )

    ANNUAL_RATE = forms.DecimalField(
        label='Годовая ставка, %',
        min_value=0,
        max_digits=5,
        decimal_places=2,
        initial=15,
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'step': '0.01'}
        ),
    )

    HAS_GRACE_PERIOD = forms.ChoiceField(
        label='Наличие льготного периода',
        choices=[('no', 'Нет'), ('yes', 'Да')],
        widget=forms.RadioSelect(attrs={'onchange': 'toggleGracePeriod()'}),
        initial='no',
    )

    GRACE_PERIOD_TERM = forms.IntegerField(
        label='Срок льготного периода, годы',
        min_value=0,
        max_value=50,
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )

    GRACE_PERIOD_RATE = forms.DecimalField(
        label='Годовая ставка на срок действия льготного периода, %',
        min_value=0,
        max_digits=5,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'step': '0.01'}
        ),
    )

    def clean_INITIAL_PAYMENT_DATE(self):
        """Описание метода clean_INITIAL_PAYMENT_DATE.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        date_value = self.cleaned_data['INITIAL_PAYMENT_DATE']
        if isinstance(date_value, str):
            try:
                return datetime.strptime(date_value, '%d.%m.%Y').date()
            except ValueError:
                try:
                    return datetime.strptime(date_value, '%Y-%m-%d').date()
                except ValueError as exc:
                    raise forms.ValidationError(
                        'Неверный формат даты. Используйте ДД.ММ.ГГГГ'
                    ) from exc
        return date_value

    def clean(self):
        """Описание метода clean.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        cleaned_data = super().clean()
        has_grace_period = cleaned_data.get('HAS_GRACE_PERIOD')
        grace_period_term = cleaned_data.get('GRACE_PERIOD_TERM')
        grace_period_rate = cleaned_data.get('GRACE_PERIOD_RATE')
        mortgage_term = cleaned_data.get('MORTGAGE_TERM')

        if has_grace_period == 'yes':
            if grace_period_term is None:
                self.add_error(
                    'GRACE_PERIOD_TERM',
                    'Это поле обязательно при наличии льготного периода',
                )
            if grace_period_rate is None:
                self.add_error(
                    'GRACE_PERIOD_RATE',
                    'Это поле обязательно при наличии льготного периода',
                )

            if (
                grace_period_term
                and mortgage_term
                and grace_period_term >= mortgage_term
            ):
                self.add_error(
                    'GRACE_PERIOD_TERM',
                    (
                        'Срок льготного периода должен быть меньше общего '
                        'срока ипотеки'
                    ),
                )

        return cleaned_data
