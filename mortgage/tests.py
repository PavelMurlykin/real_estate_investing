from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from mortgage.models import MortgageCalculation
from location.models import City, District, Region
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


class MortgageCalculatorViewTests(TestCase):
    def setUp(self):
        self.property = self._create_property(cost=Decimal('5000000.00'))
        self.url = reverse('mortgage:mortgage_calculator')

    def _create_property(self, cost: Decimal) -> Property:
        region = Region.objects.create(name='Регион 1', code='R1')
        city = City.objects.create(name='Город 1', region=region)
        district = District.objects.create(name='Район 1', city=city)
        developer = Developer.objects.create(name='Застройщик 1')
        estate_type = RealEstateType.objects.create(name='Квартира')
        estate_class = RealEstateClass.objects.create(name='Комфорт', weight=Decimal('1.00'))
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
            property_cost=cost,
        )

    def _base_payload(self) -> dict:
        return {
            'PROPERTY': str(self.property.id),
            'DISCOUNT_MARKUP_TYPE': 'discount',
            'DISCOUNT_MARKUP_VALUE': '0',
            'INITIAL_PAYMENT_PERCENT': '20',
            'INITIAL_PAYMENT_RUBLES': '0',
            'INITIAL_PAYMENT_DATE': '01.01.2026',
            'MORTGAGE_TERM': '20',
            'ANNUAL_RATE': '12',
            'HAS_GRACE_PERIOD': 'no',
            'GRACE_PERIOD_TERM': '',
            'GRACE_PERIOD_RATE': '',
        }

    def test_calculate_uses_property_cost_when_property_cost_is_empty(self):
        payload = self._base_payload()
        payload.update({
            'calculate': '1',
            'PROPERTY_COST': '',
        })

        response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(MortgageCalculation.objects.exists())
        calculation = MortgageCalculation.objects.latest('id')
        self.assertEqual(calculation.base_property_cost, Decimal('5000000.00'))
        self.assertEqual(calculation.final_property_cost, Decimal('5000000.00'))

    def test_calculate_keeps_overridden_cost_only_in_calculation(self):
        payload = self._base_payload()
        payload.update({
            'calculate': '1',
            'PROPERTY_COST': '6000000',
            'DISCOUNT_MARKUP_TYPE': 'discount',
            'DISCOUNT_MARKUP_VALUE': '10',
        })

        response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, 200)
        calculation = MortgageCalculation.objects.latest('id')
        self.assertEqual(calculation.base_property_cost, Decimal('6000000'))
        self.assertEqual(calculation.final_property_cost, Decimal('5400000'))

        self.property.refresh_from_db()
        self.assertEqual(self.property.property_cost, Decimal('5000000.00'))

    def test_export_returns_excel_file(self):
        payload = self._base_payload()
        payload.update({
            'export': '1',
            'PROPERTY_COST': '5100000',
            'DISCOUNT_MARKUP_TYPE': 'markup',
            'DISCOUNT_MARKUP_VALUE': '5',
        })

        response = self.client.post(self.url, payload)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response['Content-Type'],
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        self.assertIn('attachment; filename="mortgage_calculation.xlsx"', response['Content-Disposition'])

    def test_property_cost_api_returns_cost_from_database(self):
        url = reverse('mortgage:property_cost_api', kwargs={'pk': self.property.pk})

        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['property_cost'], '5000000.00')
