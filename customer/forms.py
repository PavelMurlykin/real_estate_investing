from django import forms

from bank.models import MortgageProgram
from location.models import City, District
from property.models import ApartmentLayout

from .models import Customer


def coerce_optional_boolean(value):
    """Преобразует строковое значение radio button в optional boolean."""
    if value is True or value == 'true':
        return True
    if value is False or value == 'false':
        return False
    return None


class CustomerForm(forms.ModelForm):
    """Описание класса CustomerForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    HAS_OWNED_PROPERTY_CHOICES = (
        ('true', 'Да'),
        ('false', 'Нет'),
        ('unknown', 'Не указано'),
    )

    has_owned_property = forms.TypedChoiceField(
        required=False,
        label=Customer._meta.get_field('has_owned_property').verbose_name,
        choices=HAS_OWNED_PROPERTY_CHOICES,
        coerce=coerce_optional_boolean,
        empty_value=None,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'}),
    )
    cardinal_directions = forms.MultipleChoiceField(
        required=False,
        label=Customer._meta.get_field('cardinal_directions').verbose_name,
        choices=Customer.CARDINAL_DIRECTION_CHOICES,
        widget=forms.CheckboxSelectMultiple(
            attrs={'class': 'form-check-input'}
        ),
    )

    class Meta:
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = Customer
        labels = {
            'preferential_programs': 'Доступные программы',
        }
        fields = [
            'first_name',
            'last_name',
            'phone',
            'email',
            'age',
            'birth_date',
            'birth_year',
            'residence_city',
            'initial_payment_amount',
            'max_monthly_payment',
            'preferential_programs',
            'has_owned_property',
            'purchase_goal',
            'desired_city',
            'desired_district',
            'desired_layouts',
            'area_min',
            'area_max',
            'desired_floor',
            'cardinal_directions',
            'comment',
        ]
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'age': forms.NumberInput(
                attrs={'class': 'form-control', 'min': 0}
            ),
            'birth_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'birth_year': forms.NumberInput(
                attrs={'class': 'form-control', 'min': 1900}
            ),
            'residence_city': forms.Select(attrs={'class': 'form-select'}),
            'initial_payment_amount': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': 0}
            ),
            'max_monthly_payment': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': 0}
            ),
            'preferential_programs': forms.CheckboxSelectMultiple(
                attrs={'class': 'form-check-input'}
            ),
            'purchase_goal': forms.Select(attrs={'class': 'form-select'}),
            'desired_city': forms.Select(attrs={'class': 'form-select'}),
            'desired_district': forms.Select(attrs={'class': 'form-select'}),
            'desired_layouts': forms.CheckboxSelectMultiple(
                attrs={'class': 'form-check-input'}
            ),
            'area_min': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': 0}
            ),
            'area_max': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': 0}
            ),
            'desired_floor': forms.TextInput(attrs={'class': 'form-control'}),
            'comment': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4}
            ),
        }
        help_texts = {
            'age': (
                'Если указаны дата или год рождения, возраст заполнится '
                'автоматически.'
            ),
            'preferential_programs': (
                'Можно выбрать несколько программ.'
            ),
        }

    @staticmethod
    def _format_optional_boolean(value):
        """Возвращает строковое значение для radio button."""
        if value is True:
            return 'true'
        if value is False:
            return 'false'
        return 'unknown'

    @staticmethod
    def _split_cardinal_directions(value):
        """Разбирает сохраненную строку сторон света для чекбоксов."""
        available_values = {
            choice_value
            for choice_value, choice_label in Customer.CARDINAL_DIRECTION_CHOICES
        }
        return [
            direction.strip()
            for direction in (value or '').split(',')
            if direction.strip() in available_values
        ]

    def __init__(self, *args, **kwargs):
        """Описание метода __init__.

        Инициализирует экземпляр класса и подготавливает его внутреннее
        состояние.

        Аргументы:
            *args: Входной параметр, влияющий на работу метода.
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            None: Заполняет атрибуты текущего экземпляра.
        """
        super().__init__(*args, **kwargs)

        self.fields['residence_city'].queryset = City.objects.order_by('name')
        self.fields['desired_city'].queryset = City.objects.order_by('name')
        self.fields[
            'desired_layouts'
        ].queryset = ApartmentLayout.objects.order_by('name')
        self.fields[
            'preferential_programs'
        ].queryset = MortgageProgram.objects.order_by('name')

        if not self.is_bound:
            self.initial['has_owned_property'] = (
                self._format_optional_boolean(
                    self.instance.has_owned_property
                )
            )
            self.initial['cardinal_directions'] = (
                self._split_cardinal_directions(
                    self.instance.cardinal_directions
                )
            )

        self.fields['residence_city'].empty_label = 'Не указан'
        self.fields['desired_city'].empty_label = 'Не указан'

        purchase_goal_choices = list(self.fields['purchase_goal'].choices)
        if purchase_goal_choices:
            purchase_goal_choices[0] = ('', 'Не указана')
            self.fields['purchase_goal'].choices = purchase_goal_choices

        self.fields['desired_district'].queryset = District.objects.order_by(
            'name'
        )
        self.fields['desired_district'].empty_label = 'Не указан'

        selected_city_id = self.data.get('desired_city')
        if (
            not selected_city_id
            and self.instance
            and self.instance.desired_city_id
        ):
            selected_city_id = str(self.instance.desired_city_id)

        if selected_city_id:
            self.fields['desired_district'].queryset = District.objects.filter(
                city_id=selected_city_id
            ).order_by('name')

    def clean_cardinal_directions(self):
        """Сохраняет выбранные стороны света в текстовое поле модели."""
        return ', '.join(self.cleaned_data['cardinal_directions'])
