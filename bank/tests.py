from decimal import Decimal
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from location.models import Region

from .key_rate_sync import KeyRateSyncError
from .models import (
    Bank,
    BankProgram,
    MortgageProgram,
    MortgageProgramRegionalCreditLimit,
)


class MortgageProgramCreditLimitTests(TestCase):
    """Проверяет лимиты кредита по льготным ипотечным программам."""

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

    def test_bank_program_catalog_shows_rate_and_initial_payment_fields(self):
        """Checks new bank program fields are visible in the catalog."""
        bank = Bank.objects.create(
            name='Alpha Bank',
            interest_rate=Decimal('11.50'),
            salary_client_discount=Decimal('0.50'),
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
        )

        response = self.client.get(
            f'{reverse("bank:catalog")}?model=bank_program'
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Процентная ставка, %')
        self.assertContains(response, 'Минимальный первый взнос, %')
        self.assertContains(response, '7.20')
        self.assertContains(response, '20.00')

    def test_bank_program_catalog_saves_rate_and_initial_payment_fields(self):
        """Checks saving bank program rate and initial payment values."""
        bank = Bank.objects.create(
            name='Alpha Bank',
            interest_rate=Decimal('11.50'),
            salary_client_discount=Decimal('0.50'),
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

    def test_bank_program_bank_filter_uses_select_and_filters_rows(self):
        """Checks the bank program bank filter is a select control."""
        first_bank = Bank.objects.create(
            name='Alpha Bank',
            interest_rate=Decimal('11.50'),
            salary_client_discount=Decimal('0.50'),
        )
        second_bank = Bank.objects.create(
            name='Beta Bank',
            interest_rate=Decimal('12.50'),
            salary_client_discount=Decimal('0.50'),
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


class KeyRateListViewTests(TestCase):
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
