from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import (
    AuthenticationForm,
    UserChangeForm,
    UserCreationForm,
)
from django.core.exceptions import ValidationError

from .utils import normalize_phone_number

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    """Описание класса UserRegistrationForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    class Meta(UserCreationForm.Meta):
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = User
        fields = (
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'is_real_estate_agent',
            'agency_name',
        )

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
        for field_name in self.fields:
            existing_class = self.fields[field_name].widget.attrs.get(
                'class', ''
            )
            combined = f'{existing_class} form-control'.strip()
            self.fields[field_name].widget.attrs['class'] = ' '.join(
                combined.split()
            )

        self.fields['first_name'].label = 'Имя'
        self.fields['last_name'].label = 'Фамилия'
        self.fields['email'].label = 'Email'
        self.fields['phone_number'].label = 'Телефон'
        self.fields['is_real_estate_agent'].label = 'Я агент недвижимости'
        self.fields['agency_name'].label = 'Название агентства'
        self.fields['password1'].label = 'Пароль'
        self.fields['password2'].label = 'Подтверждение пароля'

        self.fields['is_real_estate_agent'].widget.attrs['class'] = (
            'form-check-input'
        )
        self.fields['email'].widget.attrs['autocomplete'] = 'email'
        self.fields['phone_number'].widget.attrs['autocomplete'] = 'tel'
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'

    def clean_email(self):
        """Описание метода clean_email.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        return self.cleaned_data['email'].strip().lower()

    def clean_phone_number(self):
        """Описание метода clean_phone_number.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        phone_number = normalize_phone_number(
            self.cleaned_data['phone_number']
        )
        if not phone_number:
            raise ValidationError('Введите корректный номер телефона.')
        return phone_number

    def clean(self):
        """Описание метода clean.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        cleaned_data = super().clean()
        is_agent = cleaned_data.get('is_real_estate_agent')
        agency_name = (cleaned_data.get('agency_name') or '').strip()

        if is_agent and not agency_name:
            self.add_error(
                'agency_name',
                'Для агента недвижимости нужно указать название агентства.',
            )
        if not is_agent:
            cleaned_data['agency_name'] = ''

        return cleaned_data


class UserProfileForm(forms.ModelForm):
    """Описание класса UserProfileForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    class Meta:
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = User
        fields = (
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'is_real_estate_agent',
            'agency_name',
        )

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
        for field_name in self.fields:
            existing_class = self.fields[field_name].widget.attrs.get(
                'class', ''
            )
            combined = f'{existing_class} form-control'.strip()
            self.fields[field_name].widget.attrs['class'] = ' '.join(
                combined.split()
            )

        self.fields['first_name'].label = 'Имя'
        self.fields['last_name'].label = 'Фамилия'
        self.fields['email'].label = 'Email'
        self.fields['phone_number'].label = 'Телефон'
        self.fields['is_real_estate_agent'].label = 'Я агент недвижимости'
        self.fields['agency_name'].label = 'Название агентства'

        self.fields['is_real_estate_agent'].widget.attrs['class'] = (
            'form-check-input'
        )
        self.fields['email'].widget.attrs['autocomplete'] = 'email'
        self.fields['phone_number'].widget.attrs['autocomplete'] = 'tel'

    def clean_email(self):
        """Описание метода clean_email.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        return self.cleaned_data['email'].strip().lower()

    def clean_phone_number(self):
        """Описание метода clean_phone_number.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        phone_number = normalize_phone_number(
            self.cleaned_data['phone_number']
        )
        if not phone_number:
            raise ValidationError('Введите корректный номер телефона.')
        return phone_number

    def clean(self):
        """Описание метода clean.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        cleaned_data = super().clean()
        is_agent = cleaned_data.get('is_real_estate_agent')
        agency_name = (cleaned_data.get('agency_name') or '').strip()

        if is_agent and not agency_name:
            self.add_error(
                'agency_name',
                'Для агента недвижимости нужно указать название агентства.',
            )
        if not is_agent:
            cleaned_data['agency_name'] = ''

        return cleaned_data


class UserLoginForm(AuthenticationForm):
    """Описание класса UserLoginForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    username = forms.CharField(label='Email или телефон')

    def __init__(self, request=None, *args, **kwargs):
        """Описание метода __init__.

        Инициализирует экземпляр класса и подготавливает его внутреннее
        состояние.

        Аргументы:
            request: Входной параметр, влияющий на работу метода.
            *args: Входной параметр, влияющий на работу метода.
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            None: Заполняет атрибуты текущего экземпляра.
        """
        super().__init__(request, *args, **kwargs)
        for field_name in self.fields:
            existing_class = self.fields[field_name].widget.attrs.get(
                'class', ''
            )
            combined = f'{existing_class} form-control'.strip()
            self.fields[field_name].widget.attrs['class'] = ' '.join(
                combined.split()
            )

        self.fields['username'].widget.attrs['autocomplete'] = 'username'
        self.fields['password'].widget.attrs['autocomplete'] = (
            'current-password'
        )


class UserAdminCreationForm(UserCreationForm):
    """Описание класса UserAdminCreationForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    class Meta(UserCreationForm.Meta):
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = User
        fields = (
            'email',
            'first_name',
            'last_name',
            'phone_number',
            'is_real_estate_agent',
            'agency_name',
        )


class UserAdminChangeForm(UserChangeForm):
    """Описание класса UserAdminChangeForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    class Meta(UserChangeForm.Meta):
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = User
        fields = '__all__'
