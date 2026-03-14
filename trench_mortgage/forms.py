from datetime import date, datetime

from django import forms

from property.models import Property


class TrenchMortgageForm(forms.Form):
    """Описание класса TrenchMortgageForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

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
                'oninput': 'updateFinalPropertyCost()',
            }
        ),
    )

    DISCOUNT_MARKUP_TYPE = forms.ChoiceField(
        choices=[('discount', 'Скидка'), ('markup', 'Удорожание')],
        label='Тип изменения цены',
        widget=forms.RadioSelect(
            attrs={'onchange': 'updateFinalPropertyCost()'}
        ),
        initial='discount',
    )

    DISCOUNT_MARKUP_VALUE = forms.DecimalField(
        label='Значение, %',
        min_value=0,
        max_digits=5,
        decimal_places=2,
        required=False,
        initial=0,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'step': '0.01',
                'oninput': 'updateFinalPropertyCost()',
            }
        ),
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
                'oninput': 'updateInitialPaymentRubles()',
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
                'oninput': 'updateInitialPaymentPercent()',
            }
        ),
    )

    INITIAL_PAYMENT_DATE = forms.DateField(
        label='Дата первоначального взноса (ДД.ММ.ГГГГ)',
        initial=date.today,
        widget=forms.DateInput(
            attrs={
                'class': 'form-control',
                'type': 'date',
            },
            format='%Y-%m-%d',
        ),
        input_formats=['%d.%m.%Y', '%Y-%m-%d', '%d/%m/%Y'],
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

    TRENCH_COUNT = forms.TypedChoiceField(
        label='Количество траншей',
        choices=[(i, str(i)) for i in range(1, 6)],
        coerce=int,
        empty_value=1,
        initial=1,
        widget=forms.Select(
            attrs={'class': 'form-select', 'id': 'id_TRENCH_COUNT'}
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
        if cleaned_data.get('DISCOUNT_MARKUP_VALUE') is None:
            cleaned_data['DISCOUNT_MARKUP_VALUE'] = 0
        return cleaned_data
