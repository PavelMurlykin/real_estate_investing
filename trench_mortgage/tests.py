from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from trench_mortgage.forms import TrenchMortgageForm
from trench_mortgage.views import _calculate_months_remaining, _parse_trench_inputs


class TrenchMortgageFormTests(SimpleTestCase):
    def test_trench_count_choices_are_limited_to_one_to_five(self):
        trench_count_field = TrenchMortgageForm.base_fields["TRENCH_COUNT"]
        self.assertEqual(trench_count_field.choices, [(1, "1"), (2, "2"), (3, "3"), (4, "4"), (5, "5")])


class TrenchMortgageCalculationTests(SimpleTestCase):
    def test_parse_trench_inputs_sets_last_trench_percent_as_remainder(self):
        post_data = {
            "trench_date_1": "2026-01-10",
            "trench_percent_1": "40",
            "annual_rate_1": "11.5",
            "trench_date_2": "2026-06-10",
            "trench_percent_2": "",
            "annual_rate_2": "10",
        }

        entries, _, errors = _parse_trench_inputs(post_data, 2)

        self.assertEqual(errors, [])
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]["trench_percent"], Decimal("60.00"))

    def test_parse_trench_inputs_rejects_percent_sum_over_or_equal_hundred(self):
        post_data = {
            "trench_date_1": "2026-01-10",
            "trench_percent_1": "100",
            "annual_rate_1": "11.5",
            "trench_date_2": "2026-06-10",
            "trench_percent_2": "",
            "annual_rate_2": "10",
        }

        entries, _, errors = _parse_trench_inputs(post_data, 2)

        self.assertEqual(entries, [])
        self.assertTrue(errors)

    def test_months_remaining_depends_on_actual_dates(self):
        self.assertEqual(_calculate_months_remaining(date(2026, 1, 15), date(2027, 1, 15)), 12)
        self.assertEqual(_calculate_months_remaining(date(2026, 1, 16), date(2027, 1, 15)), 11)
