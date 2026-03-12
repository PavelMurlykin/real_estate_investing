from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import AuthenticationForm, UserChangeForm, UserCreationForm
from django.core.exceptions import ValidationError

from .utils import normalize_phone_number

User = get_user_model()


class UserRegistrationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
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
        super().__init__(*args, **kwargs)
        for field_name in self.fields:
            existing_class = self.fields[field_name].widget.attrs.get('class', '')
            combined = f'{existing_class} form-control'.strip()
            self.fields[field_name].widget.attrs['class'] = ' '.join(combined.split())

        self.fields['is_real_estate_agent'].widget.attrs['class'] = 'form-check-input'
        self.fields['email'].widget.attrs['autocomplete'] = 'email'
        self.fields['phone_number'].widget.attrs['autocomplete'] = 'tel'
        self.fields['password1'].widget.attrs['autocomplete'] = 'new-password'
        self.fields['password2'].widget.attrs['autocomplete'] = 'new-password'

    def clean_email(self):
        return self.cleaned_data['email'].strip().lower()

    def clean_phone_number(self):
        phone_number = normalize_phone_number(self.cleaned_data['phone_number'])
        if not phone_number:
            raise ValidationError('Enter a valid phone number.')
        return phone_number

    def clean(self):
        cleaned_data = super().clean()
        is_agent = cleaned_data.get('is_real_estate_agent')
        agency_name = (cleaned_data.get('agency_name') or '').strip()

        if is_agent and not agency_name:
            self.add_error('agency_name', 'Agency name is required for agents.')
        if not is_agent:
            cleaned_data['agency_name'] = ''

        return cleaned_data


class UserLoginForm(AuthenticationForm):
    username = forms.CharField(label='Email or phone')

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        for field_name in self.fields:
            existing_class = self.fields[field_name].widget.attrs.get('class', '')
            combined = f'{existing_class} form-control'.strip()
            self.fields[field_name].widget.attrs['class'] = ' '.join(combined.split())

        self.fields['username'].widget.attrs['autocomplete'] = 'username'
        self.fields['password'].widget.attrs['autocomplete'] = 'current-password'


class UserAdminCreationForm(UserCreationForm):
    class Meta(UserCreationForm.Meta):
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
    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'
