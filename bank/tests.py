from decimal import Decimal
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from location.models import Region

from .key_rate_sync import KeyRateSyncError
from .mortgage_offer_sync import (
    MARKET_MORTGAGE_PROGRAM_NAME,
    parse_banki_mortgage_offers,
    sync_bank_mortgage_offers,
)
from .models import (
    Bank,
    BankProgram,
    MortgageProgram,
    MortgageProgramRegionalCreditLimit,
)

SAMPLE_BANKI_MORTGAGE_HTML = '''
<html>
  <body>
    <article>
      <img alt="ВТБ" srcset="/logos/vtb-small.svg 1x, /logos/vtb.svg 2x">
      <h2>ВТБ</h2>
      <div>Вторичное жилье</div>
      <div>ПСК</div>
      <div>23.446%–31.458%</div>
      <div>Ставка</div>
      <div>22.3%–23.2%</div>
      <div>Платёж</div>
      <div>от 28 455 ₽</div>
      <div>Первоначальный взнос</div>
      <div>от 20.1%</div>
      <div>Срок</div>
      <div>до 30 лет</div>
      <div>Дополнительные условия: минимальная ставка — для текущих и новых
      зарплатных клиентов, при невыполнении условия +0,8 п. п. к ставке</div>
    </article>
    <article>
      <img alt="Альфа-Банк" data-srcset="https://img.example/alpha.svg 1x">
      <h2>Альфа-Банк</h2>
      <div>На вторичное жильё</div>
      <div>Ставка</div>
      <div>19.99%–20.39%</div>
      <div>Первоначальный взнос</div>
      <div>от 20.1%</div>
      <div>Срок</div>
      <div>до 25 лет</div>
      <div>Пониженная ставка</div>
      <div>до -0.4% к вашей ставке</div>
    </article>
    <article>
      <h2>Банк без логотипа</h2>
      <div>Готовое жилье</div>
      <div>Подробнее</div>
      <div>Ставка</div>
      <div>17.99%–19.99%</div>
      <div>Первоначальный взнос</div>
      <div>от 25%</div>
      <div>Срок</div>
      <div>до 20 лет</div>
    </article>
    <article>
      <img alt="Т-Банк" src="/logos/tbank.svg">
      <h2>Т-Банк</h2>
      <div>Семейная ипотека</div>
      <div>Ставка</div>
      <div>4%</div>
      <div>Первоначальный взнос</div>
      <div>от 20%</div>
    </article>
    <a href="/products/hypothec/?page=2">Показать ещё</a>
  </body>
</html>
'''

SAMPLE_BANKI_MORTGAGE_SECOND_PAGE_HTML = '''
<html>
  <body>
    <article>
      <img alt="Газпромбанк" src="/logos/gpb.svg">
      <h2>Газпромбанк</h2>
      <div>Ипотека на квартиру</div>
      <div>Подробнее</div>
      <div>Ставка</div>
      <div>21.5%</div>
      <div>Первоначальный взнос</div>
      <div>от 30%</div>
      <div>Срок</div>
      <div>до 30 лет</div>
    </article>
  </body>
</html>
'''


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


class BankMortgageOfferSyncTests(TestCase):
    """Checks parsing and synchronization of bank mortgage offers."""

    def test_parse_banki_mortgage_offers_extracts_market_offers(self):
        """Checks parser extracts market offers and skips preferential ones."""
        offers = parse_banki_mortgage_offers(
            SAMPLE_BANKI_MORTGAGE_HTML,
            source_url='https://www.banki.ru/products/hypothec/',
        )

        self.assertEqual(len(offers), 3)
        self.assertEqual(offers[0].bank_name, 'ВТБ')
        self.assertEqual(offers[0].interest_rate, Decimal('23.2'))
        self.assertEqual(
            offers[0].minimum_initial_payment_percent,
            Decimal('20.1'),
        )
        self.assertEqual(offers[0].salary_client_discount, Decimal('0.8'))
        self.assertEqual(offers[0].maximum_loan_term_years, 30)
        self.assertEqual(
            offers[0].logo_url,
            'https://www.banki.ru/logos/vtb-small.svg',
        )
        self.assertEqual(offers[1].bank_name, 'Альфа-Банк')
        self.assertEqual(offers[1].interest_rate, Decimal('20.39'))
        self.assertEqual(offers[1].salary_client_discount, Decimal('0.4'))
        self.assertEqual(offers[2].bank_name, 'Банк без логотипа')
        self.assertEqual(offers[2].interest_rate, Decimal('19.99'))
        self.assertEqual(offers[2].maximum_loan_term_years, 20)
        self.assertEqual(offers[2].logo_url, '')

    def test_parse_banki_mortgage_offers_skips_too_long_bank_name(self):
        """Checks parser rejects text fragments that cannot fit Bank.name."""
        invalid_bank_name = 'Очень длинное описание ипотечного предложения ' * 8
        raw_html = f'''
        <html>
          <body>
            <article>
              <h2>{invalid_bank_name}</h2>
              <div>Ипотека на квартиру</div>
              <div>Подробнее</div>
              <div>Ставка</div>
              <div>18.5%</div>
              <div>Первоначальный взнос</div>
              <div>от 20%</div>
            </article>
            <article>
              <h2>Надежный Банк</h2>
              <div>Ипотека на квартиру</div>
              <div>Подробнее</div>
              <div>Ставка</div>
              <div>19.5%</div>
              <div>Первоначальный взнос</div>
              <div>от 25%</div>
            </article>
          </body>
        </html>
        '''

        offers = parse_banki_mortgage_offers(
            raw_html,
            source_url='https://www.banki.ru/products/hypothec/',
        )

        self.assertEqual(len(offers), 1)
        self.assertEqual(offers[0].bank_name, 'Надежный Банк')

    def test_sync_bank_mortgage_offers_creates_banks_and_program_links(self):
        """Checks synchronization loads banks and market mortgage conditions."""
        def fake_download(source_url):
            if 'page=2' in source_url:
                return SAMPLE_BANKI_MORTGAGE_SECOND_PAGE_HTML
            return SAMPLE_BANKI_MORTGAGE_HTML

        with patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            side_effect=fake_download,
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/'
            )

        self.assertEqual(result['created'], 4)
        self.assertEqual(result['processed'], 4)
        bank = Bank.objects.get(name='ВТБ')
        self.assertEqual(bank.interest_rate, Decimal('23.2'))
        self.assertEqual(bank.salary_client_discount, Decimal('0.8'))
        self.assertEqual(bank.maximum_loan_term_years, 30)
        self.assertEqual(
            bank.logo_url,
            'https://www.banki.ru/logos/vtb-small.svg',
        )
        self.assertTrue(Bank.objects.filter(name='Газпромбанк').exists())
        bank_program = BankProgram.objects.get(
            bank=bank,
            mortgage_program__name=MARKET_MORTGAGE_PROGRAM_NAME,
        )
        self.assertEqual(bank_program.interest_rate, Decimal('23.2'))
        self.assertEqual(
            bank_program.minimum_initial_payment_percent,
            Decimal('20.1'),
        )
        self.assertEqual(bank_program.maximum_loan_term_years, 30)

    def test_bank_catalog_shows_bank_logo_before_name(self):
        """Checks bank logo is rendered in the bank catalog name column."""
        Bank.objects.create(
            name='Alpha Bank',
            logo_url='https://img.example/alpha.svg',
            interest_rate=Decimal('11.50'),
            salary_client_discount=Decimal('0.50'),
            maximum_loan_term_years=25,
        )

        response = self.client.get(f'{reverse("bank:catalog")}?model=bank')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="bank-logo"')
        self.assertContains(response, 'src="https://img.example/alpha.svg"')
        self.assertContains(response, '>Alpha Bank</span>')
        self.assertContains(response, 'Максимальный срок кредита, лет')
        self.assertContains(response, '25')

    def test_bank_catalog_sync_button_runs_mortgage_offer_sync(self):
        """Checks bank catalog update button runs mortgage offer sync."""
        with patch(
            'bank.views.sync_bank_mortgage_offers',
            return_value={'created': 1, 'updated': 2, 'processed': 3},
        ) as sync_mock:
            response = self.client.post(
                reverse('bank:catalog'),
                {
                    'action': 'sync_bank_mortgage_offers',
                    'model': 'bank',
                },
            )

        self.assertRedirects(response, f'{reverse("bank:catalog")}?model=bank')
        sync_mock.assert_called_once_with()
        messages = [
            str(message)
            for message in get_messages(response.wsgi_request)
        ]
        self.assertEqual(len(messages), 1)
        self.assertIn('создано=1', messages[0])
        self.assertIn('обновлено=2', messages[0])
        self.assertIn('обработано=3', messages[0])

    def test_bank_catalog_sync_message_is_rendered_once(self):
        """Checks bank sync message is not duplicated in the rendered page."""
        with patch(
            'bank.views.sync_bank_mortgage_offers',
            return_value={'created': 1, 'updated': 2, 'processed': 3},
        ):
            response = self.client.post(
                reverse('bank:catalog'),
                {
                    'action': 'sync_bank_mortgage_offers',
                    'model': 'bank',
                },
                follow=True,
            )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'role="alert"', count=1)
        self.assertContains(
            response,
            'data-bs-dismiss="alert"',
            count=1,
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
