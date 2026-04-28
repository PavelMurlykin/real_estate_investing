from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from location.models import City, District, Region

from .models import (
    Developer,
    Property,
    RealEstateComplex,
    RealEstateComplexBuilding,
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
            'key_handover_date',
            'is_active',
        ]
        widgets = {
            'number': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.TextInput(attrs={'class': 'form-control'}),
            'commissioning_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'key_handover_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'}
            ),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }


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
