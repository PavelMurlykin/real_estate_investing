from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bank.models import MortgageProgram
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

from .forms import CustomerForm
from .models import Customer, CustomerCalculation


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

    def _create_property(self) -> Property:
        """Создает объект недвижимости для ипотечного расчета."""
        region = Region.objects.create(name='Регион 1', code='R1')
        city = City.objects.create(name='Город 1', region=region)
        district = District.objects.create(name='Район 1', city=city)
        developer = Developer.objects.create(name='Застройщик 1')
        estate_type = RealEstateType.objects.create(name='Квартира')
        estate_class = RealEstateClass.objects.create(
            name='Комфорт', weight=Decimal('1.00')
        )
        complex_obj = RealEstateComplex.objects.create(
            name='ЖК Тест',
            developer=developer,
            district=district,
            real_estate_class=estate_class,
            real_estate_type=estate_type,
        )
        building = RealEstateComplexBuilding.objects.create(
            number='1',
            real_estate_complex=complex_obj,
        )
        layout = ApartmentLayout.objects.create(name='1К')
        decoration = ApartmentDecoration.objects.create(name='Без отделки')
        return Property.objects.create(
            apartment_number='101',
            building=building,
            decoration=decoration,
            layout=layout,
            area=Decimal('42.00'),
            floor=10,
            property_cost=Decimal('5000000.00'),
        )

    def _create_calculation(self) -> MortgageCalculation:
        """Создает сохраненный ипотечный расчет."""
        return MortgageCalculation.objects.create(
            property=self._create_property(),
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
