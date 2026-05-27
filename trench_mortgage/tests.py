from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase

from trench_mortgage.forms import TrenchMortgageForm
from trench_mortgage.views import (
    _calculate_months_remaining,
    _calculate_trench_mortgage,
    _parse_trench_inputs,
)


class TrenchMortgageFormTests(SimpleTestCase):
    """Описание класса TrenchMortgageFormTests.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    def test_trench_count_choices_are_limited_to_one_to_five(self):
        """Описание метода
        test_trench_count_choices_are_limited_to_one_to_five.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        trench_count_field = TrenchMortgageForm.base_fields['TRENCH_COUNT']
        self.assertEqual(
            trench_count_field.choices,
            [(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')],
        )


class TrenchMortgageCalculationTests(SimpleTestCase):
    """Описание класса TrenchMortgageCalculationTests.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    def _build_mortgage_data(self):
        """Описание метода _build_mortgage_data.

        Выполняет прикладную операцию текущего модуля.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        return {
            'property_obj': None,
            'property_cost': 1_200_000,
            'base_property_cost': 1_200_000,
            'discount_markup_type': 'discount',
            'discount_markup_value': 0,
            'final_property_cost': 1_200_000,
            'initial_payment_percent': 16.67,
            'initial_payment_rubles': 200_000,
            'initial_payment_date': date(2026, 1, 10),
            'mortgage_term': 1,
            'annual_rate': 0,
            'trench_count': 2,
            'total_loan_amount': 1_000_000,
        }

    def test_parse_trench_inputs_sets_last_trench_percent_as_remainder(self):
        """Описание метода
        test_parse_trench_inputs_sets_last_trench_percent_as_remainder.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        post_data = {
            'trench_date_1': '2026-01-10',
            'trench_percent_1': '40',
            'trench_amount_1': '',
            'annual_rate_1': '11.5',
            'trench_date_2': '2026-06-10',
            'trench_percent_2': '',
            'trench_amount_2': '',
            'annual_rate_2': '10',
        }

        entries, _, errors = _parse_trench_inputs(post_data, 2, 1_000_000, 10)

        self.assertEqual(errors, [])
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[1]['trench_percent'], Decimal('60.00'))
        self.assertEqual(entries[1]['trench_amount'], Decimal('600000.00'))

    def test_parse_trench_inputs_rejects_percent_sum_over_or_equal_hundred(
        self,
    ):
        """Описание метода
        test_parse_trench_inputs_rejects_percent_sum_over_or_equal_hundred.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        post_data = {
            'trench_date_1': '2026-01-10',
            'trench_percent_1': '100',
            'trench_amount_1': '',
            'annual_rate_1': '11.5',
            'trench_date_2': '2026-06-10',
            'trench_percent_2': '',
            'trench_amount_2': '',
            'annual_rate_2': '10',
        }

        entries, _, errors = _parse_trench_inputs(post_data, 2, 1_000_000, 10)

        self.assertEqual(entries, [])
        self.assertTrue(errors)

    def test_parse_trench_inputs_converts_amount_to_percent(self):
        """Описание метода test_parse_trench_inputs_converts_amount_to_percent.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        post_data = {
            'trench_date_1': '2026-01-10',
            'trench_percent_1': '',
            'trench_amount_1': '250000',
            'annual_rate_1': '11.5',
            'trench_date_2': '2026-06-10',
            'trench_percent_2': '',
            'trench_amount_2': '',
            'annual_rate_2': '10',
        }

        entries, _, errors = _parse_trench_inputs(post_data, 2, 1_000_000, 10)

        self.assertEqual(errors, [])
        self.assertEqual(entries[0]['trench_percent'], Decimal('25.00'))
        self.assertEqual(entries[0]['trench_amount'], Decimal('250000.00'))
        self.assertEqual(entries[1]['trench_percent'], Decimal('75.00'))

    def test_parse_trench_inputs_uses_locked_amount_for_remainder(self):
        """Keep the exact ruble amount when tranche rubles are locked."""
        post_data = {
            'trench_date_1': '2026-01-10',
            'trench_percent_1': '1.25',
            'trench_amount_1': '100000',
            'trench_amount_source_1': 'rubles',
            'annual_rate_1': '11.5',
            'trench_date_2': '2026-06-10',
            'trench_percent_2': '',
            'trench_amount_2': '',
            'trench_amount_source_2': 'rubles',
            'annual_rate_2': '10',
        }

        entries, _, errors = _parse_trench_inputs(post_data, 2, 7_990_000, 10)

        self.assertEqual(errors, [])
        self.assertEqual(entries[0]['trench_amount'], Decimal('100000.00'))
        self.assertEqual(entries[1]['trench_amount'], Decimal('7890000.00'))

    def test_parse_trench_inputs_uses_locked_percent_for_amount(self):
        """Keep the exact percent when tranche percent is locked."""
        post_data = {
            'trench_date_1': '2026-01-10',
            'trench_percent_1': '1.25',
            'trench_amount_1': '100000',
            'trench_amount_source_1': 'percent',
            'annual_rate_1': '11.5',
            'trench_date_2': '2026-06-10',
            'trench_percent_2': '',
            'trench_amount_2': '',
            'trench_amount_source_2': 'rubles',
            'annual_rate_2': '10',
        }

        entries, _, errors = _parse_trench_inputs(post_data, 2, 7_990_000, 10)

        self.assertEqual(errors, [])
        self.assertEqual(entries[0]['trench_amount'], Decimal('99875.00'))
        self.assertEqual(entries[1]['trench_amount'], Decimal('7890125.00'))

    def test_months_remaining_depends_on_actual_dates(self):
        """Описание метода test_months_remaining_depends_on_actual_dates.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        self.assertEqual(
            _calculate_months_remaining(date(2026, 1, 15), date(2027, 1, 15)),
            12,
        )
        self.assertEqual(
            _calculate_months_remaining(date(2026, 1, 16), date(2027, 1, 15)),
            11,
        )

    def test_payments_count_is_calculated_until_next_trench(self):
        """Описание метода test_payments_count_is_calculated_until_next_trench.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        mortgage_data = self._build_mortgage_data()
        trench_entries = [
            {
                'number': 1,
                'trench_date': date(2026, 1, 10),
                'trench_percent': Decimal('50.00'),
                'trench_amount': Decimal('500000.00'),
                'annual_rate': Decimal('0.00'),
            },
            {
                'number': 2,
                'trench_date': date(2026, 7, 10),
                'trench_percent': Decimal('50.00'),
                'trench_amount': Decimal('500000.00'),
                'annual_rate': Decimal('0.00'),
            },
        ]

        calculation, errors = _calculate_trench_mortgage(
            mortgage_data, trench_entries
        )

        self.assertEqual(errors, [])
        self.assertEqual(calculation['trenches'][0]['payments_count'], 6)
        self.assertEqual(calculation['trenches'][1]['payments_count'], 6)

    def test_details_match_schedule_for_offset_next_trench_date(self):
        """Match stage counts and cumulative payments with the schedule."""
        mortgage_data = self._build_mortgage_data()
        mortgage_data.update(
            {
                'initial_payment_date': date(2026, 5, 21),
                'mortgage_term': 30,
                'annual_rate': 13.9,
                'total_loan_amount': 7_990_000,
            }
        )
        trench_entries = [
            {
                'number': 1,
                'trench_date': date(2026, 5, 21),
                'trench_percent': Decimal('12.52'),
                'trench_amount': Decimal('1000348.00'),
                'annual_rate': Decimal('13.90'),
            },
            {
                'number': 2,
                'trench_date': date(2027, 3, 31),
                'trench_percent': Decimal('87.48'),
                'trench_amount': Decimal('6989652.00'),
                'annual_rate': Decimal('13.90'),
            },
        ]

        calculation, errors = _calculate_trench_mortgage(
            mortgage_data, trench_entries
        )

        self.assertEqual(errors, [])
        self.assertEqual(calculation['trenches'][0]['payments_count'], 11)
        self.assertAlmostEqual(
            calculation['trenches'][1]['monthly_payment'],
            calculation['payment_schedule'][11]['payment_amount'],
            places=2,
        )

    def test_payment_schedule_is_generated_for_each_month(self):
        """Описание метода test_payment_schedule_is_generated_for_each_month.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        mortgage_data = self._build_mortgage_data()
        trench_entries = [
            {
                'number': 1,
                'trench_date': date(2026, 1, 10),
                'trench_percent': Decimal('50.00'),
                'trench_amount': Decimal('500000.00'),
                'annual_rate': Decimal('0.00'),
            },
            {
                'number': 2,
                'trench_date': date(2026, 7, 10),
                'trench_percent': Decimal('50.00'),
                'trench_amount': Decimal('500000.00'),
                'annual_rate': Decimal('0.00'),
            },
        ]

        calculation, errors = _calculate_trench_mortgage(
            mortgage_data, trench_entries
        )
        payment_schedule = calculation['payment_schedule']

        self.assertEqual(errors, [])
        self.assertEqual(len(payment_schedule), 12)
        self.assertEqual(
            payment_schedule[0]['payment_date'], date(2026, 1, 10)
        )
        self.assertEqual(
            payment_schedule[6]['payment_date'], date(2026, 7, 10)
        )
        self.assertAlmostEqual(
            payment_schedule[0]['payment_amount'], 41_666.67, places=2
        )
        self.assertAlmostEqual(
            payment_schedule[6]['payment_amount'], 125_000.0, places=2
        )
        self.assertAlmostEqual(
            payment_schedule[-1]['remaining_debt'], 0.0, places=2
        )
