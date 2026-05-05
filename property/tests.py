from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.test import TestCase
from django.urls import reverse

from location.models import City, District, Metro, MetroLine, Region

from .forms import (
    RealEstateComplexBuildingForm,
    RealEstateComplexForm,
    RealEstateComplexMetroAvailabilityForm,
)
from .models import (
    ApartmentDecoration,
    ApartmentLayout,
    Developer,
    Property,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateComplexMetroAvailability,
    RealEstateType,
)


def test_metro_availability_select_opts_into_searchable_select():
    form = RealEstateComplexMetroAvailabilityForm()

    assert (
        form.fields['metro'].widget.attrs.get('data-searchable-select') == ''
    )


def test_searchable_select_static_filters_options_by_partial_match():
    script_path = Path(settings.BASE_DIR) / 'static/js/searchable_select.js'
    script = script_path.read_text(encoding='utf-8')

    assert 'select[data-searchable-select]' in script
    assert 'includes(query)' in script
    assert 'window.searchableSelect' in script


class RealEstateComplexFormLocationTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name='Region 1', code='R1')
        self.other_region = Region.objects.create(name='Region 2', code='R2')
        self.city = City.objects.create(name='City 1', region=self.region)
        self.other_city = City.objects.create(
            name='City 2', region=self.other_region
        )
        self.district = District.objects.create(
            name='District 1', city=self.city
        )
        self.developer = Developer.objects.create(name='Developer 1')
        self.estate_type = RealEstateType.objects.create(name='Apartment')
        self.estate_class = RealEstateClass.objects.create(
            name='Comfort', weight=Decimal('1.00')
        )
        self.metro_line = MetroLine.objects.create(
            line='Line 1',
            line_color='#FF0000',
            city=self.city,
        )
        self.metro = Metro.objects.create(
            station='Station 1',
            metro_line=self.metro_line,
        )

    def _form_data(self, **overrides):
        data = {
            'name': 'Complex 1',
            'description': '',
            'map_link': '',
            'presentation_link': '',
            'developer': self.developer.pk,
            'region': '',
            'city': '',
            'district': self.district.pk,
            'real_estate_class': self.estate_class.pk,
            'real_estate_type': self.estate_type.pk,
            'is_active': 'on',
        }
        data.update(overrides)
        return data

    def test_district_selection_fills_city_and_region(self):
        form = RealEstateComplexForm(data=self._form_data())

        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['city'], self.city)
        self.assertEqual(form.cleaned_data['region'], self.region)

    def test_mismatched_city_and_district_is_invalid(self):
        form = RealEstateComplexForm(
            data=self._form_data(city=self.other_city.pk)
        )

        self.assertFalse(form.is_valid())
        self.assertIn('district', form.errors)

    def test_create_view_renders_location_controls(self):
        response = self.client.get(reverse('property:complex_create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id_region')
        self.assertContains(response, 'id_city')
        self.assertContains(response, 'location-cities-data')
        self.assertContains(response, 'metro-0-metro')
        self.assertContains(response, 'data-searchable-select')
        self.assertContains(response, 'static/js/searchable_select.js')
        self.assertContains(response, 'location-metro-stations-data')
        self.assertContains(response, 'duplicate-complex-warning')
        self.assertContains(response, 'existing-complexes-data')
        self.assertContains(response, 'Доступность метро')
        self.assertNotContains(response, 'Метро рядом с ЖК')
        self.assertContains(response, 'data-add-metro-row')
        self.assertContains(response, 'data-remove-metro-row')
        self.assertContains(response, 'metro-availability-empty-form-template')
        self.assertContains(response, 'data-add-building-row')
        self.assertContains(response, 'data-remove-building-row')
        self.assertContains(response, 'building-empty-form-template')
        self.assertContains(response, 'buildings-0-commissioning_year')
        self.assertContains(response, 'buildings-0-commissioning_quarter')
        self.assertContains(response, 'buildings-0-key_handover_year')
        self.assertContains(response, 'buildings-0-key_handover_quarter')

    def test_create_view_passes_existing_complexes_for_duplicate_warning(self):
        complex_obj = RealEstateComplex.objects.create(
            name='Complex 1',
            developer=self.developer,
            district=self.district,
            real_estate_class=self.estate_class,
            real_estate_type=self.estate_type,
        )

        response = self.client.get(reverse('property:complex_create'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['existing_complexes'],
            [
                {
                    'id': complex_obj.pk,
                    'name': 'Complex 1',
                    'developer_id': self.developer.pk,
                }
            ],
        )

    def test_update_view_excludes_current_complex_from_duplicate_warning(self):
        complex_obj = RealEstateComplex.objects.create(
            name='Complex 1',
            developer=self.developer,
            district=self.district,
            real_estate_class=self.estate_class,
            real_estate_type=self.estate_type,
        )

        response = self.client.get(
            reverse('property:complex_update', kwargs={'pk': complex_obj.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['existing_complexes'], [])

    def _complex_create_post_data(self, **overrides):
        data = self._form_data(
            city=self.city.pk,
            region=self.region.pk,
            district=self.district.pk,
        )
        data.update(
            {
                'buildings-TOTAL_FORMS': '0',
                'buildings-INITIAL_FORMS': '0',
                'buildings-MIN_NUM_FORMS': '0',
                'buildings-MAX_NUM_FORMS': '1000',
                'metro-TOTAL_FORMS': '1',
                'metro-INITIAL_FORMS': '0',
                'metro-MIN_NUM_FORMS': '0',
                'metro-MAX_NUM_FORMS': '1000',
                'metro-0-metro': self.metro.pk,
                'metro-0-walking_time_minutes': '12',
                'metro-0-is_active': 'on',
            }
        )
        data.update(overrides)
        return data

    def test_create_view_saves_metro_availability(self):
        response = self.client.post(
            reverse('property:complex_create'),
            self._complex_create_post_data(),
        )

        self.assertRedirects(response, reverse('property:complex_list'))
        complex_obj = RealEstateComplex.objects.get(name='Complex 1')
        availability = RealEstateComplexMetroAvailability.objects.get(
            real_estate_complex=complex_obj
        )
        self.assertEqual(availability.metro, self.metro)
        self.assertEqual(availability.walking_time_minutes, 12)

    def test_create_view_saves_building_quarter_periods(self):
        response = self.client.post(
            reverse('property:complex_create'),
            self._complex_create_post_data(
                **{
                    'buildings-TOTAL_FORMS': '1',
                    'buildings-0-number': '1',
                    'buildings-0-address': 'Address 1',
                    'buildings-0-commissioning_date': '',
                    'buildings-0-commissioning_year': '2026',
                    'buildings-0-commissioning_quarter': '4',
                    'buildings-0-key_handover_date': '',
                    'buildings-0-key_handover_year': '2027',
                    'buildings-0-key_handover_quarter': '1',
                    'buildings-0-is_active': 'on',
                }
            ),
        )

        self.assertRedirects(response, reverse('property:complex_list'))
        building = RealEstateComplexBuilding.objects.get(number='1')
        self.assertEqual(building.commissioning_year, 2026)
        self.assertEqual(building.commissioning_quarter, 4)
        self.assertEqual(building.key_handover_year, 2027)
        self.assertEqual(building.key_handover_quarter, 1)
        self.assertEqual(building.get_commissioning_display(), 'IV кв. 2026')
        self.assertEqual(building.get_key_handover_display(), 'I кв. 2027')

    def test_building_form_rejects_date_and_quarter_period_together(self):
        form = RealEstateComplexBuildingForm(
            data={
                'number': '1',
                'address': 'Address 1',
                'commissioning_date': '2026-10-01',
                'commissioning_year': '2026',
                'commissioning_quarter': '4',
                'key_handover_date': '',
                'key_handover_year': '',
                'key_handover_quarter': '',
                'is_active': 'on',
            }
        )

        self.assertFalse(form.is_valid())
        self.assertIn('commissioning_date', form.errors)

    def test_create_view_rejects_metro_station_from_another_city(self):
        other_line = MetroLine.objects.create(
            line='Other line',
            line_color='#00FF00',
            city=self.other_city,
        )
        other_metro = Metro.objects.create(
            station='Other station',
            metro_line=other_line,
        )

        response = self.client.post(
            reverse('property:complex_create'),
            self._complex_create_post_data(**{'metro-0-metro': other_metro.pk}),
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(RealEstateComplex.objects.filter(name='Complex 1').exists())


class LocationCatalogMetroTests(TestCase):
    def setUp(self):
        self.region = Region.objects.create(name='Region 1', code='R1')
        self.city = City.objects.create(name='City 1', region=self.region)
        self.metro_line = MetroLine.objects.create(
            line='Line 1',
            line_color='#FF0000',
            city=self.city,
        )

    def test_location_catalog_routes_old_metro_line_tab_to_metro(self):
        response = self.client.get(
            reverse('location:location_catalog'), {'model': 'metro_line'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'name="model" value="metro"')
        self.assertNotContains(response, 'model=metro_line')
        self.assertNotContains(response, 'name="line_color"')

    def test_location_catalog_renders_metro_dictionary(self):
        response = self.client.get(
            reverse('location:location_catalog'), {'model': 'metro'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [column['name'] for column in response.context['columns']],
            ['station', 'metro_line', 'metro_line__city'],
        )
        self.assertContains(response, 'name="model" value="metro"')
        self.assertContains(response, 'name="station"')
        self.assertContains(response, 'name="metro_line"')
        self.assertContains(response, 'name="filter_city"')
        self.assertContains(response, 'name="filter_metro_line"')
        self.assertContains(response, 'data-metro-filter-form')
        self.assertContains(
            response, f'data-city-id="{self.city.pk}"', html=False
        )
        self.assertContains(response, 'catalog-line-select-swatch')
        self.assertNotContains(response, 'name="line_color"')
        self.assertNotContains(response, 'Применить')
        self.assertNotContains(response, 'Сбросить')

    def test_location_catalog_creates_updates_and_deletes_metro(self):
        other_line = MetroLine.objects.create(
            line='Line 2',
            line_color='#00FF00',
            city=self.city,
        )
        create_response = self.client.post(
            reverse('location:location_catalog'),
            {
                'action': 'save',
                'model': 'metro',
                'station': 'Station 1',
                'metro_line': self.metro_line.pk,
                'is_active': 'on',
            },
        )

        self.assertRedirects(
            create_response,
            f"{reverse('location:location_catalog')}?model=metro",
        )
        metro = Metro.objects.get(station='Station 1')

        update_response = self.client.post(
            reverse('location:location_catalog'),
            {
                'action': 'save',
                'model': 'metro',
                'object_id': metro.pk,
                'station': 'Station 2',
                'metro_line': other_line.pk,
            },
        )

        self.assertRedirects(
            update_response,
            f"{reverse('location:location_catalog')}?model=metro",
        )
        metro.refresh_from_db()
        self.assertEqual(metro.station, 'Station 2')
        self.assertEqual(metro.metro_line, other_line)
        self.assertFalse(metro.is_active)

        delete_response = self.client.post(
            reverse('location:location_catalog'),
            {
                'action': 'delete',
                'model': 'metro',
                'object_id': metro.pk,
            },
        )

        self.assertRedirects(
            delete_response,
            f"{reverse('location:location_catalog')}?model=metro",
        )
        self.assertFalse(Metro.objects.filter(pk=metro.pk).exists())

    def test_location_catalog_renders_metro_line_color_in_station_table(self):
        Metro.objects.create(station='Station 1', metro_line=self.metro_line)

        response = self.client.get(
            reverse('location:location_catalog'), {'model': 'metro'}
        )

        self.assertContains(response, 'catalog-line-color-strip')
        self.assertContains(response, '#FF0000')
        self.assertContains(response, 'Line 1')
        self.assertContains(response, 'City 1')

    def test_location_catalog_filters_metro_by_city_and_line(self):
        other_city = City.objects.create(name='City 2', region=self.region)
        other_line = MetroLine.objects.create(
            line='Line 2',
            line_color='#00FF00',
            city=other_city,
        )
        Metro.objects.create(station='Station 1', metro_line=self.metro_line)
        Metro.objects.create(station='Station 2', metro_line=other_line)

        city_response = self.client.get(
            reverse('location:location_catalog'),
            {'model': 'metro', 'filter_city': self.city.pk},
        )

        self.assertContains(city_response, 'Station 1')
        self.assertNotContains(city_response, 'Station 2')

        line_response = self.client.get(
            reverse('location:location_catalog'),
            {'model': 'metro', 'filter_metro_line': other_line.pk},
        )

        self.assertNotContains(line_response, 'Station 1')
        self.assertContains(line_response, 'Station 2')

    def test_location_catalog_sorts_metro_by_column_headers(self):
        Metro.objects.create(station='Bravo', metro_line=self.metro_line)
        Metro.objects.create(station='Alpha', metro_line=self.metro_line)

        asc_response = self.client.get(
            reverse('location:location_catalog'),
            {'model': 'metro', 'sort_by': 'station', 'sort_dir': 'asc'},
        )
        desc_response = self.client.get(
            reverse('location:location_catalog'),
            {'model': 'metro', 'sort_by': 'station', 'sort_dir': 'desc'},
        )

        self.assertEqual(
            asc_response.context['rows'][0]['cells'][0]['value'],
            'Alpha',
        )
        self.assertEqual(
            desc_response.context['rows'][0]['cells'][0]['value'],
            'Bravo',
        )
        self.assertContains(asc_response, 'sort_by=station')


class DeveloperListViewTests(TestCase):
    def test_developer_list_filters_and_sorts_with_catalog_static_hooks(self):
        Developer.objects.create(name='Beta Developer', description='Townhouses')
        Developer.objects.create(name='Alpha Developer', description='Apartments')

        response = self.client.get(
            reverse('property:developer_list'),
            {
                'filter_description': 'Apart',
                'sort_by': 'name',
                'sort_dir': 'desc',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'data-catalog-filter-form')
        self.assertContains(response, 'data-catalog-filter-control')
        self.assertContains(response, 'catalog-results')
        self.assertContains(response, 'static/js/catalog.js')
        self.assertContains(response, 'Alpha Developer')
        self.assertNotContains(response, 'Beta Developer')
        self.assertEqual(response.context['sort_by'], 'name')
        self.assertEqual(response.context['sort_dir'], 'desc')
        self.assertEqual(
            [column['key'] for column in response.context['columns']],
            ['name', 'description'],
        )

    def test_developer_list_does_not_render_active_column(self):
        Developer.objects.create(name='Developer 1', is_active=False)

        response = self.client.get(reverse('property:developer_list'))

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, '<th>Активен</th>', html=True)
        self.assertNotContains(response, 'Да')
        self.assertNotContains(response, 'Нет')


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
            response,
            'Нельзя удалить ЖК: есть связанные объекты недвижимости.',
            status_code=400,
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
