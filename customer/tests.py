from django.test import TestCase

from .forms import CustomerForm


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
