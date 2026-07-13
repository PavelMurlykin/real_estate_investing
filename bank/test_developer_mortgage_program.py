from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from location.models import City, District, Region
from property.models import (
    CompanyGroup,
    Developer,
    RealEstateClass,
    RealEstateComplex,
    RealEstateType,
)
from users.roles import MODERATOR_GROUP_NAME

from .forms import DeveloperMortgageProgramForm
from .models import Bank, DeveloperMortgageProgram, MortgageProgram


@pytest.fixture
def company_group(db):
    """Создает группу компаний для ипотечной программы."""
    return CompanyGroup.objects.create(name='Группа Север')


@pytest.fixture
def bank(db):
    """Создает банк для ипотечной программы."""
    return Bank.objects.create(name='Тестовый банк')


@pytest.fixture
def mortgage_program(db):
    """Создает эталонную ипотечную программу."""
    return MortgageProgram.objects.create(
        name='Семейная ипотека',
        condition='Условия программы',
        is_preferential=True,
    )


@pytest.fixture
def moderator(db):
    """Создает пользователя с правом управления справочниками."""
    user = get_user_model().objects.create_user(
        email='moderator-program@example.com',
        password='password',
        phone_number='+79990000101',
        first_name='Иван',
        last_name='Модератор',
    )
    group, _created = Group.objects.get_or_create(
        name=MODERATOR_GROUP_NAME
    )
    user.groups.add(group)
    return user


@pytest.fixture
def regular_user(db):
    """Создает пользователя без права управления справочниками."""
    return get_user_model().objects.create_user(
        email='user-program@example.com',
        password='password',
        phone_number='+79990000102',
        first_name='Петр',
        last_name='Пользователь',
    )


def create_real_estate_complex(company_group, suffix):
    """Создает ЖК с обязательными связанными справочниками."""
    region = Region.objects.create(
        name=f'Регион {suffix}',
        code=f'R{suffix}',
    )
    city = City.objects.create(name=f'Город {suffix}', region=region)
    district = District.objects.create(
        name=f'Район {suffix}',
        city=city,
    )
    developer = Developer.objects.create(
        name=f'Застройщик {suffix}',
        company_group=company_group,
    )
    real_estate_class = RealEstateClass.objects.create(
        name=f'Класс {suffix}',
        weight=Decimal('1'),
    )
    real_estate_type = RealEstateType.objects.create(
        name=f'Тип {suffix}'
    )
    return RealEstateComplex.objects.create(
        name=f'ЖК {suffix}',
        developer=developer,
        district=district,
        real_estate_class=real_estate_class,
        real_estate_type=real_estate_type,
    )


@pytest.mark.django_db
def test_program_without_complex_applies_to_all_group_complexes(
    company_group,
    bank,
    mortgage_program,
):
    """Пустой ЖК означает действие программы на всю группу компаний."""
    developer_program = DeveloperMortgageProgram(
        company_group=company_group,
        bank=bank,
        mortgage_program=mortgage_program,
        price_increase_percent=Decimal('-1.50'),
    )

    developer_program.full_clean()
    developer_program.save()

    assert developer_program.real_estate_complex is None
    assert developer_program.price_increase_percent == Decimal('-1.50')
    assert 'Все ЖК группы' in str(developer_program)


@pytest.mark.django_db
def test_program_rejects_complex_from_another_company_group(
    company_group,
    bank,
    mortgage_program,
):
    """Модель отклоняет ЖК, не принадлежащий выбранной группе."""
    other_company_group = CompanyGroup.objects.create(name='Другая группа')
    real_estate_complex = create_real_estate_complex(
        other_company_group,
        'Чужой',
    )
    developer_program = DeveloperMortgageProgram(
        company_group=company_group,
        real_estate_complex=real_estate_complex,
        bank=bank,
        mortgage_program=mortgage_program,
    )

    with pytest.raises(ValidationError) as error:
        developer_program.full_clean()

    assert 'real_estate_complex' in error.value.message_dict


@pytest.mark.django_db
def test_form_limits_complexes_to_selected_company_group(
    company_group,
):
    """Форма не загружает ЖК других групп компаний."""
    expected_complex = create_real_estate_complex(company_group, 'Свой')
    other_company_group = CompanyGroup.objects.create(name='Группа Юг')
    other_complex = create_real_estate_complex(
        other_company_group,
        'Другой',
    )

    form = DeveloperMortgageProgramForm(
        initial={'company_group': company_group.pk}
    )
    complex_ids = set(
        form.fields['real_estate_complex'].queryset.values_list(
            'pk', flat=True
        )
    )

    assert expected_complex.pk in complex_ids
    assert other_complex.pk not in complex_ids


@pytest.mark.django_db
def test_bank_catalog_contains_developer_program_tab(client):
    """Справочник банков содержит ссылку на новый отдельный CRUD."""
    response = client.get(reverse('bank:catalog'))

    assert response.status_code == 200
    developer_program_tab = next(
        tab
        for tab in response.context['model_tabs']
        if tab['key'] == 'developer_mortgage_program'
    )
    assert developer_program_tab['url'] == reverse(
        'bank:developer_mortgage_program_list'
    )


@pytest.mark.django_db
def test_regular_user_cannot_create_developer_program(
    client,
    regular_user,
    company_group,
    bank,
    mortgage_program,
):
    """Пользователь без роли модератора не может изменять справочник."""
    client.force_login(regular_user)

    response = client.post(
        reverse('bank:developer_mortgage_program_create'),
        data={
            'company_group': company_group.pk,
            'bank': bank.pk,
            'mortgage_program': mortgage_program.pk,
            'price_increase_percent': '0',
        },
    )

    assert response.status_code == 403
    assert not DeveloperMortgageProgram.objects.exists()


@pytest.mark.django_db
def test_moderator_can_create_update_and_delete_developer_program(
    client,
    moderator,
    company_group,
    bank,
    mortgage_program,
):
    """Модератор выполняет полный цикл CRUD через отдельные формы."""
    client.force_login(moderator)
    create_response = client.post(
        reverse('bank:developer_mortgage_program_create'),
        data={
            'company_group': company_group.pk,
            'real_estate_complex': '',
            'bank': bank.pk,
            'mortgage_program': mortgage_program.pk,
            'price_increase_percent': '2.50',
            'grace_period_months': '12',
            'grace_period_interest_rate': '0.10',
            'minimum_initial_payment_percent': '20.10',
            'interest_rate': '6.00',
            'maximum_loan_term_years': '30',
            'maximum_loan_amount': '12000000',
            'rate_discount_percent': '0.50',
        },
    )

    assert create_response.status_code == 302
    developer_program = DeveloperMortgageProgram.objects.get()
    assert developer_program.maximum_loan_amount == Decimal('12000000')

    update_response = client.post(
        reverse(
            'bank:developer_mortgage_program_update',
            kwargs={'pk': developer_program.pk},
        ),
        data={
            'company_group': company_group.pk,
            'real_estate_complex': '',
            'bank': bank.pk,
            'mortgage_program': mortgage_program.pk,
            'price_increase_percent': '-1.25',
            'grace_period_months': '',
            'grace_period_interest_rate': '',
            'minimum_initial_payment_percent': '25',
            'interest_rate': '5.75',
            'maximum_loan_term_years': '25',
            'maximum_loan_amount': '10000000',
            'rate_discount_percent': '0.25',
        },
    )

    assert update_response.status_code == 302
    developer_program.refresh_from_db()
    assert developer_program.price_increase_percent == Decimal('-1.25')
    assert developer_program.grace_period_months is None

    delete_response = client.post(
        reverse(
            'bank:developer_mortgage_program_delete',
            kwargs={'pk': developer_program.pk},
        )
    )

    assert delete_response.status_code == 302
    assert not DeveloperMortgageProgram.objects.exists()


@pytest.mark.django_db
def test_complex_options_only_include_selected_group(
    client,
    moderator,
    company_group,
):
    """JSON-подсказка возвращает только ЖК выбранной группы."""
    expected_complex = create_real_estate_complex(company_group, 'Основной')
    other_company_group = CompanyGroup.objects.create(name='Группа Восток')
    create_real_estate_complex(other_company_group, 'Сторонний')
    options_url = reverse(
        'bank:developer_mortgage_program_complex_options'
    )
    denied_response = client.get(
        options_url,
        data={'company_group_id': company_group.pk},
    )
    assert denied_response.status_code == 403

    client.force_login(moderator)
    response = client.get(
        options_url,
        data={'company_group_id': company_group.pk},
    )

    assert response.status_code == 200
    assert response.json() == {
        'complexes': [
            {
                'id': expected_complex.pk,
                'label': (
                    f'{expected_complex.name} '
                    f'({expected_complex.developer.name})'
                ),
            }
        ]
    }


@pytest.mark.django_db
def test_developer_program_list_has_bounded_query_count(
    client,
    company_group,
    bank,
    mortgage_program,
):
    """Список загружает связанные записи без запроса на каждую строку."""
    DeveloperMortgageProgram.objects.bulk_create(
        [
            DeveloperMortgageProgram(
                company_group=company_group,
                bank=bank,
                mortgage_program=mortgage_program,
                price_increase_percent=Decimal(index),
            )
            for index in range(3)
        ]
    )

    with CaptureQueriesContext(connection) as captured_queries:
        response = client.get(
            reverse('bank:developer_mortgage_program_list')
        )

    assert response.status_code == 200
    assert len(captured_queries) <= 8
