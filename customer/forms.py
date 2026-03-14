from django import forms

from bank.models import MortgageProgram
from location.models import City, District
from property.models import ApartmentLayout

from .models import Customer


class CustomerForm(forms.ModelForm):
    """Описание класса CustomerForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    class Meta:
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = Customer
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
            'is_active',
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
            'preferential_programs': forms.SelectMultiple(
                attrs={'class': 'form-select', 'size': 6}
            ),
            'has_owned_property': forms.Select(attrs={'class': 'form-select'}),
            'purchase_goal': forms.Select(attrs={'class': 'form-select'}),
            'desired_city': forms.Select(attrs={'class': 'form-select'}),
            'desired_district': forms.Select(attrs={'class': 'form-select'}),
            'desired_layouts': forms.SelectMultiple(
                attrs={'class': 'form-select', 'size': 6}
            ),
            'area_min': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': 0}
            ),
            'area_max': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': 0}
            ),
            'desired_floor': forms.TextInput(attrs={'class': 'form-control'}),
            'cardinal_directions': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'comment': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4}
            ),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }
        help_texts = {
            'age': (
                'Если указаны дата или год рождения, возраст заполнится '
                'автоматически.'
            ),
            'preferential_programs': (
                'Можно выбрать несколько льготных программ.'
            ),
        }

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
        ].queryset = MortgageProgram.objects.filter(
            is_preferential=True
        ).order_by('name')

        self.fields['residence_city'].empty_label = 'Не указан'
        self.fields['desired_city'].empty_label = 'Не указан'

        purchase_goal_choices = list(self.fields['purchase_goal'].choices)
        if purchase_goal_choices:
            purchase_goal_choices[0] = ('', 'Не указана')
            self.fields['purchase_goal'].choices = purchase_goal_choices

        self.fields['has_owned_property'].choices = [
            ('unknown', 'Не указано'),
            ('true', 'Да'),
            ('false', 'Нет'),
        ]

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
