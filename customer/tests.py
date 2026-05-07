from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from bank.models import MortgageProgram
from property.models import ApartmentLayout
from .forms import CustomerForm
from .models import Customer


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
