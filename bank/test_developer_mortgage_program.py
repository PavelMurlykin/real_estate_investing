from decimal import Decimal
from io import BytesIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from openpyxl import Workbook

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
from .developer_mortgage_program_importer import (
    DeveloperMortgageProgramImportError,
    REQUIRED_COLUMNS,
    import_developer_mortgage_programs,
    parse_developer_mortgage_program_workbook,
)
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


def build_import_row(**overrides):
    """Return a complete normalized import row with optional overrides."""
    row = {
        'record_id': 1,
        'source_sheet_row': 6,
        'company_group_name': 'Группа Север',
        'real_estate_complex_name': 'ЖК Основной',
        'object_scope': 'named',
        'bank_name': 'Тестовый банк',
        'program_type_code': 'family',
        'program_cell_column': 'G',
        'program_variant_index': 1,
        'is_program_on_stop': False,
        'grace_period_rate_percent': '0.10',
        'grace_period_term_years': 2,
        'interest_rate_percent': '4.30',
        'initial_payment_min_percent': '20.10',
        'maximum_loan_term_years': 30,
        'maximum_loan_amount_rub': 12_000_000,
        'rate_discount_percent': '0.50',
        'effective_price_increase_percent': '-1.25',
        'parse_warnings': '',
        'source_url': 'https://example.com/source',
    }
    row.update(overrides)
    return row


def build_import_workbook(rows, headers=REQUIRED_COLUMNS):
    """Build an in-memory XLSX workbook matching the import contract."""
    workbook = Workbook()
    worksheet = workbook.active
    worksheet.title = 'db_import'
    worksheet.append(list(headers))
    for row in rows:
        worksheet.append([row.get(column_name) for column_name in headers])

    workbook_file = BytesIO()
    workbook.save(workbook_file)
    workbook.close()
    workbook_file.seek(0)
    return workbook_file


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


@pytest.mark.django_db
def test_import_creates_typed_program_from_existing_dictionaries(
    company_group,
    bank,
    mortgage_program,
):
    """Importer maps normalized values and converts grace years to months."""
    real_estate_complex = create_real_estate_complex(
        company_group,
        'Основной',
    )
    workbook_file = build_import_workbook([build_import_row()])

    result = import_developer_mortgage_programs(workbook_file)

    developer_program = DeveloperMortgageProgram.objects.get()
    assert result.created == 1
    assert result.skipped == 0
    assert developer_program.real_estate_complex == real_estate_complex
    assert developer_program.grace_period_months == 24
    assert developer_program.grace_period_interest_rate == Decimal('0.10')
    assert developer_program.interest_rate == Decimal('4.30')
    assert developer_program.price_increase_percent == Decimal('-1.25')
    assert developer_program.source_record_id == 1
    assert developer_program.source_key


@pytest.mark.django_db
def test_import_updates_same_source_record_without_duplicates(
    company_group,
    bank,
    mortgage_program,
):
    """Rerunning a changed source variant updates the existing model row."""
    create_real_estate_complex(company_group, 'Основной')
    first_workbook = build_import_workbook([build_import_row()])
    second_workbook = build_import_workbook(
        [build_import_row(interest_rate_percent='4.75')]
    )

    first_result = import_developer_mortgage_programs(first_workbook)
    second_result = import_developer_mortgage_programs(second_workbook)

    assert first_result.created == 1
    assert second_result.created == 0
    assert second_result.updated == 1
    assert DeveloperMortgageProgram.objects.count() == 1
    assert (
        DeveloperMortgageProgram.objects.get().interest_rate
        == Decimal('4.75')
    )


@pytest.mark.django_db
def test_import_all_objects_and_unknown_price_increase(
    company_group,
    bank,
    mortgage_program,
):
    """All-object rows use a null complex and preserve unknown increase."""
    workbook_file = build_import_workbook(
        [
            build_import_row(
                object_scope='all_objects',
                real_estate_complex_name='Все объекты',
                effective_price_increase_percent=None,
                is_program_on_stop=True,
            )
        ]
    )

    result = import_developer_mortgage_programs(workbook_file)

    developer_program = DeveloperMortgageProgram.objects.get()
    assert result.created == 1
    assert result.inactive_rows == 1
    assert developer_program.real_estate_complex is None
    assert developer_program.price_increase_percent is None
    assert not developer_program.is_active


@pytest.mark.django_db
def test_import_never_creates_missing_dictionary_records(
    company_group,
    bank,
    mortgage_program,
):
    """Missing groups, banks, complexes and programs are only reported."""
    create_real_estate_complex(company_group, 'Основной')
    initial_counts = {
        'company_groups': CompanyGroup.objects.count(),
        'banks': Bank.objects.count(),
        'complexes': RealEstateComplex.objects.count(),
        'programs': MortgageProgram.objects.count(),
    }
    workbook_file = build_import_workbook(
        [
            build_import_row(
                record_id=1,
                source_sheet_row=10,
                company_group_name='Несуществующая группа',
            ),
            build_import_row(
                record_id=2,
                source_sheet_row=11,
                bank_name='Несуществующий банк',
            ),
            build_import_row(
                record_id=3,
                source_sheet_row=12,
                real_estate_complex_name='Несуществующий ЖК',
            ),
            build_import_row(
                record_id=4,
                source_sheet_row=13,
                program_type_code='it',
                program_cell_column='H',
            ),
        ]
    )

    result = import_developer_mortgage_programs(workbook_file)

    assert result.created == 0
    assert result.skipped == 4
    assert not DeveloperMortgageProgram.objects.exists()
    assert CompanyGroup.objects.count() == initial_counts['company_groups']
    assert Bank.objects.count() == initial_counts['banks']
    assert RealEstateComplex.objects.count() == initial_counts['complexes']
    assert MortgageProgram.objects.count() == initial_counts['programs']
    issue_text = ' '.join(result.issue_messages)
    assert 'отсутствует в базе' in issue_text


@pytest.mark.django_db
def test_import_skips_unsupported_scopes_and_exact_duplicates(
    company_group,
    bank,
    mortgage_program,
):
    """Report unsupported scopes and collapse exact business duplicates."""
    create_real_estate_complex(company_group, 'Основной')
    workbook_file = build_import_workbook(
        [
            build_import_row(record_id=1, source_sheet_row=20),
            build_import_row(record_id=2, source_sheet_row=21),
            build_import_row(
                record_id=3,
                source_sheet_row=22,
                object_scope='all_except',
                real_estate_complex_name='Все объекты',
            ),
        ]
    )

    result = import_developer_mortgage_programs(workbook_file)

    assert result.created == 1
    assert result.duplicate_rows == 1
    assert result.skipped == 2
    assert DeveloperMortgageProgram.objects.count() == 1
    assert 'не поддерживается моделью' in ' '.join(result.issue_messages)


def test_parser_rejects_missing_required_columns():
    """Parser rejects structurally incompatible workbooks before loading."""
    incomplete_headers = tuple(
        column_name
        for column_name in REQUIRED_COLUMNS
        if column_name != 'bank_name'
    )
    workbook_file = build_import_workbook(
        [build_import_row()],
        headers=incomplete_headers,
    )

    with pytest.raises(DeveloperMortgageProgramImportError):
        parse_developer_mortgage_program_workbook(workbook_file)


@pytest.mark.django_db
def test_import_view_requires_moderator_and_displays_summary(
    client,
    regular_user,
    moderator,
    company_group,
    bank,
    mortgage_program,
):
    """Only moderators can upload files and see the redirected summary."""
    create_real_estate_complex(company_group, 'Основной')
    upload_url = reverse('bank:developer_mortgage_program_import')
    workbook_bytes = build_import_workbook(
        [build_import_row()]
    ).getvalue()

    client.force_login(regular_user)
    denied_response = client.post(
        upload_url,
        data={
            'workbook_file': SimpleUploadedFile(
                'programs.xlsx',
                workbook_bytes,
            )
        },
    )
    assert denied_response.status_code == 403
    assert not DeveloperMortgageProgram.objects.exists()

    client.force_login(moderator)
    response = client.post(
        upload_url,
        data={
            'workbook_file': SimpleUploadedFile(
                'programs.xlsx',
                workbook_bytes,
            )
        },
        follow=True,
    )

    assert response.status_code == 200
    assert 'Результат импорта' in response.content.decode('utf-8')
    assert DeveloperMortgageProgram.objects.count() == 1


@pytest.mark.django_db
def test_import_query_count_is_bounded(
    company_group,
    bank,
    mortgage_program,
):
    """Batch loading does not issue database queries for every source row."""
    create_real_estate_complex(company_group, 'Основной')
    rows = [
        build_import_row(
            record_id=index,
            source_sheet_row=100 + index,
            program_variant_index=index,
            interest_rate_percent=Decimal('4.00') + Decimal(index) / 100,
        )
        for index in range(1, 31)
    ]
    workbook_file = build_import_workbook(rows)

    with CaptureQueriesContext(connection) as captured_queries:
        result = import_developer_mortgage_programs(workbook_file)

    assert result.created == 30
    assert len(captured_queries) <= 15
