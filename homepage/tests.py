from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from location.models import City, District, Region
from property.models import (
    Developer,
    RealEstateClass,
    RealEstateComplex,
    RealEstateType,
)


class HomepageIndexViewTests(TestCase):
    """Описание класса HomepageIndexViewTests.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    def setUp(self):
        """Описание метода setUp.

        Выполняет прикладную операцию текущего модуля.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        self.region_spb = Region.objects.create(name='Северо-Запад', code='NW')
        self.region_msk = Region.objects.create(name='Центральный', code='CTR')

        self.city_spb = City.objects.create(
            name='Санкт-Петербург', region=self.region_spb
        )
        self.city_msk = City.objects.create(
            name='Москва', region=self.region_msk
        )

        self.district_spb = District.objects.create(
            name='Приморский', city=self.city_spb
        )
        self.district_msk = District.objects.create(
            name='Тверской', city=self.city_msk
        )

        self.developer = Developer.objects.create(name='Developer')
        self.real_estate_type = RealEstateType.objects.create(name='Квартира')
        self.real_estate_class = RealEstateClass.objects.create(
            name='Комфорт', weight=Decimal('1.00')
        )

        self.complex_spb = RealEstateComplex.objects.create(
            name='ЖК СПб',
            map_link='https://yandex.ru/maps/org/spb_complex',
            developer=self.developer,
            district=self.district_spb,
            real_estate_class=self.real_estate_class,
            real_estate_type=self.real_estate_type,
        )
        self.complex_msk = RealEstateComplex.objects.create(
            name='ЖК Москва',
            map_link='https://yandex.ru/maps/org/msk_complex',
            developer=self.developer,
            district=self.district_msk,
            real_estate_class=self.real_estate_class,
            real_estate_type=self.real_estate_type,
        )

    def test_index_uses_saint_petersburg_by_default(self):
        """Описание метода test_index_uses_saint_petersburg_by_default.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        response = self.client.get(reverse('homepage:index'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_city'], self.city_spb)
        self.assertEqual(response.context['headline_city'], 'Санкт-Петербурге')
        self.assertQuerySetEqual(
            response.context['complexes'],
            [self.complex_spb],
            transform=lambda item: item,
            ordered=False,
        )

    def test_index_filters_complexes_by_selected_city(self):
        """Описание метода test_index_filters_complexes_by_selected_city.

        Проверяет ожидаемое поведение сценария в рамках автоматического
        теста.

        Возвращает:
            None: Тест завершится ошибкой при нарушении ожидаемого
        поведения.
        """
        response = self.client.get(
            reverse('homepage:index'), {'city': self.city_msk.id}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['selected_city'], self.city_msk)
        self.assertEqual(response.context['headline_city'], 'Москве')
        self.assertQuerySetEqual(
            response.context['complexes'],
            [self.complex_msk],
            transform=lambda item: item,
            ordered=False,
        )
        self.assertContains(response, 'Доступные для расчета ЖК в Москве')
