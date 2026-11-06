from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from location.models import Region
from users.roles import (
    APPLICATION_ADMINISTRATOR_GROUP_NAME,
    MODERATOR_GROUP_NAME,
)

from .forms import BankForm
from .key_rate_sync import KeyRateSyncError
from .models import (
    Bank,
    BankProgram,
    DeveloperMortgageProgram,
    KeyRate,
    MortgageProgram,
    MortgageProgramRegionalCreditLimit,
)


def test_bank_model_verbose_names():
    """Checks bank model and field labels."""
    expected_model_labels = {
        Bank: ('Банк', 'Банки'),
        MortgageProgram: (
            'Ипотечная программа',
            'Ипотечные программы',
        ),
        MortgageProgramRegionalCreditLimit: (
            'Региональный лимит ипотечной программы',
            'Региональные лимиты ипотечных программ',
        ),
        BankProgram: ('Программа банка', 'Программы банков'),
        DeveloperMortgageProgram: (
            'Ипотечная программа застройщика',
            'Ипотечные программы застройщиков',
        ),
        KeyRate: ('Ключевая ставка', 'Ключевые ставки'),
    }

    for model, expected_labels in expected_model_labels.items():
        expected_verbose_name, expected_verbose_name_plural = expected_labels

        assert model._meta.verbose_name == expected_verbose_name
        assert model._meta.verbose_name_plural == expected_verbose_name_plural

    assert str(Bank._meta.get_field('name').verbose_name) == 'Название'
    assert (
        str(BankProgram._meta.get_field('interest_rate').verbose_name)
        == 'Процентная ставка, %'
    )


def create_user_with_role(email, phone_number, group_name=None):
    """Create a test user and optionally add an application role group."""
    user = get_user_model().objects.create_user(
        email=email,
        password='password',
        phone_number=phone_number,
        first_name='Test',
        last_name='User',
    )
    if group_name:
        group, _created = Group.objects.get_or_create(name=group_name)
        user.groups.add(group)
    return user

class MortgageProgramCreditLimitTests(TestCase):
    """Проверяет лимиты кредита по льготным ипотечным программам."""

    def setUp(self):
        """Log in as moderator for catalog mutation tests."""
        self.client.force_login(
            create_user_with_role(
                'bank-moderator@example.com',
                '+79991000000',
                MODERATOR_GROUP_NAME,
            )
        )

    def test_preferential_mortgage_uses_program_credit_limit(self):
        """Проверяет базовый лимит кредита ипотечной программы."""
        program = MortgageProgram.objects.create(
            name='IT-ипотека',
            condition='Льготные условия',
            is_preferential=True,
            credit_limit=Decimal('9000000'),
        )

        self.assertEqual(
            program.get_credit_limit(),
            Decimal('9000000'),
        )

    def test_regular_mortgage_has_no_credit_limit(self):
        """Проверяет отсутствие лимита для нельготной программы."""
        program = MortgageProgram.objects.create(
            name='Стандартная',
            condition='Базовые условия',
            is_preferential=False,
            credit_limit=Decimal('5000000'),
        )

        self.assertIsNone(program.get_credit_limit())

    def test_regional_credit_limit_overrides_program_credit_limit(self):
        """Проверяет региональное исключение кредитного лимита."""
        program = MortgageProgram.objects.create(
            name='Семейная',
            condition='Льготные условия',
            is_preferential=True,
            credit_limit=Decimal('6000000'),
        )
        region = Region.objects.create(name='Москва', code='77')
        MortgageProgramRegionalCreditLimit.objects.create(
            mortgage_program=program,
            region=region,
            credit_limit=Decimal('12000000'),
        )

        self.assertEqual(
            program.get_credit_limit(region),
            Decimal('12000000'),
        )

    def test_program_credit_limit_is_used_without_regional_exception(self):
        """Проверяет базовый лимит при отсутствии регионального исключения."""
        program = MortgageProgram.objects.create(
            name='Семейная',
            condition='Льготные условия',
            is_preferential=True,
            credit_limit=Decimal('6000000'),
        )
        region = Region.objects.create(name='Татарстан', code='16')

        self.assertEqual(
            program.get_credit_limit(region),
            Decimal('6000000'),
        )

    def test_mortgage_program_catalog_uses_credit_limit_field(self):
        """Проверяет поле кредитного лимита в справочнике ипотечных программ."""
        response = self.client.get(
            f'{reverse("bank:catalog")}?model=mortgage_program'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Кредитный лимит')
        self.assertNotContains(response, 'Тип льготной программы')

    def test_mortgage_program_catalog_formats_credit_limit(self):
        """Checks grouped credit limit formatting in the program catalog."""
        program = MortgageProgram.objects.create(
            name='Family mortgage',
            condition='Preferential terms',
            is_preferential=True,
            credit_limit=Decimal('12000000'),
        )

        response = self.client.get(
            (
                f'{reverse("bank:catalog")}'
                f'?model=mortgage_program&edit={program.pk}'
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '12 000 000,00')
        self.assertContains(response, 'value="12 000 000,00"')
        self.assertContains(response, 'data-grouped-decimal-input')
        self.assertNotContains(response, '12000000.00')

    def test_mortgage_program_catalog_accepts_grouped_credit_limit(self):
        """Checks saving grouped credit limit input in the program catalog."""
        response = self.client.post(
            reverse('bank:catalog'),
            {
                'action': 'save',
                'model': 'mortgage_program',
                'name': 'IT mortgage',
                'condition': 'Preferential terms',
                'is_preferential': 'on',
                'credit_limit': '9 000 000,00',
            },
        )

        self.assertRedirects(
            response,
            f'{reverse("bank:catalog")}?model=mortgage_program',
        )
        program = MortgageProgram.objects.get(name='IT mortgage')
        self.assertEqual(program.credit_limit, Decimal('9000000.00'))

    def test_regional_credit_limit_catalog_is_available(self):
        """Проверяет справочник региональных лимитов ипотечных программ."""
        response = self.client.get(
            (
                f'{reverse("bank:catalog")}'
                '?model=mortgage_program_regional_credit_limit'
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            'Региональные лимиты ипотечных программ',
        )
        self.assertContains(response, 'Ипотечная программа')
        self.assertContains(response, 'Регион')
        self.assertContains(response, 'Кредитный лимит')

    def test_regional_credit_limit_catalog_formats_credit_limit(self):
        """Checks grouped regional credit limit formatting in the catalog."""
        program = MortgageProgram.objects.create(
            name='Family mortgage',
            condition='Preferential terms',
            is_preferential=True,
            credit_limit=Decimal('6000000'),
        )
        region = Region.objects.create(name='Moscow', code='77')
        regional_credit_limit = (
            MortgageProgramRegionalCreditLimit.objects.create(
                mortgage_program=program,
                region=region,
                credit_limit=Decimal('12000000'),
            )
        )

        response = self.client.get(
            (
                f'{reverse("bank:catalog")}'
                '?model=mortgage_program_regional_credit_limit'
                f'&edit={regional_credit_limit.pk}'
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '12 000 000,00')
        self.assertContains(response, 'value="12 000 000,00"')
        self.assertContains(response, 'data-grouped-decimal-input')
        self.assertNotContains(response, '12000000.00')

    def test_regional_credit_limit_catalog_accepts_grouped_credit_limit(self):
        """Checks saving grouped regional credit limit input in the catalog."""
        program = MortgageProgram.objects.create(
            name='Family mortgage',
            condition='Preferential terms',
            is_preferential=True,
            credit_limit=Decimal('6000000'),
        )
        region = Region.objects.create(name='Moscow', code='77')

        response = self.client.post(
            reverse('bank:catalog'),
            {
                'action': 'save',
                'model': 'mortgage_program_regional_credit_limit',
                'mortgage_program': str(program.pk),
                'region': str(region.pk),
                'credit_limit': '12 000 000,00',
            },
        )

        self.assertRedirects(
            response,
            (
                f'{reverse("bank:catalog")}'
                '?model=mortgage_program_regional_credit_limit'
            ),
        )
        regional_credit_limit = (
            MortgageProgramRegionalCreditLimit.objects.get(
                mortgage_program=program,
                region=region,
            )
        )
        self.assertEqual(
            regional_credit_limit.credit_limit,
            Decimal('12000000.00'),
        )


class BankProgramCatalogTests(TestCase):
    """Checks bank mortgage program catalog behavior."""

    def setUp(self):
        """Log in as moderator for catalog mutation tests."""
        self.moderator = create_user_with_role(
            'bank-program-moderator@example.com',
            '+79991000001',
            MODERATOR_GROUP_NAME,
        )
        self.client.force_login(self.moderator)

    def test_bank_model_and_form_do_not_use_mortgage_condition_fields(self):
        """Checks bank conditions live only on bank programs."""
        bank_field_names = {
            field.name
            for field in Bank._meta.get_fields()
        }
        self.assertNotIn('interest_rate', bank_field_names)
        self.assertNotIn('salary_client_discount', bank_field_names)
        self.assertNotIn('maximum_loan_term_years', bank_field_names)

        form = BankForm()

        self.assertEqual(set(form.fields), {'name', 'logo_url'})

    def test_bank_catalog_limits_bank_table_to_ten_rows(self):
        """Checks bank catalog paginates banks by ten rows."""
        for index in range(12):
            Bank.objects.create(name=f'Bank {index:02d}')

        response = self.client.get(f'{reverse("bank:catalog")}?model=bank')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['rows']), 10)
        self.assertEqual(response.context['page_obj'].paginator.per_page, 10)
        self.assertContains(response, 'Bank 00')
        self.assertContains(response, 'Bank 09')
        self.assertNotContains(response, 'Bank 10')

    def test_bank_catalog_filter_uses_dynamic_filtering(self):
        """Checks bank filter does not render a manual apply button."""
        response = self.client.get(f'{reverse("bank:catalog")}?model=bank')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-catalog-filter-form')
        self.assertContains(response, 'data-catalog-filter-control')
        self.assertContains(response, 'name="filter_bank_scope"')
        self.assertContains(response, 'Все банки')
        self.assertContains(response, 'С ипотечными программами')
        self.assertNotContains(response, '>Применить</button>')

    def test_bank_catalog_scope_filter_shows_banks_with_programs(self):
        """Checks bank scope filter hides banks without mortgage programs."""
        bank_with_program = Bank.objects.create(name='Alpha Bank')
        bank_without_program = Bank.objects.create(name='Beta Bank')
        program = MortgageProgram.objects.create(
            name='Market mortgage',
            condition='Regular terms',
        )
        BankProgram.objects.create(
            bank=bank_with_program,
            mortgage_program=program,
            interest_rate=Decimal('12.50'),
            minimum_initial_payment_percent=Decimal('20.00'),
        )

        response = self.client.get(
            (
                f'{reverse("bank:catalog")}'
                '?model=bank&filter_bank_scope=with_programs'
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_bank'], bank_with_program)
        self.assertEqual(len(response.context['rows']), 1)
        self.assertContains(response, bank_with_program.name)
        self.assertNotContains(response, bank_without_program.name)

    def test_bank_catalog_shows_selected_bank_programs_and_detail_action(self):
        """Checks bank catalog side table and bank card action."""
        first_bank = Bank.objects.create(
            name='Alpha Bank',
            logo_url='https://img.example/alpha.svg',
        )
        second_bank = Bank.objects.create(name='Beta Bank')
        program = MortgageProgram.objects.create(
            name='Market mortgage',
            condition='Regular terms',
        )
        BankProgram.objects.create(
            bank=first_bank,
            mortgage_program=program,
            interest_rate=Decimal('12.50'),
            minimum_initial_payment_percent=Decimal('20.00'),
            maximum_loan_term_years=30,
        )

        response = self.client.get(
            (
                f'{reverse("bank:catalog")}'
                f'?model=bank&selected_bank={first_bank.pk}'
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_bank'], first_bank)
        self.assertContains(response, 'Market mortgage')
        self.assertContains(response, '12,50')
        self.assertContains(
            response,
            reverse('bank:bank_detail', kwargs={'pk': first_bank.pk}),
        )
        self.assertContains(response, second_bank.name)

    def test_bank_create_page_saves_bank_with_programs(self):
        """Checks separate bank create page saves linked programs."""
        program = MortgageProgram.objects.create(
            name='Market mortgage',
            condition='Regular terms',
        )

        response = self.client.post(
            reverse('bank:bank_create'),
            {
                'name': 'Alpha Bank',
                'logo_url': 'https://img.example/alpha.svg',
                'bankprogram_set-TOTAL_FORMS': '3',
                'bankprogram_set-INITIAL_FORMS': '0',
                'bankprogram_set-MIN_NUM_FORMS': '0',
                'bankprogram_set-MAX_NUM_FORMS': '1000',
                'bankprogram_set-0-mortgage_program': str(program.pk),
                'bankprogram_set-0-interest_rate': '12.50',
                'bankprogram_set-0-minimum_initial_payment_percent': '20.00',
                'bankprogram_set-0-maximum_loan_term_years': '30',
                'bankprogram_set-1-mortgage_program': '',
                'bankprogram_set-1-interest_rate': '',
                'bankprogram_set-1-minimum_initial_payment_percent': '',
                'bankprogram_set-1-maximum_loan_term_years': '',
                'bankprogram_set-2-mortgage_program': '',
                'bankprogram_set-2-interest_rate': '',
                'bankprogram_set-2-minimum_initial_payment_percent': '',
                'bankprogram_set-2-maximum_loan_term_years': '',
            },
        )

        bank = Bank.objects.get(name='Alpha Bank')

        self.assertRedirects(
            response,
            reverse('bank:bank_detail', kwargs={'pk': bank.pk}),
        )
        bank_program = BankProgram.objects.get(bank=bank)
        self.assertEqual(bank.logo_url, 'https://img.example/alpha.svg')
        self.assertEqual(bank_program.mortgage_program, program)
        self.assertEqual(bank_program.interest_rate, Decimal('12.50'))
        self.assertEqual(
            bank_program.minimum_initial_payment_percent,
            Decimal('20.00'),
        )
        self.assertEqual(bank_program.maximum_loan_term_years, 30)

    def test_bank_program_catalog_shows_rate_and_initial_payment_fields(self):
        """Checks new bank program fields are visible in the catalog."""
        bank = Bank.objects.create(
            name='Alpha Bank',
        )
        program = MortgageProgram.objects.create(
            name='Family mortgage',
            condition='Preferential terms',
        )
        BankProgram.objects.create(
            bank=bank,
            mortgage_program=program,
            interest_rate=Decimal('7.20'),
            minimum_initial_payment_percent=Decimal('20.00'),
            maximum_loan_term_years=30,
        )

        response = self.client.get(
            f'{reverse("bank:catalog")}?model=bank_program'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Процентная ставка, %')
        self.assertContains(response, 'Минимальный первый взнос, %')
        self.assertContains(response, 'Максимальный срок кредита, лет')
        self.assertContains(response, '7.20')
        self.assertContains(response, '20.00')
        self.assertContains(response, '30')

    def test_bank_program_catalog_saves_rate_and_initial_payment_fields(self):
        """Checks saving bank program rate and initial payment values."""
        bank = Bank.objects.create(
            name='Alpha Bank',
        )
        program = MortgageProgram.objects.create(
            name='Family mortgage',
            condition='Preferential terms',
        )

        response = self.client.post(
            reverse('bank:catalog'),
            {
                'action': 'save',
                'model': 'bank_program',
                'bank': str(bank.pk),
                'mortgage_program': str(program.pk),
                'interest_rate': '7.20',
                'minimum_initial_payment_percent': '20.00',
                'maximum_loan_term_years': '30',
            },
        )

        self.assertRedirects(
            response,
            f'{reverse("bank:catalog")}?model=bank_program',
        )
        bank_program = BankProgram.objects.get(
            bank=bank,
            mortgage_program=program,
        )
        self.assertEqual(bank_program.interest_rate, Decimal('7.20'))
        self.assertEqual(
            bank_program.minimum_initial_payment_percent,
            Decimal('20.00'),
        )
        self.assertEqual(bank_program.maximum_loan_term_years, 30)

    def test_bank_program_bank_filter_uses_select_and_filters_rows(self):
        """Checks the bank program bank filter is a select control."""
        first_bank = Bank.objects.create(
            name='Alpha Bank',
        )
        second_bank = Bank.objects.create(
            name='Beta Bank',
        )
        program = MortgageProgram.objects.create(
            name='Family mortgage',
            condition='Preferential terms',
        )
        BankProgram.objects.create(
            bank=first_bank,
            mortgage_program=program,
            interest_rate=Decimal('7.20'),
            minimum_initial_payment_percent=Decimal('20.00'),
        )
        BankProgram.objects.create(
            bank=second_bank,
            mortgage_program=program,
            interest_rate=Decimal('8.10'),
            minimum_initial_payment_percent=Decimal('25.00'),
        )

        response = self.client.get(
            (
                f'{reverse("bank:catalog")}'
                f'?model=bank_program&filter_bank={first_bank.pk}'
            )
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="filter_bank"')
        self.assertContains(response, '<select name="filter_bank"')
        self.assertEqual(len(response.context['rows']), 1)
        row_values = [
            cell['value']
            for cell in response.context['rows'][0]['cells']
        ]
        self.assertIn(first_bank.name, row_values)
        self.assertNotIn(second_bank.name, row_values)

    def test_bank_catalog_delete_cascades_bank_program_links(self):
        """Checks deleting a bank removes its program links without an error."""
        bank = Bank.objects.create(
            name='Alpha Bank',
        )
        program = MortgageProgram.objects.create(
            name='Market mortgage',
            condition='Regular terms',
        )
        BankProgram.objects.create(
            bank=bank,
            mortgage_program=program,
            interest_rate=Decimal('11.50'),
            minimum_initial_payment_percent=Decimal('20.00'),
        )

        response = self.client.post(
            reverse('bank:catalog'),
            {
                'action': 'delete',
                'model': 'bank',
                'object_id': str(bank.pk),
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Bank.objects.filter(pk=bank.pk).exists())
        self.assertFalse(BankProgram.objects.filter(bank=bank).exists())
        self.assertTrue(MortgageProgram.objects.filter(pk=program.pk).exists())
        self.assertNotContains(response, 'есть связанные записи')

    def test_anonymous_bank_catalog_is_read_only(self):
        """Checks anonymous users can read banks but cannot mutate catalogs."""
        self.client.logout()
        Bank.objects.create(name='Alpha Bank')

        response = self.client.get(f'{reverse("bank:catalog")}?model=bank')
        post_response = self.client.post(
            reverse('bank:catalog'),
            {
                'action': 'save',
                'model': 'bank',
                'name': 'Beta Bank',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Alpha Bank')
        self.assertNotContains(response, reverse('bank:bank_create'))
        self.assertNotContains(response, 'import_catalog')
        self.assertEqual(post_response.status_code, 403)
        self.assertFalse(Bank.objects.filter(name='Beta Bank').exists())

class KeyRateListViewTests(TestCase):
    def setUp(self):
        """Log in as application administrator for key rate sync tests."""
        self.client.force_login(
            create_user_with_role(
                'key-rate-admin@example.com',
                '+79991000003',
                APPLICATION_ADMINISTRATOR_GROUP_NAME,
            )
        )

    def test_key_rate_list_paginates_rows(self):
        for index in range(21):
            KeyRate.objects.create(
                meeting_date=date(2026, 1, 1) + timedelta(days=index),
                key_rate=Decimal('16.00'),
            )

        response = self.client.get(reverse('bank:key_rate_list'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['rows']), 20)
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(response.context['page_obj'].paginator.per_page, 20)

    def test_manual_sync_posts_to_key_rate_sync(self):
        with patch(
            'bank.views.sync_key_rates',
            return_value={'created': 1, 'updated': 2, 'processed': 3},
        ) as sync_key_rates_mock:
            response = self.client.post(reverse('bank:key_rate_list'))

        self.assertRedirects(response, reverse('bank:key_rate_list'))
        sync_key_rates_mock.assert_called_once_with()

        messages = [
            str(message)
            for message in get_messages(response.wsgi_request)
        ]
        self.assertEqual(len(messages), 1)
        self.assertIn('создано=1', messages[0])
        self.assertIn('обновлено=2', messages[0])
        self.assertIn('обработано=3', messages[0])

    def test_manual_sync_message_is_rendered_once(self):
        """Checks key rate sync message is rendered once and is dismissible."""
        with patch(
            'bank.views.sync_key_rates',
            return_value={'created': 1, 'updated': 2, 'processed': 3},
        ):
            response = self.client.post(
                reverse('bank:key_rate_list'),
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"', count=1)
        self.assertContains(
            response,
            'data-bs-dismiss="alert"',
            count=1,
        )

    def test_manual_sync_shows_error_message(self):
        with patch(
            'bank.views.sync_key_rates',
            side_effect=KeyRateSyncError('Сервис недоступен'),
        ):
            response = self.client.post(reverse('bank:key_rate_list'))

        self.assertRedirects(response, reverse('bank:key_rate_list'))

        messages = [
            str(message)
            for message in get_messages(response.wsgi_request)
        ]
        self.assertEqual(len(messages), 1)
        self.assertIn('Не удалось обновить данные ключевой ставки', messages[0])

    def test_moderator_cannot_run_key_rate_sync(self):
        """Checks key rate sync requires administrator role."""
        moderator = create_user_with_role(
            'key-rate-moderator@example.com',
            '+79991000004',
            MODERATOR_GROUP_NAME,
        )
        self.client.force_login(moderator)

        with patch('bank.views.sync_key_rates') as sync_key_rates_mock:
            response = self.client.post(reverse('bank:key_rate_list'))

        self.assertEqual(response.status_code, 403)
        sync_key_rates_mock.assert_not_called()
