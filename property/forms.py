from django import forms
from django.forms import BaseInlineFormSet, inlineformset_factory

from location.models import City, District, Metro, Region

from .models import (
    CompanyGroup,
    Developer,
    Property,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateComplexMetroAvailability,
    TransportAccessibilityType,
    WindowView,
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
    """Form for creating and updating property objects."""

    IMAGE_CLEAR_FIELDS = (
        ('clear_layout_image', 'layout_image'),
        ('clear_floor_plan_image', 'floor_plan_image'),
        ('clear_window_view_image', 'window_view_image'),
    )

    clear_layout_image = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'd-none'}),
    )
    clear_floor_plan_image = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'd-none'}),
    )
    clear_window_view_image = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'd-none'}),
    )

    class Meta:
        """Configure model fields and widgets for the property form."""

        model = Property
        fields = [
            'apartment_number',
            'building',
            'decoration',
            'layout',
            'area',
            'floor',
            'property_cost',
            'window_views',
            'layout_image',
            'floor_plan_image',
            'window_view_image',
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
            'window_views': forms.CheckboxSelectMultiple(
                attrs={'class': 'form-check-input'}
            ),
            'layout_image': forms.FileInput(attrs={'class': 'form-control'}),
            'floor_plan_image': forms.FileInput(
                attrs={'class': 'form-control'}
            ),
            'window_view_image': forms.FileInput(
                attrs={'class': 'form-control'}
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
            'window_views': 'Вид из окна',
            'layout_image': 'Планировка',
            'floor_plan_image': 'План этажа',
            'window_view_image': 'Вид из окна',
        }

    def __init__(self, *args, **kwargs):
        """Prepare dictionary fields and current image names."""
        super().__init__(*args, **kwargs)
        self.fields['window_views'].queryset = WindowView.objects.order_by(
            'name'
        )
        self.fields['window_views'].required = False
        self.initial_image_names = {}
        for _, image_field in self.IMAGE_CLEAR_FIELDS:
            image = getattr(self.instance, image_field, None)
            self.initial_image_names[image_field] = image.name if image else ''

    def save(self, commit=True):
        """Save property fields and remove images marked for deletion."""
        instance = super().save(commit=False)
        image_names_to_delete = []

        for clear_field, image_field in self.IMAGE_CLEAR_FIELDS:
            if not self.cleaned_data.get(clear_field):
                continue

            initial_image_name = self.initial_image_names.get(image_field)
            if initial_image_name:
                image_names_to_delete.append((image_field, initial_image_name))

            if image_field not in self.files:
                setattr(instance, image_field, None)

        if commit:
            instance.save()
            self.save_m2m()
            self.delete_saved_images(image_names_to_delete, instance)

        return instance

    def delete_saved_images(self, image_names_to_delete, instance):
        """Delete cleared image files from storage after saving the model."""
        for image_field, image_name in image_names_to_delete:
            current_image = getattr(instance, image_field)
            if current_image and current_image.name == image_name:
                continue

            storage = instance._meta.get_field(image_field).storage
            if storage.exists(image_name):
                storage.delete(image_name)


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
        fields = [
            'name',
            'company_group',
            'legal_address',
            'actual_address',
            'taxpayer_identification_number',
            'tax_registration_reason_code',
            'primary_state_registration_number',
            'description',
            'is_active',
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_group': forms.Select(attrs={'class': 'form-control'}),
            'legal_address': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 2}
            ),
            'actual_address': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 2}
            ),
            'taxpayer_identification_number': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'tax_registration_reason_code': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'primary_state_registration_number': forms.TextInput(
                attrs={'class': 'form-control'}
            ),
            'description': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 3}
            ),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }

    def __init__(self, *args, **kwargs):
        """Prepare optional company group choices."""
        super().__init__(*args, **kwargs)
        self.fields['company_group'].queryset = CompanyGroup.objects.order_by(
            'name'
        )
        self.fields['company_group'].empty_label = 'Без группы компаний'


class CompanyGroupForm(forms.ModelForm):
    """Form for creating and updating company groups."""

    class Meta:
        """Configure company group form fields and widgets."""

        model = CompanyGroup
        fields = ['name']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class RealEstateComplexForm(forms.ModelForm):
    """Описание класса RealEstateComplexForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    clear_photo = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'd-none'}),
    )
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
            'investment_potential',
            'photo',
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
            'investment_potential': forms.Textarea(
                attrs={'class': 'form-control', 'rows': 4}
            ),
            'photo': forms.FileInput(attrs={'class': 'form-control'}),
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
        photo = getattr(self.instance, 'photo', None)
        self.initial_photo_name = photo.name if photo else ''

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

    def save(self, commit=True):
        """Save complex fields and remove the photo marked for deletion."""
        instance = super().save(commit=False)
        photo_name_to_delete = ''

        if self.cleaned_data.get('clear_photo'):
            photo_name_to_delete = self.initial_photo_name
            if 'photo' not in self.files:
                instance.photo = None

        if commit:
            instance.save()
            self.delete_saved_photo(photo_name_to_delete, instance)

        return instance

    def delete_saved_photo(self, photo_name_to_delete, instance):
        """Delete a cleared complex photo from storage after saving."""
        if not photo_name_to_delete:
            return

        if instance.photo and instance.photo.name == photo_name_to_delete:
            return

        storage = instance._meta.get_field('photo').storage
        if storage.exists(photo_name_to_delete):
            storage.delete(photo_name_to_delete)


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
            'address': forms.TextInput(
                attrs={'class': 'form-control', 'autocomplete': 'off'}
            ),
            'commissioning_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d',
            ),
            'commissioning_year': forms.NumberInput(
                attrs={'class': 'form-control', 'min': 2000, 'max': 2100}
            ),
            'commissioning_quarter': forms.Select(
                attrs={'class': 'form-control'}
            ),
            'key_handover_date': forms.DateInput(
                attrs={'class': 'form-control', 'type': 'date'},
                format='%Y-%m-%d',
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
            'transport_accessibility_type',
            'walking_time_minutes',
            'is_active',
        ]
        widgets = {
            'metro': forms.Select(attrs={'class': 'form-control'}),
            'transport_accessibility_type': forms.Select(
                attrs={'class': 'form-control'}
            ),
            'walking_time_minutes': forms.NumberInput(
                attrs={'class': 'form-control', 'min': 1}
            ),
            'is_active': forms.CheckboxInput(
                attrs={'class': 'form-check-input'}
            ),
        }
        labels = {
            'metro': 'Станция метро',
            'transport_accessibility_type': 'Способ',
            'walking_time_minutes': 'Время, мин',
            'is_active': 'Активен',
        }

    def __init__(self, *args, **kwargs):
        """Prepare dictionary querysets for metro availability rows."""
        super().__init__(*args, **kwargs)
        self.fields['metro'].queryset = Metro.objects.select_related(
            'metro_line__city'
        ).order_by('metro_line__city__name', 'metro_line__line', 'station')
        self.fields['metro'].empty_label = 'Выберите станцию'
        self.fields['metro'].label_from_instance = lambda metro: metro.station
        transport_accessibility_type_field = self.fields[
            'transport_accessibility_type'
        ]
        transport_accessibility_type_field.queryset = (
            TransportAccessibilityType.objects.order_by('id')
        )
        transport_accessibility_type_field.empty_label = 'Выберите способ'


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
            transport_accessibility_type = form.cleaned_data.get(
                'transport_accessibility_type'
            )
            walking_time = form.cleaned_data.get('walking_time_minutes')
            has_any_data = bool(
                metro or transport_accessibility_type or walking_time
            )

            if not has_any_data:
                continue

            if not metro:
                form.add_error('metro', 'Выберите станцию метро.')
            if not transport_accessibility_type:
                form.add_error(
                    'transport_accessibility_type',
                    'Выберите способ.',
                )
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


RealEstateComplexBuildingUpdateFormSet = inlineformset_factory(
    RealEstateComplex,
    RealEstateComplexBuilding,
    form=RealEstateComplexBuildingForm,
    formset=BaseRealEstateComplexBuildingInlineFormSet,
    extra=0,
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


RealEstateComplexMetroAvailabilityUpdateFormSet = inlineformset_factory(
    RealEstateComplex,
    RealEstateComplexMetroAvailability,
    form=RealEstateComplexMetroAvailabilityForm,
    formset=BaseRealEstateComplexMetroAvailabilityInlineFormSet,
    extra=0,
    can_delete=True,
)

