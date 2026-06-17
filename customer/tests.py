from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from bank.models import MortgageProgram, MortgageProgramRegionalCreditLimit
from location.models import City, District, Region
from mortgage.models import MortgageCalculation
from mortgage.utils import format_currency
from property.models import (
    ApartmentDecoration,
    ApartmentLayout,
    Developer,
    Property,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateType,
)
from trench_mortgage.models import Trench, TrenchMortgageCalculation
from users.roles import APPLICATION_ADMINISTRATOR_GROUP_NAME

from .forms import CustomerForm
from .models import Customer, CustomerCalculation, CustomerTrenchCalculation


class CustomerFormTests(TestCase):
    def test_new_customers_are_active_by_default(self):
        form = CustomerForm(data={'first_name': 'Test'})

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertIs(form.instance.is_active, True)

    def test_has_owned_property_accepts_optional_boolean_values(self):
        cases = (
            ('unknown', None),
            ('', None),
            ('true', True),
            ('false', False),
        )

        for value, expected in cases:
            with self.subTest(value=value):
                form = CustomerForm(
                    data={
                        'first_name': 'Test',
                        'has_owned_property': value,
                    }
                )

                self.assertTrue(form.is_valid(), form.errors.as_json())
                self.assertIs(form.cleaned_data['has_owned_property'], expected)
                self.assertIs(form.instance.has_owned_property, expected)

    def test_has_owned_property_uses_three_radio_choices(self):
        form = CustomerForm()

        self.assertEqual(
            list(form.fields['has_owned_property'].choices),
            [('true', 'Да'), ('false', 'Нет'), ('unknown', 'Не указано')],
        )
        self.assertEqual(
            form.fields['has_owned_property'].widget.__class__.__name__,
            'RadioSelect',
        )

    def test_programs_include_preferential_and_regular_programs(self):
        regular_program = MortgageProgram.objects.create(
            name='Стандартная',
            condition='Базовые условия',
            is_preferential=False,
        )
        preferential_program = MortgageProgram.objects.create(
            name='Семейная',
            condition='Льготные условия',
            is_preferential=True,
        )

        form = CustomerForm()

        self.assertEqual(
            form.fields['preferential_programs'].label,
            'Доступные программы',
        )
        self.assertIn(
            regular_program,
            form.fields['preferential_programs'].queryset,
        )
        self.assertIn(
            preferential_program,
            form.fields['preferential_programs'].queryset,
        )
        self.assertEqual(
            form.fields['preferential_programs'].widget.__class__.__name__,
            'CheckboxSelectMultiple',
        )

    def test_multiselect_customer_fields_use_checkboxes(self):
        form = CustomerForm()

        self.assertEqual(
            form.fields['desired_layouts'].widget.__class__.__name__,
            'CheckboxSelectMultiple',
        )
        self.assertEqual(
            form.fields['cardinal_directions'].widget.__class__.__name__,
            'CheckboxSelectMultiple',
        )

    def test_cardinal_directions_are_selected_from_code_choices(self):
        form = CustomerForm(
            data={
                'first_name': 'Test',
                'cardinal_directions': [
                    Customer.CARDINAL_DIRECTION_NORTH,
                    Customer.CARDINAL_DIRECTION_EAST,
                ],
            }
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        self.assertEqual(
            form.cleaned_data['cardinal_directions'],
            'Север, Восток',
        )
        self.assertEqual(form.instance.cardinal_directions, 'Север, Восток')

    def test_cardinal_directions_initial_values_are_split_for_checkboxes(self):
        customer = Customer(cardinal_directions='Север, Восток')

        form = CustomerForm(instance=customer)

        self.assertEqual(
            form.initial['cardinal_directions'],
            ['Север', 'Восток'],
        )

    def test_create_page_renders_radio_and_checkbox_controls(self):
        user_model = get_user_model()
        user = user_model.objects.create_user(
            email='agent@example.com',
            password='password',
            phone_number='+79990000000',
            first_name='Agent',
            last_name='User',
        )
        MortgageProgram.objects.create(
            name='Стандартная',
            condition='Базовые условия',
            is_preferential=False,
        )
        MortgageProgram.objects.create(
            name='Семейная',
            condition='Льготные условия',
            is_preferential=True,
        )
        ApartmentLayout.objects.create(name='Евро-2')
        self.client.force_login(user)

        response = self.client.get(reverse('customer:create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Доступные программы')
        self.assertContains(response, 'name="preferential_programs"', count=2)
        self.assertContains(response, 'name="desired_layouts"', count=1)
        self.assertContains(response, 'name="cardinal_directions"', count=8)
        self.assertContains(response, 'name="has_owned_property"', count=3)


class CustomerDetailViewTests(TestCase):
    """Проверяет карточку клиента."""

    def setUp(self):
        """Подготавливает пользователя для тестов карточки клиента."""
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email='detail-agent@example.com',
            password='password',
            phone_number='+79990000001',
            first_name='Agent',
            last_name='User',
        )
        self.client.force_login(self.user)

    def test_detail_page_uses_customer_name_in_heading(self):
        """Проверяет вывод имени клиента в заголовке карточки."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Карточка клиента Иван Петров')
        self.assertNotContains(response, f'Карточка клиента #{customer.pk}')

    def test_detail_page_calculates_preferential_max_property_cost(self):
        """Проверяет расчет максимальной стоимости по льготной ставке."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            initial_payment_amount=Decimal('1000000'),
            max_monthly_payment=Decimal('100000'),
        )
        preferential_program = MortgageProgram.objects.create(
            name='Семейная',
            condition='Льготные условия',
            is_preferential=True,
        )
        customer.preferential_programs.add(preferential_program)
        expected_cost = customer.calculate_max_property_cost(
            annual_rate=Customer.DEFAULT_PREFERENTIAL_ANNUAL_RATE,
            max_term_years=Customer.MAX_MORTGAGE_TERM_YEARS,
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(
            response.context['calculated']['has_preferential_program']
        )
        self.assertEqual(
            response.context['calculated'][
                'preferential_max_property_cost'
            ],
            format_currency(expected_cost),
        )
        self.assertContains(
            response,
            'Максимальная стоимость объекта по льготной ставке 6%',
        )

    def test_detail_page_limits_family_mortgage_credit_by_region(self):
        """Проверяет региональный лимит кредита семейной ипотеки."""
        region = Region.objects.create(name='Москва', code='77')
        city = City.objects.create(name='Москва', region=region)
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            desired_city=city,
            initial_payment_amount=Decimal('1000000'),
            max_monthly_payment=Decimal('100000'),
        )
        preferential_program = MortgageProgram.objects.create(
            name='Семейная',
            condition='Льготные условия',
            is_preferential=True,
            credit_limit=Decimal('6000000'),
        )
        MortgageProgramRegionalCreditLimit.objects.create(
            mortgage_program=preferential_program,
            region=region,
            credit_limit=Decimal('12000000'),
        )
        customer.preferential_programs.add(preferential_program)

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['calculated']['preferential_credit_limit'],
            format_currency(Decimal('12000000')),
        )
        self.assertEqual(
            response.context['calculated'][
                'preferential_max_property_cost'
            ],
            format_currency(Decimal('13000000')),
        )
        self.assertContains(response, 'Лимит кредита по льготной программе')
        self.assertContains(response, '12 000 000,00 руб.')

    def test_detail_page_hides_preferential_calculation_without_program(self):
        """Проверяет скрытие льготного расчета без льготной программы."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            initial_payment_amount=Decimal('1000000'),
            max_monthly_payment=Decimal('100000'),
        )
        regular_program = MortgageProgram.objects.create(
            name='Стандартная',
            condition='Базовые условия',
            is_preferential=False,
        )
        customer.preferential_programs.add(regular_program)

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            response.context['calculated']['has_preferential_program']
        )
        self.assertNotContains(
            response,
            'Максимальная стоимость объекта по льготной ставке',
        )


class CustomerDeleteViewTests(TestCase):
    """Проверяет удаление клиента из списка клиентов."""

    def setUp(self):
        """Подготавливает пользователя для тестов удаления клиента."""
        user_model = get_user_model()
        self.user = user_model.objects.create_user(
            email='delete-agent@example.com',
            password='password',
            phone_number='+79990000002',
            first_name='Agent',
            last_name='User',
        )
        self.client.force_login(self.user)

    def _create_user(self, email, phone_number):
        """Create a regular test user."""
        return get_user_model().objects.create_user(
            email=email,
            password='password',
            phone_number=phone_number,
            first_name='Agent',
            last_name='User',
        )

    def _create_application_administrator(self):
        """Create an application administrator user."""
        user = self._create_user(
            'customer-admin@example.com',
            '+79990000003',
        )
        group, _created = Group.objects.get_or_create(
            name=APPLICATION_ADMINISTRATOR_GROUP_NAME
        )
        user.groups.add(group)
        return user

    def _create_property(
        self,
        city_name='Город 1',
        complex_name='ЖК Тест',
    ) -> Property:
        """Создает объект недвижимости для ипотечного расчета."""
        suffix = Region.objects.count() + 1
        region = Region.objects.create(
            name=f'Регион {suffix}', code=f'R{suffix}'
        )
        city = City.objects.create(name=city_name, region=region)
        district = District.objects.create(
            name=f'Район {suffix}', city=city
        )
        developer = Developer.objects.create(name=f'Застройщик {suffix}')
        estate_type = RealEstateType.objects.create(name=f'Квартира {suffix}')
        estate_class = RealEstateClass.objects.create(
            name=f'Комфорт {suffix}', weight=Decimal('1.00')
        )
        complex_obj = RealEstateComplex.objects.create(
            name=complex_name,
            developer=developer,
            district=district,
            real_estate_class=estate_class,
            real_estate_type=estate_type,
        )
        building = RealEstateComplexBuilding.objects.create(
            number='1',
            real_estate_complex=complex_obj,
        )
        layout = ApartmentLayout.objects.create(name=f'1К {suffix}')
        decoration = ApartmentDecoration.objects.create(
            name=f'Без отделки {suffix}'
        )
        return Property.objects.create(
            apartment_number='101',
            building=building,
            decoration=decoration,
            layout=layout,
            area=Decimal('42.00'),
            floor=10,
            property_cost=Decimal('5000000.00'),
        )

    def _create_calculation(
        self,
        city_name='Город 1',
        complex_name='ЖК Тест',
    ) -> MortgageCalculation:
        """Создает сохраненный ипотечный расчет."""
        return MortgageCalculation.objects.create(
            user=self.user,
            property=self._create_property(
                city_name=city_name,
                complex_name=complex_name,
            ),
            base_property_cost=Decimal('5000000.00'),
            initial_payment_percent=Decimal('20.00'),
            initial_payment_date=date(2026, 1, 1),
            mortgage_term=240,
            annual_rate=Decimal('12.00'),
            has_grace_period=False,
            final_property_cost=Decimal('5000000.00'),
            main_payments_count=240,
            mortgage_end_date=date(2046, 1, 1),
            main_monthly_payment=Decimal('55054.31'),
            total_loan_amount=Decimal('4000000.00'),
            total_overpayment=Decimal('9213034.40'),
        )

    def _create_trench_calculation(
        self,
        city_name='Город 1',
        complex_name='ЖК Транш',
    ) -> TrenchMortgageCalculation:
        """Создает сохраненный траншевый ипотечный расчет."""
        calculation = TrenchMortgageCalculation.objects.create(
            user=self.user,
            property=self._create_property(
                city_name=city_name,
                complex_name=complex_name,
            ),
            base_property_cost=Decimal('5000000.00'),
            discount_markup_type='discount',
            discount_markup_value=Decimal('0.00'),
            final_property_cost=Decimal('5000000.00'),
            initial_payment_percent=Decimal('20.00'),
            initial_payment_date=date(2026, 1, 1),
            mortgage_term=240,
            annual_rate=Decimal('12.00'),
            trench_count=2,
            total_loan_amount=Decimal('4000000.00'),
            total_overpayment=Decimal('8500000.00'),
        )
        Trench.objects.create(
            calculation=calculation,
            trench_number=1,
            trench_date=date(2026, 1, 1),
            trench_percent=Decimal('50.00'),
            trench_amount=Decimal('2000000.00'),
            annual_rate=Decimal('12.00'),
            monthly_payment=Decimal('22021.72'),
            payments_count=12,
            remaining_debt=Decimal('2000000.00'),
        )
        Trench.objects.create(
            calculation=calculation,
            trench_number=2,
            trench_date=date(2027, 1, 1),
            trench_percent=Decimal('50.00'),
            trench_amount=Decimal('2000000.00'),
            annual_rate=Decimal('12.00'),
            monthly_payment=Decimal('44043.44'),
            payments_count=228,
            remaining_debt=Decimal('0.00'),
        )
        return calculation

    def test_list_page_shows_delete_button(self):
        """Проверяет вывод кнопки удаления в списке клиентов."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )

        response = self.client.get(reverse('customer:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Удалить')
        self.assertContains(
            response,
            reverse('customer:delete', kwargs={'pk': customer.pk}),
        )

    def test_regular_user_cannot_access_other_user_customer(self):
        """Checks customer detail and list are scoped to owner."""
        other_user = self._create_user(
            'other-customer-user@example.com',
            '+79990000004',
        )
        customer = Customer.objects.create(
            user=other_user,
            first_name='Иван',
            last_name='Петров',
        )

        list_response = self.client.get(reverse('customer:list'))
        detail_response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )
        delete_response = self.client.post(
            reverse('customer:delete', kwargs={'pk': customer.pk})
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertNotContains(list_response, customer.full_name)
        self.assertEqual(detail_response.status_code, 404)
        self.assertEqual(delete_response.status_code, 404)
        self.assertTrue(Customer.objects.filter(pk=customer.pk).exists())

    def test_application_administrator_can_access_all_customers(self):
        """Checks administrators have global customer access."""
        other_user = self._create_user(
            'admin-visible-customer-user@example.com',
            '+79990000005',
        )
        customer = Customer.objects.create(
            user=other_user,
            first_name='Иван',
            last_name='Петров',
        )
        administrator = self._create_application_administrator()
        self.client.force_login(administrator)

        list_response = self.client.get(reverse('customer:list'))
        detail_response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, customer.full_name)
        self.assertEqual(detail_response.status_code, 200)

    def test_delete_customer_removes_link_and_keeps_calculation(self):
        """Проверяет, что удаление клиента не удаляет сам расчет."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        calculation = self._create_calculation()
        customer_calculation = CustomerCalculation.objects.create(
            customer=customer,
            calculation=calculation,
        )

        response = self.client.post(
            reverse('customer:delete', kwargs={'pk': customer.pk})
        )

        self.assertRedirects(response, reverse('customer:list'))
        self.assertFalse(Customer.objects.filter(pk=customer.pk).exists())
        self.assertFalse(
            CustomerCalculation.objects.filter(
                pk=customer_calculation.pk
            ).exists()
        )
        self.assertTrue(
            MortgageCalculation.objects.filter(pk=calculation.pk).exists()
        )

    def test_detail_saved_calculations_use_dynamic_filters(self):
        """Проверяет подключение динамической фильтрации в карточке."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        calculation = self._create_calculation()
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=calculation,
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-catalog-filter-form')
        self.assertContains(response, 'data-catalog-filter-control', count=12)
        self.assertContains(response, 'customer-calculation-results')
        self.assertContains(response, 'static/js/catalog.js')
        self.assertContains(response, 'dropdown-toggle')
        self.assertContains(response, 'Добавить существующий расчет')
        self.assertContains(
            response,
            reverse('mortgage:calculation_list') + f'?customer={customer.pk}',
        )
        self.assertContains(
            response,
            (
                reverse('mortgage:trench_calculation_list')
                + f'?customer={customer.pk}'
            ),
        )
        self.assertContains(response, 'Рыночная ипотека')
        self.assertContains(response, 'Траншевая ипотека')

    def test_detail_saved_calculations_hide_date_and_show_detail_action(self):
        """Проверяет состав столбцов и действий в сохраненных расчетах."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        calculation = self._create_calculation()
        customer_calculation = CustomerCalculation.objects.create(
            customer=customer,
            calculation=calculation,
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Дата расчета')
        self.assertContains(response, 'Подробнее')
        self.assertContains(
            response,
            reverse(
                'mortgage:calculation_detail',
                kwargs={'pk': calculation.pk},
            ),
        )
        self.assertContains(response, 'Удалить')
        self.assertContains(
            response,
            reverse(
                'customer:calculation_delete',
                kwargs={'pk': customer_calculation.pk},
            ),
        )

    def test_detail_saved_calculations_include_trench_calculations(self):
        """Проверяет вывод рыночных и траншевых расчетов в одной таблице."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        market_calculation = self._create_calculation(
            complex_name='ЖК Рыночный'
        )
        trench_calculation = self._create_trench_calculation(
            complex_name='ЖК Траншевый'
        )
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=market_calculation,
        )
        customer_trench_calculation = (
            CustomerTrenchCalculation.objects.create(
                customer=customer,
                calculation=trench_calculation,
            )
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )
        calculations = list(response.context['customer_calculations'])

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '<th>Программа</th>', html=True)
        content = response.content.decode()
        table_header = content[
            content.index('<thead>'):content.index('</thead>')
        ]
        self.assertGreater(
            table_header.index('<th>Программа</th>'),
            table_header.index('Ставка'),
        )
        self.assertLess(
            table_header.index('<th>Программа</th>'),
            table_header.index('<th>Действия</th>'),
        )
        self.assertContains(response, 'Рыночная ипотека')
        self.assertContains(response, 'Траншевая ипотека')
        self.assertContains(response, 'ЖК Рыночный, кв. 101')
        self.assertContains(response, 'ЖК Траншевый, кв. 101')
        self.assertContains(response, '55 054,31 руб.')
        self.assertContains(response, '44 043,44 руб.')
        self.assertContains(
            response,
            reverse(
                'mortgage:trench_calculation_detail',
                kwargs={'pk': trench_calculation.pk},
            ),
        )
        self.assertContains(
            response,
            reverse(
                'customer:trench_calculation_delete',
                kwargs={'pk': customer_trench_calculation.pk},
            ),
        )
        self.assertEqual(
            {calculation.program_type for calculation in calculations},
            {'market', 'trench'},
        )

    def test_delete_customer_calculation_removes_link_and_keeps_calculation(
        self,
    ):
        """Проверяет удаление связи клиента и расчета из карточки."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        calculation = self._create_calculation()
        customer_calculation = CustomerCalculation.objects.create(
            customer=customer,
            calculation=calculation,
        )

        response = self.client.post(
            reverse(
                'customer:calculation_delete',
                kwargs={'pk': customer_calculation.pk},
            )
        )

        self.assertRedirects(
            response, reverse('customer:detail', kwargs={'pk': customer.pk})
        )
        self.assertTrue(Customer.objects.filter(pk=customer.pk).exists())
        self.assertFalse(
            CustomerCalculation.objects.filter(
                pk=customer_calculation.pk
            ).exists()
        )
        self.assertTrue(
            MortgageCalculation.objects.filter(pk=calculation.pk).exists()
        )

    def test_delete_customer_trench_calculation_removes_link_and_keeps_calculation(
        self,
    ):
        """Проверяет удаление связи клиента и траншевого расчета."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        calculation = self._create_trench_calculation()
        customer_calculation = CustomerTrenchCalculation.objects.create(
            customer=customer,
            calculation=calculation,
        )

        response = self.client.post(
            reverse(
                'customer:trench_calculation_delete',
                kwargs={'pk': customer_calculation.pk},
            )
        )

        self.assertRedirects(
            response, reverse('customer:detail', kwargs={'pk': customer.pk})
        )
        self.assertTrue(Customer.objects.filter(pk=customer.pk).exists())
        self.assertFalse(
            CustomerTrenchCalculation.objects.filter(
                pk=customer_calculation.pk
            ).exists()
        )
        self.assertTrue(
            TrenchMortgageCalculation.objects.filter(pk=calculation.pk)
            .exists()
        )

    def test_detail_saved_calculations_show_city_column_and_filter(self):
        """Проверяет столбец города и фильтр по городу."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        moscow_calculation = self._create_calculation(
            city_name='Москва',
            complex_name='ЖК Москва',
        )
        kazan_calculation = self._create_calculation(
            city_name='Казань',
            complex_name='ЖК Казань',
        )
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=moscow_calculation,
        )
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=kazan_calculation,
        )
        moscow_city = (
            moscow_calculation.property.building.real_estate_complex
            .district.city
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk}),
            {'city': moscow_city.pk},
        )
        calculations = list(response.context['customer_calculations'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['calculation_table_headers'][0]['field'],
            'city',
        )
        self.assertEqual(
            response.context['calculation_table_headers'][1]['field'],
            'object',
        )
        self.assertContains(response, 'Город')
        self.assertContains(response, 'name="city"')
        self.assertEqual(len(calculations), 1)
        self.assertEqual(calculations[0].calculation, moscow_calculation)

    def test_detail_saved_calculations_sort_by_city(self):
        """Проверяет сортировку сохраненных расчетов по городу."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        z_calculation = self._create_calculation(
            city_name='Ярославль',
            complex_name='ЖК Ярославль',
        )
        a_calculation = self._create_calculation(
            city_name='Астрахань',
            complex_name='ЖК Астрахань',
        )
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=z_calculation,
        )
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=a_calculation,
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk}),
            {'sort': 'city', 'order': 'asc'},
        )
        cities = [
            calculation.calculation.property.building.real_estate_complex
            .district.city.name
            for calculation in response.context['customer_calculations']
        ]

        self.assertEqual(response.status_code, 200)
        self.assertEqual(cities, ['Астрахань', 'Ярославль'])

    def test_detail_saved_calculations_filter_trench_by_city(self):
        """Проверяет фильтрацию траншевых расчетов по городу."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        moscow_calculation = self._create_trench_calculation(
            city_name='Москва',
            complex_name='ЖК Москва',
        )
        kazan_calculation = self._create_calculation(
            city_name='Казань',
            complex_name='ЖК Казань',
        )
        CustomerTrenchCalculation.objects.create(
            customer=customer,
            calculation=moscow_calculation,
        )
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=kazan_calculation,
        )
        moscow_city = (
            moscow_calculation.property.building.real_estate_complex
            .district.city
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk}),
            {'city': moscow_city.pk},
        )
        calculations = list(response.context['customer_calculations'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(calculations), 1)
        self.assertEqual(calculations[0].calculation, moscow_calculation)
        self.assertEqual(calculations[0].program_type, 'trench')

    def test_detail_saved_calculations_sort_by_monthly_payment_across_programs(
        self,
    ):
        """Проверяет сортировку по платежу для обоих типов ипотеки."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        market_calculation = self._create_calculation()
        trench_calculation = self._create_trench_calculation()
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=market_calculation,
        )
        CustomerTrenchCalculation.objects.create(
            customer=customer,
            calculation=trench_calculation,
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk}),
            {'sort': 'monthly_payment', 'order': 'asc'},
        )
        calculations = list(response.context['customer_calculations'])

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [calculation.program_type for calculation in calculations],
            ['trench', 'market'],
        )
        self.assertEqual(
            [
                calculation.main_monthly_payment
                for calculation in calculations
            ],
            [Decimal('44043.44'), Decimal('55054.31')],
        )

    def test_detail_saved_calculation_spoiler_shows_full_calculation(self):
        """Проверяет содержимое спойлера сохраненного расчета."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        calculation = self._create_calculation()
        calculation.base_property_cost = Decimal('5000000.00')
        calculation.final_property_cost = Decimal('4500000.00')
        calculation.discount_markup_type = 'discount'
        calculation.discount_markup_value = Decimal('10.00')
        calculation.initial_payment_percent = Decimal('20.00')
        calculation.mortgage_term = 240
        calculation.annual_rate = Decimal('12.00')
        calculation.has_grace_period = False
        calculation.main_payments_count = 240
        calculation.main_monthly_payment = Decimal('55054.31')
        calculation.save()
        calculation.property.layout_image = 'property/layouts/layout.gif'
        calculation.property.save()
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=calculation,
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-bs-toggle="collapse"')
        self.assertContains(response, 'calculation-toggle')
        self.assertContains(response, 'aria-label="Показать детали расчета"')
        self.assertContains(response, 'css/calculation_table.css')
        self.assertNotContains(response, '>Раскрыть</button>')
        self.assertContains(
            response,
            (
                'customer-market-calculation-details-'
                f'{calculation.customer_links.first().pk}'
            ),
        )
        self.assertContains(response, 'table-bordered')
        self.assertContains(response, 'Стоимость объекта')
        self.assertContains(response, '5 000 000 руб.')
        self.assertContains(
            response,
            '<th scope="row" class="text-nowrap">Скидка</th>',
            html=True,
        )
        self.assertContains(response, 'calculation-detail-table')
        self.assertContains(response, 'style="width: 36ch;"')
        self.assertContains(response, 'style="width: 23ch;"')
        self.assertContains(response, 'calculation-layout-cell')
        self.assertContains(
            response,
            'src="/media/property/layouts/layout.gif"',
        )
        self.assertContains(response, 'data-image-modal="true"')
        self.assertContains(response, 'static/js/image_modal.js')
        self.assertNotContains(
            response,
            'href="/media/property/layouts/layout.gif" target="_blank"',
        )
        self.assertContains(response, 'alt="Планировка"')
        self.assertContains(
            response,
            '<th scope="row" class="text-nowrap">Планировка</th>',
            html=True,
        )
        self.assertContains(
            response,
            '<th scope="row" class="text-nowrap">Площадь</th>',
            html=True,
        )
        self.assertContains(response, '1К 1')
        self.assertContains(response, '<td class="text-nowrap">42</td>', html=True)
        self.assertContains(response, '500 000 руб. (10 %)')
        self.assertNotContains(response, 'Скидка/Удорожание')
        self.assertNotContains(response, 'Скидка - 500 000 руб. (10 %)')
        self.assertContains(response, 'Итоговая стоимость объекта')
        self.assertContains(response, '4 500 000 руб.')
        self.assertContains(response, '900 000 руб. (20 %)')
        self.assertNotContains(response, 'Дата первоначального взноса')
        self.assertNotContains(response, '01.01.2026')
        self.assertContains(response, '20 лет (240 мес.)')
        self.assertContains(response, '12 %')
        self.assertNotContains(response, 'Число платежей')
        self.assertContains(response, 'Сумма ежемесячного платежа')
        self.assertContains(response, '55 054,31 руб.')
        self.assertNotContains(response, 'Срок льготного периода')

    def test_detail_saved_trench_calculation_spoiler_shows_trench_fields(self):
        """Проверяет содержимое спойлера траншевого расчета клиента."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        calculation = self._create_trench_calculation()
        customer_calculation = CustomerTrenchCalculation.objects.create(
            customer=customer,
            calculation=calculation,
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(
            response,
            (
                'customer-trench-calculation-details-'
                f'{customer_calculation.pk}'
            ),
        )
        self.assertContains(response, 'Количество траншей')
        self.assertContains(response, 'Число платежей по траншу 1')
        self.assertContains(response, 'Сумма платежа по траншу 1')
        self.assertContains(response, '22 021,72 руб.')
        self.assertContains(response, 'Число платежей по траншу 2')
        self.assertContains(response, 'Сумма платежа по траншу 2')
        self.assertContains(response, '44 043,44 руб.')

    def test_detail_saved_calculation_spoiler_shows_grace_period_fields(self):
        """Проверяет поля льготного периода в спойлере расчета."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        calculation = self._create_calculation()
        calculation.has_grace_period = True
        calculation.grace_period_term = 24
        calculation.grace_period_rate = Decimal('6.00')
        calculation.grace_payments_count = 24
        calculation.grace_monthly_payment = Decimal('30000.00')
        calculation.save()
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=calculation,
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'style="width: 36ch;"')
        self.assertContains(response, 'Срок льготного периода')
        self.assertContains(response, '2 года (24 мес.)')
        self.assertContains(response, 'Годовая ставка в льготный период')
        self.assertContains(response, '6 %')
        self.assertNotContains(response, 'Число платежей за льготный период')
        self.assertNotContains(
            response,
            'Сумма ежемесячного платежа во время льготного периода',
        )
        self.assertContains(response, 'Сумма льготного платежа')
        self.assertContains(response, '30 000 руб.')
        content = response.content.decode()
        self.assertLess(
            content.index('Сумма ежемесячного платежа'),
            content.index('Срок льготного периода'),
        )

    def test_detail_saved_calculation_sort_links_use_ajax_without_anchor(self):
        """Проверяет AJAX-сортировку без браузерного якоря."""
        customer = Customer.objects.create(
            user=self.user,
            first_name='Иван',
            last_name='Петров',
        )
        calculation = self._create_calculation()
        CustomerCalculation.objects.create(
            customer=customer,
            calculation=calculation,
        )

        response = self.client.get(
            reverse('customer:detail', kwargs={'pk': customer.pk})
        )
        header_urls = [
            header['url']
            for header in response.context['calculation_table_headers']
        ]

        self.assertTrue(header_urls)
        self.assertTrue(
            all(
                '#customer-calculation-results' not in url
                for url in header_urls
            )
        )
        self.assertContains(
            response,
            '?sort=city&amp;order=desc',
        )
        self.assertContains(response, 'data-catalog-sort-link')
        self.assertContains(response, 'data-catalog-results')
        self.assertContains(response, 'catalog.js?v=20260516-sort')

    def test_catalog_static_sorts_results_without_page_reload(self):
        """Проверяет AJAX-сортировку таблиц без полного перехода."""
        script_path = Path(settings.BASE_DIR) / 'static/js/catalog.js'
        script = script_path.read_text(encoding='utf-8')

        self.assertIn('data-catalog-sort-link', script)
        self.assertIn('getCatalogResultsTarget', script)
        self.assertIn("closest('[data-catalog-results]')", script)
        self.assertIn('event.preventDefault()', script)
        self.assertIn('fetchResultsUrl(', script)
        self.assertIn("historyUrl.hash = ''", script)
        self.assertIn('}, true);', script)

