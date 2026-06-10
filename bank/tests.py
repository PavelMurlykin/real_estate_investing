from decimal import Decimal
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from location.models import Region

from .key_rate_sync import KeyRateSyncError
from .models import MortgageProgram


class MortgageProgramCreditLimitTests(TestCase):
    """Проверяет лимиты кредита по льготным ипотечным программам."""

    def test_information_technology_mortgage_credit_limit_is_nine_million(
        self,
    ):
        """Проверяет лимит IT-ипотеки."""
        program_type = (
            MortgageProgram.PREFERENTIAL_PROGRAM_TYPE_INFORMATION_TECHNOLOGY
        )
        program = MortgageProgram.objects.create(
            name='IT-ипотека',
            condition='Льготные условия',
            is_preferential=True,
            preferential_program_type=program_type,
        )

        self.assertEqual(
            program.get_credit_limit(),
            Decimal('9000000'),
        )

    def test_family_mortgage_uses_high_cost_region_credit_limit(self):
        """Проверяет повышенный лимит семейной ипотеки для Москвы."""
        program_type = MortgageProgram.PREFERENTIAL_PROGRAM_TYPE_FAMILY
        program = MortgageProgram.objects.create(
            name='Семейная',
            condition='Льготные условия',
            is_preferential=True,
            preferential_program_type=program_type,
        )
        region = Region.objects.create(name='Москва', code='77')

        self.assertEqual(
            program.get_credit_limit(region),
            Decimal('12000000'),
        )

    def test_family_mortgage_uses_default_region_credit_limit(self):
        """Проверяет базовый лимит семейной ипотеки для остальных регионов."""
        program_type = MortgageProgram.PREFERENTIAL_PROGRAM_TYPE_FAMILY
        program = MortgageProgram.objects.create(
            name='Семейная',
            condition='Льготные условия',
            is_preferential=True,
            preferential_program_type=program_type,
        )
        region = Region.objects.create(name='Татарстан', code='16')

        self.assertEqual(
            program.get_credit_limit(region),
            Decimal('6000000'),
        )


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
