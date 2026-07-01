# mortgage/forms.py
from datetime import date, datetime

from django import forms

from location.models import City, District
from property.form_fields import (
    DeveloperModelChoiceField,
    get_developers_with_company_groups_queryset,
)
from property.models import (
    ApartmentDecoration,
    ApartmentLayout,
    Property,
    RealEstateComplex,
    RealEstateComplexBuilding,
)


MANUAL_PROPERTY_FIELD_NAMES = (
    'OBJECT_CITY',
    'OBJECT_DISTRICT',
    'OBJECT_DEVELOPER',
    'OBJECT_COMPLEX',
    'OBJECT_BUILDING',
    'OBJECT_APARTMENT_NUMBER',
    'OBJECT_AREA',
    'OBJECT_LAYOUT',
    'OBJECT_FLOOR',
    'OBJECT_DECORATION',
)


class MortgageForm(forms.Form):
    """Входные параметры для расчета ипотеки."""

    CALCULATION_TYPE = forms.ChoiceField(
        choices=[('market', 'Ипотека'), ('trench', 'Траншевая ипотека')],
        initial='market',
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'calculation_type'}),
    )

    PROPERTY = forms.ModelChoiceField(
        queryset=Property.objects.all(),
        label='Объект недвижимости',
        required=False,
        widget=forms.HiddenInput(attrs={'id': 'id_PROPERTY'}),
    )

    OBJECT_CITY = forms.ModelChoiceField(
        queryset=City.objects.all(),
        label='Город',
        required=False,
        empty_label='Выберите город',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
                'id': 'city-select',
                'data-cascade-field': 'city',
            }
        ),
    )

    OBJECT_DISTRICT = forms.ModelChoiceField(
        queryset=District.objects.all(),
        label='Район',
        required=False,
        empty_label='Выберите район',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
                'id': 'district-select',
                'data-cascade-field': 'district',
                'data-cascade-data-key': 'districts',
                'data-cascade-empty-label': 'Выберите район',
                'data-cascade-parent-city': 'city_id',
                'data-cascade-autofill-city': 'city_id',
            }
        ),
    )

    OBJECT_DEVELOPER = DeveloperModelChoiceField(
        queryset=get_developers_with_company_groups_queryset(),
        label='Застройщик',
        required=False,
        empty_label='Выберите застройщика',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
                'id': 'developer-select',
                'data-cascade-field': 'developer',
            }
        ),
    )

    OBJECT_COMPLEX = forms.ModelChoiceField(
        queryset=RealEstateComplex.objects.all(),
        label='Жилой комплекс',
        required=False,
        empty_label='Выберите ЖК',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
                'id': 'complex-select',
                'data-cascade-field': 'complex',
                'data-cascade-data-key': 'complexes',
                'data-cascade-empty-label': 'Выберите ЖК',
                'data-cascade-parent-city': 'district__city_id',
                'data-cascade-parent-district': 'district_id',
                'data-cascade-parent-developer': 'developer_id',
                'data-cascade-autofill-city': 'district__city_id',
                'data-cascade-autofill-district': 'district_id',
                'data-cascade-autofill-developer': 'developer_id',
            }
        ),
    )

    OBJECT_BUILDING = forms.ModelChoiceField(
        queryset=RealEstateComplexBuilding.objects.all(),
        label='Корпус',
        required=False,
        empty_label='Выберите корпус',
        widget=forms.Select(
            attrs={
                'class': 'form-select',
                'id': 'id_building',
                'data-cascade-field': 'building',
                'data-cascade-data-key': 'buildings',
                'data-cascade-label-key': 'number',
                'data-cascade-empty-label': 'Выберите корпус',
                'data-cascade-parent-complex': 'real_estate_complex_id',
                'data-cascade-required-parents': 'complex',
            }
        ),
    )

    OBJECT_APARTMENT_NUMBER = forms.CharField(
        label='Номер квартиры',
        required=False,
        max_length=50,
        widget=forms.TextInput(
            attrs={
                'class': 'form-control',
                'autocomplete': 'off',
            }
        ),
    )

    OBJECT_AREA = forms.DecimalField(
        label='Площадь, м2',
        required=False,
        min_value=0,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(
            attrs={'class': 'form-control', 'step': '0.01'}
        ),
    )

    OBJECT_LAYOUT = forms.ModelChoiceField(
        queryset=ApartmentLayout.objects.all(),
        label='Планировка',
        required=False,
        empty_label='Выберите планировку',
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    OBJECT_FLOOR = forms.IntegerField(
        label='Этаж',
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )

    OBJECT_DECORATION = forms.ModelChoiceField(
        queryset=ApartmentDecoration.objects.all(),
        label='Отделка',
        required=False,
        empty_label='Выберите отделку',
        widget=forms.Select(attrs={'class': 'form-select'}),
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
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        """Prepare querysets for object selectors."""
        super().__init__(*args, **kwargs)
        self.fields['PROPERTY'].queryset = Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex__district__city',
            'building',
            'layout',
            'decoration',
        ).order_by(
            'building__real_estate_complex__name',
            'building__number',
            'apartment_number',
        )
        self.fields['OBJECT_CITY'].queryset = City.objects.order_by('name')
        self.fields['OBJECT_DISTRICT'].queryset = (
            District.objects.select_related('city').order_by('name')
        )
        self.fields['OBJECT_DEVELOPER'].queryset = (
            get_developers_with_company_groups_queryset()
        )
        self.fields['OBJECT_COMPLEX'].queryset = (
            RealEstateComplex.objects.select_related(
                'developer',
                'district__city',
            ).order_by('name')
        )
        self.fields['OBJECT_BUILDING'].queryset = (
            RealEstateComplexBuilding.objects.select_related(
                'real_estate_complex'
            ).order_by('real_estate_complex__name', 'number')
        )
        self.fields['OBJECT_LAYOUT'].queryset = ApartmentLayout.objects.order_by(
            'name'
        )
        self.fields['OBJECT_DECORATION'].queryset = (
            ApartmentDecoration.objects.order_by('name')
        )

    def has_manual_property_data(self):
        """Return whether the object block contains a new property."""
        if not hasattr(self, 'cleaned_data'):
            return False

        return any(
            self.cleaned_data.get(field_name)
            for field_name in MANUAL_PROPERTY_FIELD_NAMES
        )

    DISCOUNT_MARKUP_TYPE = forms.ChoiceField(
        label='Корректировка цены',
        choices=[('discount', 'Скидка'), ('markup', 'Удорожание')],
        widget=forms.RadioSelect(),
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

    MORTGAGE_TERM_YEARS = forms.IntegerField(
        label='Срок ипотеки, годы',
        min_value=0,
        max_value=50,
        initial=30,
        required=False,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'id': 'mortgage_term_years',
            }
        ),
    )

    MORTGAGE_TERM = forms.IntegerField(
        label='Срок ипотеки, мес.',
        min_value=1,
        max_value=600,
        initial=360,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'id': 'mortgage_term_months',
            }
        ),
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

    HAS_GRACE_PERIOD = forms.ChoiceField(
        label='Наличие льготного периода',
        choices=[('no', 'Нет'), ('yes', 'Да')],
        widget=forms.RadioSelect(),
        initial='no',
    )

    GRACE_PERIOD_TERM_YEARS = forms.IntegerField(
        label='Срок льготного периода, годы',
        min_value=0,
        max_value=50,
        required=False,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'id': 'grace_period_term_years',
            }
        ),
    )

    GRACE_PERIOD_TERM = forms.IntegerField(
        label='Срок льготного периода, мес.',
        min_value=0,
        max_value=600,
        required=False,
        widget=forms.NumberInput(
            attrs={
                'class': 'form-control',
                'id': 'grace_period_term_months',
            }
        ),
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
        calculation_type = cleaned_data.get('CALCULATION_TYPE') or 'market'
        has_grace_period = cleaned_data.get('HAS_GRACE_PERIOD')
        grace_period_term = cleaned_data.get('GRACE_PERIOD_TERM')
        grace_period_term_years = cleaned_data.get('GRACE_PERIOD_TERM_YEARS')
        grace_period_rate = cleaned_data.get('GRACE_PERIOD_RATE')
        mortgage_term = cleaned_data.get('MORTGAGE_TERM')
        mortgage_term_years = cleaned_data.get('MORTGAGE_TERM_YEARS')
        selected_property = cleaned_data.get('PROPERTY')

        if mortgage_term is not None:
            cleaned_data['MORTGAGE_TERM_YEARS'] = mortgage_term // 12
        elif mortgage_term_years is not None:
            cleaned_data['MORTGAGE_TERM'] = mortgage_term_years * 12
            mortgage_term = cleaned_data['MORTGAGE_TERM']

        if grace_period_term is not None:
            cleaned_data['GRACE_PERIOD_TERM_YEARS'] = (
                grace_period_term // 12
            )
        elif grace_period_term_years is not None:
            cleaned_data['GRACE_PERIOD_TERM'] = grace_period_term_years * 12
            grace_period_term = cleaned_data['GRACE_PERIOD_TERM']

        if calculation_type == 'market' and has_grace_period == 'yes':
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

        if selected_property:
            building = cleaned_data.get('OBJECT_BUILDING')
            apartment_number = cleaned_data.get('OBJECT_APARTMENT_NUMBER')
            if building and selected_property.building_id != building.pk:
                self.add_error(
                    'OBJECT_BUILDING',
                    'Выбранная квартира не относится к выбранному корпусу.',
                )
            if (
                apartment_number
                and selected_property.apartment_number != apartment_number
            ):
                self.add_error(
                    'OBJECT_APARTMENT_NUMBER',
                    'Выбранная квартира не соответствует номеру квартиры.',
                )
            return cleaned_data

        if self.has_manual_property_data():
            for field_name in MANUAL_PROPERTY_FIELD_NAMES:
                if cleaned_data.get(field_name):
                    continue
                self.add_error(
                    field_name,
                    'Заполните поле для сохранения нового объекта.',
                )

            city = cleaned_data.get('OBJECT_CITY')
            district = cleaned_data.get('OBJECT_DISTRICT')
            developer = cleaned_data.get('OBJECT_DEVELOPER')
            real_estate_complex = cleaned_data.get('OBJECT_COMPLEX')
            building = cleaned_data.get('OBJECT_BUILDING')

            if district and city and district.city_id != city.pk:
                self.add_error(
                    'OBJECT_DISTRICT',
                    'Выбранный район не относится к выбранному городу.',
                )

            if real_estate_complex:
                if (
                    developer
                    and real_estate_complex.developer_id != developer.pk
                ):
                    self.add_error(
                        'OBJECT_COMPLEX',
                        'Выбранный ЖК не относится к выбранному застройщику.',
                    )
                if district and real_estate_complex.district_id != district.pk:
                    self.add_error(
                        'OBJECT_COMPLEX',
                        'Выбранный ЖК не относится к выбранному району.',
                    )

            if (
                building
                and real_estate_complex
                and building.real_estate_complex_id != real_estate_complex.pk
            ):
                self.add_error(
                    'OBJECT_BUILDING',
                    'Выбранный корпус не относится к выбранному ЖК.',
                )

        return cleaned_data
