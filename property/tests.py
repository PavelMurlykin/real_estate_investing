from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from location.models import City, District, Metro, MetroLine, Region
from users.roles import MODERATOR_GROUP_NAME

from .forms import (
    PropertyForm,
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
    TransportAccessibilityType,
    WindowView,
)


SIMPLE_GIF = (
    b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!'
    b'\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
    b'\x00\x02\x02L\x01\x00;'
)


def create_moderator(email, phone_number):
    """Create a test moderator user."""
    user = get_user_model().objects.create_user(
        email=email,
        password='password',
        phone_number=phone_number,
        first_name='Test',
        last_name='User',
    )
    group, _created = Group.objects.get_or_create(
        name=MODERATOR_GROUP_NAME
    )
    user.groups.add(group)
    return user


def test_metro_availability_select_uses_bootstrap_class_for_auto_search():
    form = RealEstateComplexMetroAvailabilityForm()

    assert form.fields['metro'].widget.attrs.get('class') == 'form-control'


def test_metro_availability_form_fields_use_requested_order():
    form = RealEstateComplexMetroAvailabilityForm()

    assert list(form.fields)[:3] == [
        'metro',
        'transport_accessibility_type',
        'walking_time_minutes',
    ]
    assert (
        form.fields['transport_accessibility_type'].widget.attrs.get('class')
        == 'form-control'
    )


def test_searchable_select_static_filters_options_by_partial_match():
    script_path = Path(settings.BASE_DIR) / 'static/js/searchable_select.js'
    script = script_path.read_text(encoding='utf-8')

    assert 'select.form-control' in script
    assert 'select.form-select' in script
    assert 'searchableSelectExclude' in script
    assert 'searchableSelectColor' in script
    assert 'searchable-select-option-color' in script
    assert 'MutationObserver' in script
    assert 'includes(query)' in script
    assert 'searchQuery' in script
    assert 'resetSearch' in script
    assert "state.input.value = ''" in script
    assert 'skipNextSelectSync' in script
    assert 'searchable-select-toggle' in script
    assert 'window.searchableSelect' in script


def test_searchable_select_static_looks_like_dropdown():
    script_path = Path(settings.BASE_DIR) / 'static/js/searchable_select.js'
    style_path = Path(settings.BASE_DIR) / 'static/css/searchable_select.css'
    script = script_path.read_text(encoding='utf-8')
    styles = style_path.read_text(encoding='utf-8')

    assert "const classes = ['form-select', 'searchable-select-input']" in script
    assert 'form-select-sm' in script
    assert 'form-select-lg' in script
    assert '.searchable-select-toggle' in styles
    assert 'border-top: 0.3em solid var(--bs-body-color)' in styles
    assert 'padding-right: 2.25rem' in styles


def test_base_template_cache_busts_searchable_select_assets():
    template_path = Path(settings.BASE_DIR) / 'templates/base.html'
    template = template_path.read_text(encoding='utf-8')

    assert "css/searchable_select.css' %}?v=" in template
    assert "js/searchable_select.js' %}?v=" in template


def test_dependent_selects_static_supports_cascade_configuration():
    script_path = Path(settings.BASE_DIR) / 'static/js/dependent_selects.js'
    script = script_path.read_text(encoding='utf-8')

    assert 'data-cascade-selects' in script
    assert 'cascadeParent' in script
    assert 'cascadeAutofill' in script
    assert 'cascadeRequiredParents' in script
    assert 'clearDependentValues' in script


class RealEstateComplexFormLocationTests(TestCase):
    def setUp(self):
        self.client.force_login(
            create_moderator(
                'complex-moderator@example.com',
                '+79992000000',
            )
        )
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
        self.walking_accessibility_type = (
            TransportAccessibilityType.objects.get_or_create(name='Пешком')[0]
        )
        self.transport_accessibility_type = (
            TransportAccessibilityType.objects.get_or_create(
                name='На транспорте'
            )[0]
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
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'id_region')
        self.assertContains(response, 'id_city')
        self.assertContains(response, 'id_investment_potential')
        self.assertContains(response, 'id_photo')
        self.assertContains(response, 'Инвестиционный потенциал')
        self.assertContains(response, 'Фото ЖК')
        self.assertContains(response, 'location-cities-data')
        self.assertContains(response, 'metro-0-metro')
        self.assertContains(response, 'metro-0-transport_accessibility_type')
        self.assertContains(response, 'static/js/searchable_select.js')
        self.assertContains(response, 'location-metro-stations-data')
        self.assertContains(response, 'duplicate-complex-warning')
        self.assertContains(response, 'existing-complexes-data')
        self.assertContains(response, 'Доступность метро')
        self.assertContains(response, 'Способ')
        self.assertContains(response, 'Время, мин')
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
        self.assertEqual(
            response.context['location_metro_stations'][0][
                'metro_line__line_color'
            ],
            '#FF0000',
        )

    def test_complex_form_metro_options_show_station_name_without_line(self):
        form = RealEstateComplexMetroAvailabilityForm()

        metro_choices = {
            str(value): label for value, label in form.fields['metro'].choices
        }

        self.assertEqual(metro_choices[str(self.metro.pk)], 'Station 1')
        self.assertNotIn('Line 1', metro_choices[str(self.metro.pk)])

    def test_dictionary_catalog_renders_transport_accessibility_type(self):
        response = self.client.get(
            reverse('property:dictionary_catalog'),
            {'model': 'transport_accessibility_type'},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Типы транспортной доступности')
        self.assertContains(response, 'Пешком')

    def test_building_address_input_disables_browser_autocomplete(self):
        form = RealEstateComplexBuildingForm()

        self.assertEqual(
            form.fields['address'].widget.attrs.get('autocomplete'),
            'off',
        )

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

    def test_update_view_does_not_render_empty_extra_inline_rows(self):
        complex_obj = RealEstateComplex.objects.create(
            name='Complex 1',
            developer=self.developer,
            district=self.district,
            real_estate_class=self.estate_class,
            real_estate_type=self.estate_type,
        )
        RealEstateComplexBuilding.objects.create(
            number='1',
            address='Address 1',
            real_estate_complex=complex_obj,
        )
        RealEstateComplexMetroAvailability.objects.create(
            real_estate_complex=complex_obj,
            metro=self.metro,
            transport_accessibility_type=self.walking_accessibility_type,
            walking_time_minutes=12,
        )

        response = self.client.get(
            reverse('property:complex_update', kwargs={'pk': complex_obj.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.context['building_formset'].total_form_count(),
            1,
        )
        self.assertEqual(
            response.context['metro_availability_formset'].total_form_count(),
            1,
        )
        self.assertNotContains(response, 'buildings-1-number')
        self.assertNotContains(response, 'metro-1-metro')

    def test_update_view_renders_building_dates_in_html_date_format(self):
        complex_obj = RealEstateComplex.objects.create(
            name='Complex 1',
            developer=self.developer,
            district=self.district,
            real_estate_class=self.estate_class,
            real_estate_type=self.estate_type,
        )
        RealEstateComplexBuilding.objects.create(
            number='1',
            address='Address 1',
            commissioning_date=date(2026, 10, 1),
            key_handover_date=date(2027, 1, 15),
            real_estate_complex=complex_obj,
        )

        response = self.client.get(
            reverse('property:complex_update', kwargs={'pk': complex_obj.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'value="2026-10-01"')
        self.assertContains(response, 'value="2027-01-15"')

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
                'metro-0-transport_accessibility_type': (
                    self.transport_accessibility_type.pk
                ),
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
        self.assertEqual(
            availability.transport_accessibility_type,
            self.transport_accessibility_type,
        )
        self.assertEqual(availability.walking_time_minutes, 12)

    def test_create_view_saves_investment_potential_and_photo(self):
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('property:complex_create'),
                    self._complex_create_post_data(
                        investment_potential='Высокий спрос на аренду.',
                        photo=SimpleUploadedFile(
                            'complex.gif',
                            SIMPLE_GIF,
                            content_type='image/gif',
                        ),
                    ),
                )

                self.assertRedirects(
                    response, reverse('property:complex_list')
                )
                complex_obj = RealEstateComplex.objects.get(name='Complex 1')
                self.assertEqual(
                    complex_obj.investment_potential,
                    'Высокий спрос на аренду.',
                )
                self.assertTrue(
                    complex_obj.photo.name.startswith(
                        'property/complexes/complex'
                    )
                )
                self.assertTrue(
                    (Path(media_root) / complex_obj.photo.name).exists()
                )

    @override_settings(PROPERTY_IMAGE_MAX_UPLOAD_SIZE=1)
    def test_complex_form_rejects_oversized_photo(self):
        """The complex form should reject images above the configured limit."""
        form = RealEstateComplexForm(
            data=self._form_data(),
            files={
                'photo': SimpleUploadedFile(
                    'complex.gif',
                    SIMPLE_GIF,
                    content_type='image/gif',
                ),
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn('photo', form.errors)

    def test_update_view_shows_current_complex_photo(self):
        complex_obj = RealEstateComplex.objects.create(
            name='Complex 1',
            developer=self.developer,
            district=self.district,
            real_estate_class=self.estate_class,
            real_estate_type=self.estate_type,
            photo='property/complexes/complex.gif',
        )

        response = self.client.get(
            reverse('property:complex_update', kwargs={'pk': complex_obj.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'complex.gif')
        self.assertContains(response, '/media/property/complexes/complex.gif')
        self.assertContains(response, 'id_clear_photo')
        self.assertContains(response, 'data-clear-file-button')
        self.assertContains(response, 'data-image-modal="true"')

    def test_update_view_clears_current_complex_photo(self):
        with TemporaryDirectory() as media_root:
            media_root_path = Path(media_root)
            photo_path = media_root_path / 'property/complexes/complex.gif'
            photo_path.parent.mkdir(parents=True)
            photo_path.write_bytes(SIMPLE_GIF)

            with override_settings(MEDIA_ROOT=media_root):
                complex_obj = RealEstateComplex.objects.create(
                    name='Complex 1',
                    developer=self.developer,
                    district=self.district,
                    real_estate_class=self.estate_class,
                    real_estate_type=self.estate_type,
                    photo='property/complexes/complex.gif',
                )
                data = self._form_data(
                    city=self.city.pk,
                    region=self.region.pk,
                    district=self.district.pk,
                    clear_photo='on',
                )
                data.update(
                    {
                        'buildings-TOTAL_FORMS': '0',
                        'buildings-INITIAL_FORMS': '0',
                        'buildings-MIN_NUM_FORMS': '0',
                        'buildings-MAX_NUM_FORMS': '1000',
                        'metro-TOTAL_FORMS': '0',
                        'metro-INITIAL_FORMS': '0',
                        'metro-MIN_NUM_FORMS': '0',
                        'metro-MAX_NUM_FORMS': '1000',
                    }
                )

                response = self.client.post(
                    reverse(
                        'property:complex_update',
                        kwargs={'pk': complex_obj.pk},
                    ),
                    data,
                )

                self.assertRedirects(
                    response, reverse('property:complex_list')
                )
                complex_obj.refresh_from_db()
                self.assertFalse(complex_obj.photo)
                self.assertFalse(photo_path.exists())

    def test_complex_list_has_detail_action(self):
        complex_obj = RealEstateComplex.objects.create(
            name='Complex 1',
            developer=self.developer,
            district=self.district,
            real_estate_class=self.estate_class,
            real_estate_type=self.estate_type,
        )

        response = self.client.get(reverse('property:complex_list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Подробнее')
        self.assertContains(
            response,
            reverse('property:complex_detail', kwargs={'pk': complex_obj.pk}),
        )

    def test_complex_detail_shows_card_fields_photo_and_related_data(self):
        complex_obj = RealEstateComplex.objects.create(
            name='Complex 1',
            description='Описание комплекса.',
            investment_potential='Высокий спрос на аренду.',
            photo='property/complexes/complex.gif',
            developer=self.developer,
            district=self.district,
            real_estate_class=self.estate_class,
            real_estate_type=self.estate_type,
        )
        RealEstateComplexBuilding.objects.create(
            number='1',
            address='Address 1',
            real_estate_complex=complex_obj,
        )
        RealEstateComplexMetroAvailability.objects.create(
            real_estate_complex=complex_obj,
            metro=self.metro,
            transport_accessibility_type=self.walking_accessibility_type,
            walking_time_minutes=12,
        )

        response = self.client.get(
            reverse('property:complex_detail', kwargs={'pk': complex_obj.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Complex 1')
        self.assertContains(response, 'Фото ЖК')
        self.assertContains(response, 'Инвестиционный потенциал')
        self.assertContains(response, 'Высокий спрос на аренду.')
        self.assertContains(response, 'src="/media/property/complexes/complex.gif"')
        self.assertContains(response, 'data-image-modal="true"')
        self.assertContains(response, 'Station 1')
        self.assertContains(response, 'Пешком')
        self.assertContains(response, 'Address 1')

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

    def test_create_view_saves_building_exact_dates(self):
        response = self.client.post(
            reverse('property:complex_create'),
            self._complex_create_post_data(
                **{
                    'buildings-TOTAL_FORMS': '1',
                    'buildings-0-number': '1',
                    'buildings-0-address': 'Address 1',
                    'buildings-0-commissioning_date': '2026-10-01',
                    'buildings-0-commissioning_year': '',
                    'buildings-0-commissioning_quarter': '',
                    'buildings-0-key_handover_date': '2027-01-15',
                    'buildings-0-key_handover_year': '',
                    'buildings-0-key_handover_quarter': '',
                    'buildings-0-is_active': 'on',
                }
            ),
        )

        self.assertRedirects(response, reverse('property:complex_list'))
        building = RealEstateComplexBuilding.objects.get(number='1')
        self.assertEqual(building.commissioning_date, date(2026, 10, 1))
        self.assertEqual(building.key_handover_date, date(2027, 1, 15))

    def test_update_view_saves_building_date_and_quarter_periods(self):
        complex_obj = RealEstateComplex.objects.create(
            name='Complex 1',
            developer=self.developer,
            district=self.district,
            real_estate_class=self.estate_class,
            real_estate_type=self.estate_type,
        )
        building = RealEstateComplexBuilding.objects.create(
            number='1',
            address='Address 1',
            real_estate_complex=complex_obj,
        )
        data = self._form_data(
            city=self.city.pk,
            region=self.region.pk,
            district=self.district.pk,
        )
        data.update(
            {
                'buildings-TOTAL_FORMS': '1',
                'buildings-INITIAL_FORMS': '1',
                'buildings-MIN_NUM_FORMS': '0',
                'buildings-MAX_NUM_FORMS': '1000',
                'buildings-0-id': building.pk,
                'buildings-0-real_estate_complex': complex_obj.pk,
                'buildings-0-number': '1A',
                'buildings-0-address': 'Address 1A',
                'buildings-0-commissioning_date': '2026-10-01',
                'buildings-0-commissioning_year': '',
                'buildings-0-commissioning_quarter': '',
                'buildings-0-key_handover_date': '',
                'buildings-0-key_handover_year': '2027',
                'buildings-0-key_handover_quarter': '1',
                'buildings-0-is_active': 'on',
                'metro-TOTAL_FORMS': '0',
                'metro-INITIAL_FORMS': '0',
                'metro-MIN_NUM_FORMS': '0',
                'metro-MAX_NUM_FORMS': '1000',
            }
        )

        response = self.client.post(
            reverse('property:complex_update', kwargs={'pk': complex_obj.pk}),
            data,
        )

        self.assertRedirects(response, reverse('property:complex_list'))
        building.refresh_from_db()
        self.assertEqual(building.number, '1A')
        self.assertEqual(building.address, 'Address 1A')
        self.assertEqual(building.commissioning_date, date(2026, 10, 1))
        self.assertEqual(building.key_handover_year, 2027)
        self.assertEqual(building.key_handover_quarter, 1)

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
        self.client.force_login(
            create_moderator(
                'location-moderator@example.com',
                '+79992000001',
            )
        )
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

    def test_anonymous_location_catalog_is_read_only(self):
        """Checks anonymous users can read locations but cannot mutate them."""
        self.client.logout()

        response = self.client.get(
            reverse('location:location_catalog'), {'model': 'metro'}
        )
        post_response = self.client.post(
            reverse('location:location_catalog'),
            {
                'action': 'save',
                'model': 'metro',
                'station': 'Station 1',
                'metro_line': self.metro_line.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'name="station"')
        self.assertEqual(post_response.status_code, 403)
        self.assertFalse(Metro.objects.filter(station='Station 1').exists())

    def test_location_catalog_paginates_metro_rows(self):
        for index in range(21):
            Metro.objects.create(
                station=f'Station {index:02d}',
                metro_line=self.metro_line,
            )

        response = self.client.get(
            reverse('location:location_catalog'), {'model': 'metro'}
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.context['rows']), 20)
        self.assertTrue(response.context['is_paginated'])
        self.assertEqual(response.context['page_obj'].paginator.per_page, 20)

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
        self.assertContains(response, 'data-catalog-results')
        self.assertContains(response, 'data-catalog-sort-link')
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

    def setUp(self):
        """Log in as moderator for complex delete tests."""
        self.client.force_login(
            create_moderator(
                'complex-delete-moderator@example.com',
                '+79992000002',
            )
        )

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
class PropertyFormCascadeTests(TestCase):
    """Tests for property form dependent location selectors."""

    def setUp(self):
        """Create related location, complex, and building records."""
        self.client.force_login(
            create_moderator(
                'property-moderator@example.com',
                '+79992000003',
            )
        )
        self.region = Region.objects.create(name='Region 1', code='R1')
        self.other_region = Region.objects.create(name='Region 2', code='R2')
        self.city = City.objects.create(name='City 1', region=self.region)
        self.other_city = City.objects.create(
            name='City 2',
            region=self.other_region,
        )
        self.district = District.objects.create(
            name='District 1',
            city=self.city,
        )
        self.other_district = District.objects.create(
            name='District 2',
            city=self.other_city,
        )
        self.developer = Developer.objects.create(name='Developer 1')
        self.other_developer = Developer.objects.create(name='Developer 2')
        self.estate_type = RealEstateType.objects.create(name='Apartment')
        self.estate_class = RealEstateClass.objects.create(
            name='Comfort',
            weight=Decimal('1.00'),
        )
        self.complex = self.create_complex(
            'Complex 1',
            self.developer,
            self.district,
        )
        self.other_complex = self.create_complex(
            'Complex 2',
            self.other_developer,
            self.other_district,
        )
        self.building = RealEstateComplexBuilding.objects.create(
            number='1',
            real_estate_complex=self.complex,
        )
        self.other_building = RealEstateComplexBuilding.objects.create(
            number='2',
            real_estate_complex=self.other_complex,
        )
        self.layout = ApartmentLayout.objects.create(name='Layout 1')
        self.decoration = ApartmentDecoration.objects.create(
            name='Decoration 1'
        )
        self.window_view = WindowView.objects.create(name='Park')
        self.other_window_view = WindowView.objects.create(name='River')

    def create_complex(self, name, developer, district):
        """Create a complex with shared dictionary values."""
        return RealEstateComplex.objects.create(
            name=name,
            developer=developer,
            district=district,
            real_estate_class=self.estate_class,
            real_estate_type=self.estate_type,
        )

    def test_create_view_starts_without_building_options(self):
        """The property create form should not show all buildings initially."""
        response = self.client.get(reverse('property:create'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'static/js/dependent_selects.js')
        self.assertContains(response, 'data-cascade-selects')
        self.assertContains(response, 'property-form-data')
        self.assertFalse(response.context['buildings'].exists())
        self.assertEqual(response.context['current_complex'], '')
        self.assertEqual(
            {
                item['id']
                for item in response.context['property_form_data']['buildings']
            },
            {self.building.pk, self.other_building.pk},
        )
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'id_layout_image')
        self.assertContains(response, 'id_floor_plan_image')
        self.assertContains(response, 'id_window_view_image')
        self.assertContains(response, 'type="checkbox"')
        self.assertContains(response, 'Park')

    def test_invalid_create_post_restores_selected_location_chain(self):
        """A selected building should restore its dependent selectors."""
        response = self.client.post(
            reverse('property:create'),
            {
                'building': self.building.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['current_region'], self.region.pk)
        self.assertEqual(response.context['current_city'], self.city.pk)
        self.assertEqual(response.context['current_district'], self.district.pk)
        self.assertEqual(
            response.context['current_developer'],
            self.developer.pk,
        )
        self.assertEqual(response.context['current_complex'], self.complex.pk)
        self.assertEqual(response.context['current_building'], self.building.pk)
        self.assertEqual(
            list(response.context['buildings']),
            [self.building],
        )

    def test_property_form_rejects_non_image_extension(self):
        """The property form should reject unsupported upload extensions."""
        form = PropertyForm(
            data={
                'apartment_number': '101',
                'building': self.building.pk,
                'decoration': self.decoration.pk,
                'layout': self.layout.pk,
                'area': '42.00',
                'floor': '10',
                'property_cost': '1000000.00',
            },
            files={
                'layout_image': SimpleUploadedFile(
                    'layout.txt',
                    SIMPLE_GIF,
                    content_type='text/plain',
                ),
            },
        )

        self.assertFalse(form.is_valid())
        self.assertIn('layout_image', form.errors)

    def test_complexes_api_filters_by_developer_and_location(self):
        """The complexes API should support developer and location filters."""
        response = self.client.get(
            '/api/complexes/',
            {
                'developer_id': self.developer.pk,
                'region_id': self.region.pk,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item['id'] for item in response.json()],
            [self.complex.pk],
        )
        self.assertEqual(
            set(response.json()[0]),
            {
                'id',
                'name',
                'developer_id',
                'district_id',
                'district__city_id',
                'district__city__region_id',
            },
        )

    def test_complexes_api_rejects_invalid_id_filter(self):
        """The complexes API should reject invalid integer filters."""
        response = self.client.get(
            '/api/complexes/',
            {'region_id': 'not-a-number'},
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json(), {'error': 'Invalid region_id.'})

    def test_complexes_api_returns_empty_list_without_filters(self):
        """The complexes API should not expose a full unfiltered dump."""
        response = self.client.get('/api/complexes/')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])

    @override_settings(PUBLIC_CATALOG_API_MAX_RESULTS=1)
    def test_cities_api_limits_rows_and_fields(self):
        """The cities API should expose a bounded allowlisted payload."""
        City.objects.create(name='City 0', region=self.region)

        response = self.client.get(
            '/api/cities/',
            {'region_id': self.region.pk},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        self.assertEqual(set(response.json()[0]), {'id', 'name'})

    def test_buildings_api_requires_complex(self):
        """The buildings API should return rows only for a selected complex."""
        empty_response = self.client.get('/api/buildings/')
        selected_response = self.client.get(
            '/api/buildings/',
            {'complex_id': self.complex.pk},
        )

        self.assertEqual(empty_response.status_code, 200)
        self.assertEqual(empty_response.json(), [])
        self.assertEqual(
            [item['id'] for item in selected_response.json()],
            [self.building.pk],
        )
        self.assertEqual(
            set(selected_response.json()[0]),
            {'id', 'number', 'real_estate_complex_id'},
        )

    def test_property_list_has_detail_action(self):
        """The property list should link each row to its detail card."""
        property_obj = Property.objects.create(
            apartment_number='101',
            building=self.building,
            decoration=self.decoration,
            layout=self.layout,
            area=Decimal('42.00'),
            floor=10,
            property_cost=Decimal('1000000.00'),
        )

        response = self.client.get(reverse('property:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Подробнее')
        self.assertContains(
            response,
            reverse('property:detail', kwargs={'pk': property_obj.pk}),
        )

    def test_anonymous_property_pages_are_read_only(self):
        """Checks anonymous users can read property pages but cannot mutate."""
        property_obj = Property.objects.create(
            apartment_number='101',
            building=self.building,
            decoration=self.decoration,
            layout=self.layout,
            area=Decimal('42.00'),
            floor=10,
            property_cost=Decimal('1000000.00'),
        )
        self.client.logout()

        list_response = self.client.get(reverse('property:list'))
        detail_response = self.client.get(
            reverse('property:detail', kwargs={'pk': property_obj.pk})
        )
        create_response = self.client.get(reverse('property:create'))

        self.assertEqual(list_response.status_code, 200)
        self.assertContains(
            list_response,
            reverse('property:detail', kwargs={'pk': property_obj.pk}),
        )
        self.assertNotContains(list_response, reverse('property:create'))
        self.assertNotContains(
            list_response,
            reverse('property:update', kwargs={'pk': property_obj.pk}),
        )
        self.assertEqual(detail_response.status_code, 200)
        self.assertNotContains(
            detail_response,
            reverse('property:update', kwargs={'pk': property_obj.pk}),
        )
        self.assertNotContains(
            detail_response,
            reverse('property:delete', kwargs={'pk': property_obj.pk}),
        )
        self.assertEqual(create_response.status_code, 403)

    def test_property_list_formats_property_cost_with_spaces(self):
        """The property list should group price thousands with spaces."""
        Property.objects.create(
            apartment_number='101',
            building=self.building,
            decoration=self.decoration,
            layout=self.layout,
            area=Decimal('42.00'),
            floor=10,
            property_cost=Decimal('1000000.00'),
        )

        response = self.client.get(reverse('property:list'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '1 000 000,00')
        self.assertNotContains(response, '>1000000.00<')

    def test_property_detail_shows_title_window_views_and_images(self):
        """The property detail page should show new view and image fields."""
        property_obj = Property.objects.create(
            apartment_number='101',
            building=self.building,
            decoration=self.decoration,
            layout=self.layout,
            area=Decimal('42.00'),
            floor=10,
            property_cost=Decimal('1000000.00'),
            layout_image='property/layouts/layout.gif',
            floor_plan_image='property/floor_plans/floor-plan.gif',
            window_view_image='property/window_views/window-view.gif',
        )
        property_obj.window_views.add(self.window_view)

        response = self.client.get(
            reverse('property:detail', kwargs={'pk': property_obj.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Complex 1 - 1 - 101')
        self.assertContains(response, 'Вид из окна')
        self.assertContains(response, 'Park')
        self.assertContains(response, 'property/layouts/layout.gif')
        self.assertContains(response, 'property/floor_plans/floor-plan.gif')
        self.assertContains(response, 'property/window_views/window-view.gif')
        self.assertContains(
            response,
            'src="/media/property/layouts/layout.gif"',
        )
        self.assertContains(
            response,
            'src="/media/property/floor_plans/floor-plan.gif"',
        )
        self.assertContains(
            response,
            'src="/media/property/window_views/window-view.gif"',
        )
        self.assertContains(response, 'static/js/image_modal.js')
        self.assertContains(response, 'static/css/image_modal.css')
        self.assertContains(response, 'id="image-preview-modal"')
        self.assertContains(response, 'data-image-modal="true"', count=3)
        self.assertNotContains(
            response,
            'href="/media/property/layouts/layout.gif" target="_blank"',
        )
        self.assertNotContains(
            response,
            'href="/media/property/floor_plans/floor-plan.gif" target="_blank"',
        )
        self.assertNotContains(
            response,
            'href="/media/property/window_views/window-view.gif" target="_blank"',
        )

    def test_update_view_shows_current_image_filenames(self):
        """The property update form should show saved image filenames."""
        property_obj = Property.objects.create(
            apartment_number='101',
            building=self.building,
            decoration=self.decoration,
            layout=self.layout,
            area=Decimal('42.00'),
            floor=10,
            property_cost=Decimal('1000000.00'),
            layout_image='property/layouts/layout.gif',
            floor_plan_image='property/floor_plans/floor-plan.gif',
            window_view_image='property/window_views/window-view.gif',
        )

        response = self.client.get(
            reverse('property:update', kwargs={'pk': property_obj.pk})
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'layout.gif')
        self.assertContains(response, 'floor-plan.gif')
        self.assertContains(response, 'window-view.gif')
        self.assertContains(response, '/media/property/layouts/layout.gif')
        self.assertContains(response, 'id_clear_layout_image')
        self.assertContains(response, 'id_clear_floor_plan_image')
        self.assertContains(response, 'id_clear_window_view_image')
        self.assertContains(response, 'data-clear-file-button')
        self.assertContains(response, '&times;')
        self.assertContains(response, 'data-image-modal="true"', count=3)
        self.assertNotContains(
            response,
            'href="/media/property/layouts/layout.gif" target="_blank"',
        )
        self.assertContains(
            response,
            '/media/property/floor_plans/floor-plan.gif',
        )
        self.assertContains(
            response,
            '/media/property/window_views/window-view.gif',
        )

    def test_update_view_clears_selected_image_files(self):
        """The property update form should clear and delete selected images."""
        with TemporaryDirectory() as media_root:
            media_root_path = Path(media_root)
            image_paths = [
                media_root_path / 'property/layouts/layout.gif',
                media_root_path / 'property/floor_plans/floor-plan.gif',
                media_root_path / 'property/window_views/window-view.gif',
            ]
            for image_path in image_paths:
                image_path.parent.mkdir(parents=True, exist_ok=True)
                image_path.write_bytes(SIMPLE_GIF)

            with override_settings(MEDIA_ROOT=media_root):
                property_obj = Property.objects.create(
                    apartment_number='101',
                    building=self.building,
                    decoration=self.decoration,
                    layout=self.layout,
                    area=Decimal('42.00'),
                    floor=10,
                    property_cost=Decimal('1000000.00'),
                    layout_image='property/layouts/layout.gif',
                    floor_plan_image='property/floor_plans/floor-plan.gif',
                    window_view_image='property/window_views/window-view.gif',
                )
                response = self.client.post(
                    reverse(
                        'property:update',
                        kwargs={'pk': property_obj.pk},
                    ),
                    {
                        'apartment_number': '101',
                        'building': self.building.pk,
                        'decoration': self.decoration.pk,
                        'layout': self.layout.pk,
                        'area': '42.00',
                        'floor': '10',
                        'property_cost': '1000000.00',
                        'clear_layout_image': 'on',
                        'clear_floor_plan_image': 'on',
                        'clear_window_view_image': 'on',
                    },
                )

                self.assertRedirects(
                    response,
                    reverse(
                        'property:detail',
                        kwargs={'pk': property_obj.pk},
                    ),
                )
                property_obj.refresh_from_db()
                self.assertFalse(property_obj.layout_image)
                self.assertFalse(property_obj.floor_plan_image)
                self.assertFalse(property_obj.window_view_image)

            for image_path in image_paths:
                self.assertFalse(image_path.exists())

    def test_create_view_saves_window_views_and_image_fields(self):
        """The property create form should save window views and images."""
        with TemporaryDirectory() as media_root:
            with override_settings(MEDIA_ROOT=media_root):
                response = self.client.post(
                    reverse('property:create'),
                    {
                        'apartment_number': '101',
                        'building': self.building.pk,
                        'decoration': self.decoration.pk,
                        'layout': self.layout.pk,
                        'area': '42.00',
                        'floor': '10',
                        'property_cost': '1000000.00',
                        'window_views': [
                            self.window_view.pk,
                            self.other_window_view.pk,
                        ],
                        'layout_image': SimpleUploadedFile(
                            'layout.gif',
                            SIMPLE_GIF,
                            content_type='image/gif',
                        ),
                        'floor_plan_image': SimpleUploadedFile(
                            'floor-plan.gif',
                            SIMPLE_GIF,
                            content_type='image/gif',
                        ),
                        'window_view_image': SimpleUploadedFile(
                            'window-view.gif',
                            SIMPLE_GIF,
                            content_type='image/gif',
                        ),
                    },
                )

        self.assertRedirects(response, reverse('property:list'))
        property_obj = Property.objects.get(apartment_number='101')
        self.assertEqual(
            set(property_obj.window_views.values_list('pk', flat=True)),
            {self.window_view.pk, self.other_window_view.pk},
        )
        self.assertTrue(property_obj.layout_image.name)
        self.assertTrue(property_obj.floor_plan_image.name)
        self.assertTrue(property_obj.window_view_image.name)
