from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from location.models import City, District, Metro, Region

from .models import (
    Developer,
    Property,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateComplexMetroAvailability,
)


class PropertyFilterForm(forms.Form):
    """Описание класса PropertyFilterForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    city = forms.ModelChoiceField(
        queryset=City.objects.all(),
        required=False,
        empty_label='Все города',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Город',
    )
    developer = forms.ModelChoiceField(
        queryset=Developer.objects.all(),
        required=False,
        empty_label='Все застройщики',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Застройщик',
    )
    complex = forms.ModelChoiceField(
        queryset=RealEstateComplex.objects.all(),
        required=False,
        empty_label='Все ЖК',
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Жилой комплекс',
    )


class PropertyForm(forms.ModelForm):
    """Описание класса PropertyForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    class Meta:
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = Property
        fields = [
            'apartment_number',
            'building',
            'decoration',
            'layout',
            'area',
            'floor',
            'property_cost',
        ]
        widgets = {
            'apartment_number': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'building': forms.Select(attrs={'class': 'form-control'}),
            'decoration': forms.Select(attrs={'class': 'form-control'}),
            'layout': forms.Select(attrs={'class': 'form-control'}),
            'area': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01'}
            ),
            'floor': forms.NumberInput(attrs={'class': 'form-control'}),
            'property_cost': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01'}
            ),
        }
        labels = {
            'apartment_number': 'Номер квартиры',
            'building': 'Корпус',
            'decoration': 'Отделка',
            'layout': 'Планировка',
            'area': 'Площадь, м2',
            'floor': 'Этаж',
            'property_cost': 'Стоимость, руб.',
        }


class DeveloperForm(forms.ModelForm):
    """Описание класса DeveloperForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    class Meta:
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = Developer
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3}
            ),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }


class RealEstateComplexForm(forms.ModelForm):
    """Описание класса RealEstateComplexForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    region = forms.ModelChoiceField(
        queryset=Region.objects.none(),
        required=False,
        empty_label='Все регионы',
        label='Регион',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )
    city = forms.ModelChoiceField(
        queryset=City.objects.none(),
        required=False,
        empty_label='Все города',
        label='Город',
        widget=forms.Select(attrs={'class': 'form-control'}),
    )

    class Meta:
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = RealEstateComplex
        fields = [
            'name',
            'description',
            'developer',
            'region',
            'city',
            'district',
            'map_link',
            'presentation_link',
            'real_estate_class',
            'real_estate_type',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3}
            ),
            'map_link': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 2}
            ),
            'presentation_link': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 2}
            ),
            'developer': forms.Select(attrs={'class': 'form-control'}),
            'district': forms.Select(attrs={'class': 'form-control'}),
            'real_estate_class': forms.Select(attrs={'class': 'form-control'}),
            'real_estate_type': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }

    def __init__(self, *args, **kwargs):
        """Prepare location helper fields from the selected district."""
        super().__init__(*args, **kwargs)

        self.fields['region'].queryset = Region.objects.order_by('name')
        self.fields['city'].queryset = City.objects.select_related(
            'region'
        ).order_by('name')
        self.fields['district'].queryset = District.objects.select_related(
            'city__region'
        ).order_by('name')
        self.fields['district'].empty_label = 'Выберите район'

        district = getattr(self.instance, 'district', None)
        if district:
            self.fields['city'].initial = district.city_id
            self.fields['region'].initial = district.city.region_id

    def clean(self):
        """Keep region, city, and district hierarchy consistent."""
        cleaned_data = super().clean()
        region = cleaned_data.get('region')
        city = cleaned_data.get('city')
        district = cleaned_data.get('district')

        if district:
            district_city = district.city
            district_region = district_city.region

            if city and district.city_id != city.pk:
                self.add_error(
                    'district',
                    'Выбранный район не относится к выбранному городу.',
                )
            else:
                cleaned_data['city'] = district_city

            if region and district_region.pk != region.pk:
                self.add_error(
                    'district',
                    'Выбранный район не относится к выбранному региону.',
                )
            else:
                cleaned_data['region'] = district_region

        elif city:
            city_region = city.region
            if region and city_region.pk != region.pk:
                self.add_error(
                    'city',
                    'Выбранный город не относится к выбранному региону.',
                )
            else:
                cleaned_data['region'] = city_region

        return cleaned_data


class RealEstateComplexBuildingForm(forms.ModelForm):
    """Описание класса RealEstateComplexBuildingForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    class Meta:
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = RealEstateComplexBuilding
        fields = [
            'number',
            'address',
            'commissioning_date',
            'commissioning_year',
            'commissioning_quarter',
            'key_handover_date',
            'key_handover_year',
            'key_handover_quarter',
            'is_active',
        ]
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'commissioning_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'commissioning_year': forms.NumberInput(
                attrs={'class': 'form-control', 'min': 2000, 'max': 2100}
            ),
            'commissioning_quarter': forms.Select(
                attrs={'class': 'form-control'}
            ),
            'key_handover_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'key_handover_year': forms.NumberInput(
                attrs={'class': 'form-control', 'min': 2000, 'max': 2100}
            ),
            'key_handover_quarter': forms.Select(
                attrs={'class': 'form-control'}
            ),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }


class RealEstateComplexMetroAvailabilityForm(forms.ModelForm):
    """Form for metro availability rows on the complex form."""

    class Meta:
        model = RealEstateComplexMetroAvailability
        fields = [
            'metro',
            'walking_time_minutes',
            'is_active',
        ]
        widgets = {
            'metro': forms.Select(attrs={'class': 'form-control'}),
            'walking_time_minutes': forms.NumberInput(
                attrs={'class': 'form-control', 'min': 1}
            ),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }
        labels = {
            'metro': 'Станция метро',
            'walking_time_minutes': 'Пешком, мин.',
            'is_active': 'Активен',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['metro'].queryset = Metro.objects.select_related(
            'metro_line__city'
        ).order_by('metro_line__city__name', 'metro_line__line', 'station')
        self.fields['metro'].empty_label = 'Выберите станцию'


class BaseRealEstateComplexMetroAvailabilityInlineFormSet(BaseInlineFormSet):
    """Validation for metro availability inline rows."""

    def clean(self):
        super().clean()

        seen_metro_ids = set()
        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue
            if form.cleaned_data.get('DELETE'):
                continue

            metro = form.cleaned_data.get('metro')
            walking_time = form.cleaned_data.get('walking_time_minutes')
            has_any_data = bool(metro or walking_time)

            if not has_any_data:
                continue

            if not metro:
                form.add_error('metro', 'Выберите станцию метро.')
            if walking_time in (None, ''):
                form.add_error(
                    'walking_time_minutes',
                    'Укажите время до метро.',
                )
            elif walking_time <= 0:
                form.add_error(
                    'walking_time_minutes',
                    'Время должно быть больше 0.',
                )

            if metro:
                if metro.pk in seen_metro_ids:
                    form.add_error(
                        'metro',
                        'Эта станция уже добавлена для ЖК.',
                    )
                seen_metro_ids.add(metro.pk)


class BaseRealEstateComplexBuildingInlineFormSet(BaseInlineFormSet):
    """Описание класса BaseRealEstateComplexBuildingInlineFormSet.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    def clean(self):
        """Описание метода clean.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        super().clean()

        for form in self.forms:
            if not hasattr(form, 'cleaned_data'):
                continue

            if (
                form.cleaned_data.get('DELETE')
                and form.instance.pk
                and form.instance.property_set.exists()
            ):
                form.add_error(
                    None,
                    (
                        'Нельзя удалить корпус, к которому привязаны '
                        'объекты недвижимости.'
                    ),
                )


RealEstateComplexBuildingFormSet = inlineformset_factory(
    RealEstateComplex,
    RealEstateComplexBuilding,
    form=RealEstateComplexBuildingForm,
    formset=BaseRealEstateComplexBuildingInlineFormSet,
    extra=1,
    can_delete=True,
)


RealEstateComplexMetroAvailabilityFormSet = inlineformset_factory(
    RealEstateComplex,
    RealEstateComplexMetroAvailability,
    form=RealEstateComplexMetroAvailabilityForm,
    formset=BaseRealEstateComplexMetroAvailabilityInlineFormSet,
    extra=3,
    can_delete=True,
)
