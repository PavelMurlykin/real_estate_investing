from decimal import Decimal
from unittest.mock import patch

from django.contrib.messages import get_messages
from django.test import TestCase
from django.urls import reverse

from location.models import Region

from .forms import BankForm
from .key_rate_sync import KeyRateSyncError
from .mortgage_offer_sync import (
    _normalize_bank_match_name,
    FEDERAL_REFERENCE_SOURCE_NAME,
    normalize_bank_name_for_storage,
    parse_reference_mortgage_programs,
    parse_cbr_bank_records,
    parse_banki_mortgage_offers,
    parse_google_sheet_mortgage_offers,
    sync_bank_mortgage_offers,
)
from .models import (
    Bank,
    BankProgram,
    MortgageProgram,
    MortgageProgramAlias,
    MortgageProgramRegionalCreditLimit,
)

SAMPLE_BANKI_MORTGAGE_HTML = '''
<html>
  <body>
    <article>
      <img alt="ВТБ" srcset="/logos/vtb-small.svg 1x, /logos/vtb.svg 2x">
      <h2>ВТБ</h2>
      <div>Вторичное жилье</div>
      <div>Подробнее</div>
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
      <div>Подробнее</div>
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
      <div>Подробнее</div>
      <div>Ставка</div>
      <div>4%</div>
      <div>Первоначальный взнос</div>
      <div>от 20%</div>
    </article>
    <a href="/products/hypothec/?page=2">Показать ещё</a>
  </body>
</html>
'''

SAMPLE_CBR_BANK_LIST_HTML = '''
<html>
  <body>
    <table>
      <tr>
        <th>№ п/п</th>
        <th>Вид</th>
        <th>Регистрационный номер</th>
        <th>ОГРН</th>
        <th>Наименование</th>
        <th>Организационно-правовая форма</th>
        <th>Дата регистрации Банком России</th>
        <th>Статус лицензии</th>
        <th>Местонахождение</th>
      </tr>
      <tr>
        <td>1</td>
        <td></td>
        <td>1000</td>
        <td>1020000000001</td>
        <td>Банк ВТБ (ПАО)</td>
        <td>ПАО</td>
        <td>01.01.1990</td>
        <td>Действующая</td>
        <td>Москва</td>
      </tr>
      <tr>
        <td>2</td>
        <td></td>
        <td>2000</td>
        <td>1020000000002</td>
        <td>АО «Альфа-Банк»</td>
        <td>НПАО</td>
        <td>01.01.1990</td>
        <td>Действующая</td>
        <td>Москва</td>
      </tr>
      <tr>
        <td>3</td>
        <td></td>
        <td>3000</td>
        <td>1020000000003</td>
        <td>Банк без логотипа</td>
        <td>ПАО</td>
        <td>01.01.1990</td>
        <td>Действующая</td>
        <td>Москва</td>
      </tr>
      <tr>
        <td>4</td>
        <td></td>
        <td>4000</td>
        <td>1020000000004</td>
        <td>Т-Банк</td>
        <td>НПАО</td>
        <td>01.01.1990</td>
        <td>Действующая</td>
        <td>Москва</td>
      </tr>
      <tr>
        <td>5</td>
        <td></td>
        <td>5000</td>
        <td>1020000000005</td>
        <td>Газпромбанк</td>
        <td>ПАО</td>
        <td>01.01.1990</td>
        <td>Действующая</td>
        <td>Москва</td>
      </tr>
      <tr>
        <td>6</td>
        <td>Расчетная НКО</td>
        <td>6000</td>
        <td>1020000000006</td>
        <td>НКО «Платежный Центр»</td>
        <td>ООО</td>
        <td>01.01.1990</td>
        <td>Действующая</td>
        <td>Москва</td>
      </tr>
      <tr>
        <td>7</td>
        <td></td>
        <td>7000</td>
        <td>1020000000007</td>
        <td>Отозванный Банк</td>
        <td>ПАО</td>
        <td>01.01.1990</td>
        <td>Отозванная</td>
        <td>Москва</td>
      </tr>
    </table>
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

SAMPLE_GOOGLE_FAMILY_MORTGAGE_CSV = '''
"Описание","Условия","Банк","Регион","Прием заявок","Выдачи","Ставка","Мин ПВ"
"","","Банк ВТБ","МСК","да","да","6,00%","40,10%"
"","","Альфа-Банк","МСК","да","да","5,90%–6,20%","20,10%"
'''

SAMPLE_GOOGLE_IT_MORTGAGE_CSV = '''
"Описание","Банк","Регион","Прием заявок","Выдачи","Ставка","Мин ПВ"
"","Альфа-Банк","МСК","да","да","5,70%","20,01%"
"","Газпромбанк","МСК","да","да","5,99%","20,10%"
'''

SAMPLE_REFERENCE_MORTGAGE_PROGRAMS_HTML = '''
<html>
  <body>
    <main>
      <h1>Льготы по ипотеке</h1>
      <a href="/catalog/family/">Семейная ипотека</a>
      <a href="/catalog/it/">IT-ипотека</a>
      <a href="/catalog/arctic/">Дальневосточная и арктическая ипотека</a>
      <a href="/catalog/family-duplicate/">Семейная ипотека</a>
    </main>
  </body>
</html>
'''

SAMPLE_BANKI_DUPLICATE_PROGRAM_NAME_HTML = '''
<html>
  <body>
    <article>
      <h2>Т-Банк</h2>
      <div>Ипотека для семей с детьми</div>
      <div>Подробнее</div>
      <div>Ставка</div>
      <div>6%</div>
      <div>Первоначальный взнос</div>
      <div>от 20%</div>
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


class BankMortgageOfferSyncTests(TestCase):
    """Checks parsing and synchronization of bank mortgage offers."""

    def setUp(self):
        """Patch external reference source downloads for sync tests."""
        super().setUp()
        self.reference_program_patch = patch(
            'bank.mortgage_offer_sync.'
            '_download_reference_mortgage_programs_payload',
            return_value=SAMPLE_REFERENCE_MORTGAGE_PROGRAMS_HTML,
        )
        self.reference_program_download_mock = (
            self.reference_program_patch.start()
        )
        self.addCleanup(self.reference_program_patch.stop)

    def test_normalize_bank_name_for_storage_removes_legal_wrappers(self):
        """Checks imported bank names are cleaned before saving."""
        self.assertEqual(
            normalize_bank_name_for_storage(
                '  ПАО «„Тестовый Банк“» [АО] {ООО}  '
            ),
            'Тестовый Банк',
        )

    def test_normalize_bank_match_name_ignores_spacing_and_punctuation(self):
        """Checks bank matching ignores spaces and punctuation."""
        expected_key = _normalize_bank_match_name('ТБанк')

        self.assertEqual(_normalize_bank_match_name('Т - Банк'), expected_key)
        self.assertEqual(_normalize_bank_match_name('Т — Банк'), expected_key)
        self.assertEqual(_normalize_bank_match_name('Т. Банк'), expected_key)
        self.assertEqual(_normalize_bank_match_name('Банк ВТБ'), 'втб')

    def test_parse_cbr_bank_records_extracts_active_banks_only(self):
        """Checks CBR parser skips non-banks and inactive banks."""
        records = parse_cbr_bank_records(SAMPLE_CBR_BANK_LIST_HTML)

        self.assertEqual(
            [record.name for record in records],
            [
                'Банк ВТБ',
                'Альфа-Банк',
                'Банк без логотипа',
                'Т-Банк',
                'Газпромбанк',
            ],
        )

    def test_parse_reference_mortgage_programs_extracts_unique_names(self):
        """Checks reference parser extracts unique preferential programs."""
        records = parse_reference_mortgage_programs(
            SAMPLE_REFERENCE_MORTGAGE_PROGRAMS_HTML
        )

        self.assertEqual(
            [record.name for record in records],
            [
                'Семейная ипотека',
                'IT-ипотека',
                'Дальневосточная и арктическая ипотека',
            ],
        )

    def test_sync_uses_federal_reference_when_source_is_unavailable(self):
        """Checks sync falls back to federal program reference records."""
        self.reference_program_download_mock.side_effect = OSError('403')

        with patch(
            'bank.mortgage_offer_sync._download_cbr_bank_list_payload',
            return_value=SAMPLE_CBR_BANK_LIST_HTML,
        ), patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            return_value=SAMPLE_BANKI_DUPLICATE_PROGRAM_NAME_HTML,
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/',
                cbr_source_url='https://www.cbr.ru/banking_sector/credit/FullCoList/',
                google_sheet_sources=(),
            )

        self.assertEqual(result['reference_programs_processed'], 6)
        self.assertTrue(
            any(
                'Эталонный источник ипотечных программ не обработан'
                in warning
                for warning in result['warnings']
            )
        )
        self.assertTrue(
            MortgageProgramAlias.objects.filter(
                source=FEDERAL_REFERENCE_SOURCE_NAME,
                source_name='Семейная ипотека',
                mortgage_program__name='Семейная ипотека',
            ).exists()
        )

    def test_sync_reports_google_sheet_source_errors(self):
        """Checks Google Sheets errors do not stop successful sync."""
        with patch(
            'bank.mortgage_offer_sync._download_cbr_bank_list_payload',
            return_value=SAMPLE_CBR_BANK_LIST_HTML,
        ), patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            return_value=SAMPLE_BANKI_MORTGAGE_HTML,
        ), patch(
            'bank.mortgage_offer_sync._download_google_sheet_mortgage_payload',
            side_effect=ConnectionResetError('connection reset'),
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/',
                cbr_source_url='https://www.cbr.ru/banking_sector/credit/FullCoList/',
                google_sheet_sources=(
                    {
                        'program_name': 'Семейная ипотека',
                        'source_url': 'https://example.test/family.csv',
                        'bank_column_index': 2,
                        'rate_column_index': 6,
                        'initial_payment_column_index': 7,
                    },
                ),
            )

        self.assertGreater(result['processed'], 0)
        self.assertTrue(
            any(
                'Google Sheets источник не обработан' in warning
                for warning in result['warnings']
            )
        )

    def test_parse_banki_mortgage_offers_extracts_all_program_types(self):
        """Checks parser extracts market and preferential mortgage offers."""
        offers = parse_banki_mortgage_offers(
            SAMPLE_BANKI_MORTGAGE_HTML,
            source_url='https://www.banki.ru/products/hypothec/',
        )

        self.assertEqual(len(offers), 4)
        self.assertEqual(offers[0].bank_name, 'ВТБ')
        self.assertEqual(offers[0].interest_rate, Decimal('23.2'))
        self.assertEqual(
            offers[0].minimum_initial_payment_percent,
            Decimal('20.1'),
        )
        self.assertEqual(offers[0].maximum_loan_term_years, 30)
        self.assertEqual(
            offers[0].logo_url,
            'https://www.banki.ru/logos/vtb.svg',
        )
        self.assertEqual(offers[1].bank_name, 'Альфа-Банк')
        self.assertEqual(offers[1].interest_rate, Decimal('20.39'))
        self.assertEqual(offers[2].bank_name, 'Банк без логотипа')
        self.assertEqual(offers[2].interest_rate, Decimal('19.99'))
        self.assertEqual(offers[2].maximum_loan_term_years, 20)
        self.assertEqual(offers[2].logo_url, '')
        self.assertEqual(offers[3].bank_name, 'Т-Банк')
        self.assertEqual(offers[3].program_name, 'Семейная ипотека')
        self.assertEqual(offers[3].interest_rate, Decimal('4'))

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

    def test_parse_google_sheet_mortgage_offers_extracts_configured_columns(self):
        """Checks Google Sheets parser uses configured column indexes."""
        offers = parse_google_sheet_mortgage_offers(
            SAMPLE_GOOGLE_FAMILY_MORTGAGE_CSV,
            program_name='Семейная ипотека',
            bank_column_index=2,
            rate_column_index=6,
            initial_payment_column_index=7,
        )

        self.assertEqual(len(offers), 2)
        self.assertEqual(offers[0].bank_name, 'Банк ВТБ')
        self.assertEqual(offers[0].program_name, 'Семейная ипотека')
        self.assertEqual(offers[0].interest_rate, Decimal('6.00'))
        self.assertEqual(
            offers[0].minimum_initial_payment_percent,
            Decimal('40.10'),
        )
        self.assertEqual(offers[1].bank_name, 'Альфа-Банк')
        self.assertEqual(offers[1].interest_rate, Decimal('6.20'))

    def test_sync_bank_mortgage_offers_creates_banks_and_program_links(self):
        """Checks synchronization loads CBR banks and Banki.ru programs."""
        def fake_download(source_url):
            if 'page=2' in source_url:
                return SAMPLE_BANKI_MORTGAGE_SECOND_PAGE_HTML
            return SAMPLE_BANKI_MORTGAGE_HTML

        with patch(
            'bank.mortgage_offer_sync._download_cbr_bank_list_payload',
            return_value=SAMPLE_CBR_BANK_LIST_HTML,
        ), patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            side_effect=fake_download,
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/',
                cbr_source_url='https://www.cbr.ru/banking_sector/credit/FullCoList/',
                google_sheet_sources=(),
            )

        self.assertEqual(result['created'], 5)
        self.assertEqual(result['processed'], 5)
        self.assertEqual(result['skipped'], 0)
        bank = Bank.objects.get(name='Банк ВТБ')
        self.assertEqual(
            bank.logo_url,
            'https://www.banki.ru/logos/vtb.svg',
        )
        self.assertTrue(Bank.objects.filter(name='Газпромбанк').exists())
        self.assertFalse(Bank.objects.filter(name='Отозванный Банк').exists())
        bank_program = BankProgram.objects.get(
            bank=bank,
            mortgage_program__name='Вторичное жилье',
        )
        self.assertEqual(bank_program.interest_rate, Decimal('23.2'))
        self.assertEqual(
            bank_program.minimum_initial_payment_percent,
            Decimal('20.1'),
        )
        self.assertEqual(bank_program.maximum_loan_term_years, 30)
        self.assertTrue(
            BankProgram.objects.filter(
                bank__name='Т-Банк',
                mortgage_program__name='Семейная ипотека',
            ).exists()
        )

    def test_sync_bank_mortgage_offers_skips_unknown_banki_banks(self):
        """Checks Banki.ru offers are not added when absent from CBR list."""
        cbr_html = SAMPLE_CBR_BANK_LIST_HTML.replace(
            '<td>Банк без логотипа</td>',
            '<td>Другой Банк</td>',
        )

        with patch(
            'bank.mortgage_offer_sync._download_cbr_bank_list_payload',
            return_value=cbr_html,
        ), patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            return_value=SAMPLE_BANKI_MORTGAGE_HTML,
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/',
                cbr_source_url='https://www.cbr.ru/banking_sector/credit/FullCoList/',
                google_sheet_sources=(),
            )

        self.assertEqual(result['processed'], 3)
        self.assertEqual(result['skipped'], 1)
        self.assertFalse(
            BankProgram.objects.filter(
                bank__name='Банк без логотипа',
                mortgage_program__name='Готовое жилье',
            ).exists()
        )

    def test_sync_bank_mortgage_offers_loads_google_sheet_programs(self):
        """Checks Google Sheets sources update family and IT mortgages."""
        def fake_download_google_sheet(source_url):
            if source_url == 'https://example.test/family.csv':
                return SAMPLE_GOOGLE_FAMILY_MORTGAGE_CSV
            return SAMPLE_GOOGLE_IT_MORTGAGE_CSV

        with patch(
            'bank.mortgage_offer_sync._download_cbr_bank_list_payload',
            return_value=SAMPLE_CBR_BANK_LIST_HTML,
        ), patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            return_value=SAMPLE_BANKI_MORTGAGE_HTML,
        ), patch(
            'bank.mortgage_offer_sync._download_google_sheet_mortgage_payload',
            side_effect=fake_download_google_sheet,
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/',
                cbr_source_url='https://www.cbr.ru/banking_sector/credit/FullCoList/',
                google_sheet_sources=(
                    {
                        'program_name': 'Семейная ипотека',
                        'source_url': 'https://example.test/family.csv',
                        'bank_column_index': 2,
                        'rate_column_index': 6,
                        'initial_payment_column_index': 7,
                    },
                    {
                        'program_name': 'IT-ипотека',
                        'source_url': 'https://example.test/it.csv',
                        'bank_column_index': 1,
                        'rate_column_index': 5,
                        'initial_payment_column_index': 6,
                    },
                ),
            )

        self.assertEqual(result['google_sheet_offers_processed'], 4)
        family_program = BankProgram.objects.get(
            bank__name='Банк ВТБ',
            mortgage_program__name='Семейная ипотека',
        )
        self.assertEqual(family_program.interest_rate, Decimal('6.00'))
        self.assertEqual(
            family_program.minimum_initial_payment_percent,
            Decimal('40.10'),
        )
        it_program = BankProgram.objects.get(
            bank__name='Альфа-Банк',
            mortgage_program__name='IT-ипотека',
        )
        self.assertEqual(it_program.interest_rate, Decimal('5.70'))
        self.assertEqual(
            it_program.minimum_initial_payment_percent,
            Decimal('20.01'),
        )

    def test_sync_bank_mortgage_offers_maps_duplicate_program_names(self):
        """Checks imported duplicate program names use canonical program."""
        with patch(
            'bank.mortgage_offer_sync._download_cbr_bank_list_payload',
            return_value=SAMPLE_CBR_BANK_LIST_HTML,
        ), patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            return_value=SAMPLE_BANKI_DUPLICATE_PROGRAM_NAME_HTML,
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/',
                cbr_source_url='https://www.cbr.ru/banking_sector/credit/FullCoList/',
                google_sheet_sources=(),
            )

        self.assertEqual(result['reference_programs_processed'], 3)
        self.assertFalse(
            MortgageProgram.objects.filter(
                name='Ипотека для семей с детьми'
            ).exists()
        )
        canonical_program = MortgageProgram.objects.get(
            name='Семейная ипотека'
        )
        self.assertTrue(
            BankProgram.objects.filter(
                bank__name='Т-Банк',
                mortgage_program=canonical_program,
            ).exists()
        )
        alias = MortgageProgramAlias.objects.get(
            source_name='Семейная ипотека'
        )
        self.assertEqual(alias.mortgage_program, canonical_program)

    def test_sync_bank_mortgage_offers_can_update_existing_banks_only(self):
        """Checks program-only sync does not create missing banks."""
        Bank.objects.create(name='Т-Банк')
        raw_html = SAMPLE_BANKI_DUPLICATE_PROGRAM_NAME_HTML.replace(
            '<h2>Т-Банк</h2>',
            '<img alt="Т-Банк" src="/logos/tbank.svg"><h2>Т-Банк</h2>',
        )

        with patch(
            'bank.mortgage_offer_sync._download_cbr_bank_list_payload',
            side_effect=AssertionError('CBR source must not be called'),
        ), patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            return_value=raw_html,
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/',
                cbr_source_url='https://www.cbr.ru/banking_sector/credit/FullCoList/',
                google_sheet_sources=(),
                update_bank_registry=False,
            )

        self.assertEqual(result['created'], 0)
        self.assertEqual(result['banks_processed'], 0)
        self.assertEqual(result['processed'], 1)
        self.assertFalse(Bank.objects.filter(name='Банк ВТБ').exists())
        bank = Bank.objects.get(name='Т-Банк')
        self.assertEqual(
            bank.logo_url,
            'https://www.banki.ru/logos/tbank.svg',
        )
        self.assertTrue(
            BankProgram.objects.filter(
                bank=bank,
                mortgage_program__name='Семейная ипотека',
            ).exists()
        )

    def test_sync_bank_mortgage_offers_reports_banki_download_errors(self):
        """Checks Banki.ru network errors are reported as warnings."""
        with patch(
            'bank.mortgage_offer_sync._download_cbr_bank_list_payload',
            return_value=SAMPLE_CBR_BANK_LIST_HTML,
        ), patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            side_effect=ConnectionResetError('connection reset'),
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/',
                cbr_source_url='https://www.cbr.ru/banking_sector/credit/FullCoList/',
                google_sheet_sources=(),
            )

        self.assertEqual(result['processed'], 0)
        self.assertTrue(
            any(
                'Banki.ru не обработан' in warning
                for warning in result['warnings']
            )
        )

    def test_sync_bank_mortgage_offers_reports_cbr_download_errors(self):
        """Checks CBR errors do not stop mortgage offer updates."""
        Bank.objects.create(name='Т-Банк')

        with patch(
            'bank.mortgage_offer_sync._download_cbr_bank_list_payload',
            side_effect=ConnectionResetError('connection reset'),
        ), patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            return_value=SAMPLE_BANKI_DUPLICATE_PROGRAM_NAME_HTML,
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/',
                cbr_source_url='https://www.cbr.ru/banking_sector/credit/FullCoList/',
                google_sheet_sources=(),
            )

        self.assertEqual(result['created'], 0)
        self.assertEqual(result['processed'], 1)
        self.assertTrue(
            any(
                'Список банков ЦБ РФ не обновлен' in warning
                for warning in result['warnings']
            )
        )

    def test_sync_bank_mortgage_offers_renames_existing_raw_bank_name(self):
        """Checks sync updates a previously imported unnormalized bank name."""
        Bank.objects.create(name='Банк ВТБ (ПАО)')

        with patch(
            'bank.mortgage_offer_sync._download_cbr_bank_list_payload',
            return_value=SAMPLE_CBR_BANK_LIST_HTML,
        ), patch(
            'bank.mortgage_offer_sync._download_banki_mortgage_payload',
            return_value=SAMPLE_BANKI_MORTGAGE_HTML,
        ):
            result = sync_bank_mortgage_offers(
                source_url='https://www.banki.ru/products/hypothec/',
                cbr_source_url='https://www.cbr.ru/banking_sector/credit/FullCoList/',
                google_sheet_sources=(),
            )

        self.assertEqual(result['created'], 4)
        self.assertGreaterEqual(result['updated'], 1)
        self.assertTrue(Bank.objects.filter(name='Банк ВТБ').exists())
        self.assertFalse(Bank.objects.filter(name='Банк ВТБ (ПАО)').exists())

    def test_bank_catalog_shows_bank_logo_before_name(self):
        """Checks bank logo is rendered in the bank catalog name column."""
        Bank.objects.create(
            name='Alpha Bank',
            logo_url='https://img.example/alpha.svg',
        )

        response = self.client.get(f'{reverse("bank:catalog")}?model=bank')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'class="bank-logo"')
        self.assertContains(response, 'src="https://img.example/alpha.svg"')
        self.assertContains(response, '>Alpha Bank</span>')

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
        sync_mock.assert_called_once_with(update_bank_registry=True)
        messages = [
            str(message)
            for message in get_messages(response.wsgi_request)
        ]
        self.assertEqual(len(messages), 1)
        self.assertIn('создано=1', messages[0])
        self.assertIn('обновлено=2', messages[0])
        self.assertIn('обработано=3', messages[0])

    def test_bank_catalog_program_sync_button_runs_program_only_sync(self):
        """Checks bank catalog has program-only sync action."""
        response = self.client.get(f'{reverse("bank:catalog")}?model=bank')

        self.assertContains(
            response,
            'value="sync_existing_bank_mortgage_offers"',
        )
        self.assertContains(response, 'Обновить ипотечные программы')

        with patch(
            'bank.views.sync_bank_mortgage_offers',
            return_value={'created': 0, 'updated': 2, 'processed': 3},
        ) as sync_mock:
            response = self.client.post(
                reverse('bank:catalog'),
                {
                    'action': 'sync_existing_bank_mortgage_offers',
                    'model': 'bank',
                },
            )

        self.assertRedirects(response, f'{reverse("bank:catalog")}?model=bank')
        sync_mock.assert_called_once_with(update_bank_registry=False)
        messages = [
            str(message)
            for message in get_messages(response.wsgi_request)
        ]
        self.assertEqual(len(messages), 1)
        self.assertIn(
            'Обновление ипотечных программ банков завершено',
            messages[0],
        )

    def test_bank_catalog_program_sync_shows_warning_messages(self):
        """Checks program-only sync warnings are rendered instead of 500."""
        with patch(
            'bank.views.sync_bank_mortgage_offers',
            return_value={
                'created': 0,
                'updated': 0,
                'processed': 0,
                'reference_programs_processed': 0,
                'reference_program_aliases_created': 0,
                'warnings': ['Banki.ru не обработан'],
            },
        ):
            response = self.client.post(
                reverse('bank:catalog'),
                {
                    'action': 'sync_existing_bank_mortgage_offers',
                    'model': 'bank',
                },
            )

        self.assertRedirects(response, f'{reverse("bank:catalog")}?model=bank')
        messages = [
            str(message)
            for message in get_messages(response.wsgi_request)
        ]
        self.assertEqual(len(messages), 2)
        self.assertIn(
            'Обновление ипотечных программ банков завершено',
            messages[0],
        )
        self.assertIn('Banki.ru не обработан', messages[1])

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
