from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from location.models import City, District, Region

from .models import (
    ApartmentDecoration,
    ApartmentLayout,
    Developer,
    Property,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateType,
)


class RealEstateComplexDeleteViewTests(TestCase):
    """Описание класса RealEstateComplexDeleteViewTests.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    def _create_complex(self) -> RealEstateComplex:
        """Описание метода _create_complex.

        Выполняет прикладную операцию текущего модуля.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        region = Region.objects.create(name='Region 1', code='R1')
        city = City.objects.create(name='City 1', region=region)
        district = District.objects.create(name='District 1', city=city)
        developer = Developer.objects.create(name='Developer 1')
        estate_type = RealEstateType.objects.create(name='Apartment')
        estate_class = RealEstateClass.objects.create(
            name='Comfort', weight=Decimal('1.00')
        )
        return RealEstateComplex.objects.create(
            name='Complex 1',
            developer=developer,
            district=district,
            real_estate_class=estate_class,
            real_estate_type=estate_type,
        )

    def test_delete_complex_cascades_linked_buildings(self):
        """Описание метода test_delete_complex_cascades_linked_buildings.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        complex_obj = self._create_complex()
        building = RealEstateComplexBuilding.objects.create(
            number='1',
            real_estate_complex=complex_obj,
        )

        response = self.client.post(
            reverse('property:complex_delete', kwargs={'pk': complex_obj.pk})
        )

        self.assertRedirects(response, reverse('property:complex_list'))
        self.assertFalse(
            RealEstateComplex.objects.filter(pk=complex_obj.pk).exists()
        )
        self.assertFalse(
            RealEstateComplexBuilding.objects.filter(pk=building.pk).exists()
        )

    def test_delete_complex_with_property_shows_protected_error(self):
        """Описание метода
        test_delete_complex_with_property_shows_protected_error.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        complex_obj = self._create_complex()
        building = RealEstateComplexBuilding.objects.create(
            number='1',
            real_estate_complex=complex_obj,
        )
        layout = ApartmentLayout.objects.create(name='Layout 1')
        decoration = ApartmentDecoration.objects.create(name='Decoration 1')
        Property.objects.create(
            apartment_number='101',
            building=building,
            decoration=decoration,
            layout=layout,
            area=Decimal('42.00'),
            floor=10,
            property_cost=Decimal('1000000.00'),
        )

        response = self.client.post(
            reverse('property:complex_delete', kwargs={'pk': complex_obj.pk})
        )

        self.assertEqual(response.status_code, 400)
        self.assertContains(
            response, 'Нельзя удалить ЖК: есть связанные объекты недвижимости.'
        )
        self.assertTrue(
            RealEstateComplex.objects.filter(pk=complex_obj.pk).exists()
        )

    def test_property_string_representation_contains_russian_labels(self):
        """Описание метода
        test_property_string_representation_contains_russian_labels.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
            поведения.
        """
        complex_obj = self._create_complex()
        building = RealEstateComplexBuilding.objects.create(
            number='1',
            real_estate_complex=complex_obj,
        )
        layout = ApartmentLayout.objects.create(name='Layout 1')
        decoration = ApartmentDecoration.objects.create(name='Decoration 1')
        property_obj = Property.objects.create(
            apartment_number='101',
            building=building,
            decoration=decoration,
            layout=layout,
            area=Decimal('42.00'),
            floor=10,
            property_cost=Decimal('1000000.00'),
        )

        self.assertEqual(
            str(property_obj),
            'ЖК "Complex 1", корпус 1, кв. 101',
        )
