from django.apps import apps
from django.contrib import admin

from .models import User


def test_admin_app_verbose_names():
    """Checks custom admin app group names."""
    assert apps.get_app_config('bank').verbose_name == 'Банки'
    assert (
        apps.get_app_config('trench_mortgage').verbose_name
        == 'Траншевая ипотека'
    )
    assert apps.get_app_config('users').verbose_name == 'Пользователи'


def test_user_admin_list_starts_with_id_and_links_email():
    """Checks user changelist columns and clickable field."""
    user_admin = admin.site._registry[User]

    assert user_admin.list_display[0] == 'id'
    assert user_admin.list_display[1] == 'email'
    assert user_admin.list_display_links == ('email',)


def test_user_model_verbose_names():
    """Checks user model and custom field labels."""
    assert User._meta.verbose_name == 'Пользователь'
    assert User._meta.verbose_name_plural == 'Пользователи'

    expected_field_labels = {
        'first_name': 'Имя',
        'last_name': 'Фамилия',
        'email': 'Электронная почта',
        'phone_number': 'Номер телефона',
        'is_real_estate_agent': 'Агент недвижимости',
        'agency_name': 'Название агентства',
    }
    for field_name, expected_label in expected_field_labels.items():
        field = User._meta.get_field(field_name)

        assert str(field.verbose_name) == expected_label
