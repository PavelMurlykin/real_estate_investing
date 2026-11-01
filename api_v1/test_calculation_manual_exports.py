from io import BytesIO

import openpyxl
import pytest
from django.contrib.auth.models import Group
from django.test import Client
from django.urls import reverse
from docx import Document

from location.models import City
from mortgage.models import MortgageCalculation
from property.models import Property
from trench_mortgage.models import TrenchMortgageCalculation
from users.roles import MODERATOR_GROUP_NAME

from .test_mortgage import build_mortgage_payload
from .test_saved_mortgage import calculation_user, saved_calculation_property
from .test_trench_mortgage import build_trench_mortgage_payload


def manual_parameters(property_object, apartment_number='NEW-42'):
    """Return complete object inputs without relying on a persisted apartment."""
    complex_object = property_object.building.real_estate_complex
    return {
        'cityId': complex_object.district.city_id,
        'districtId': complex_object.district_id,
        'developerId': complex_object.developer_id,
        'realEstateComplexId': complex_object.pk,
        'buildingId': property_object.building_id,
        'apartmentNumber': apartment_number, 'area': '51.25', 'floor': 9,
        'layoutId': property_object.layout_id,
        'decorationId': property_object.decoration_id,
    }


def scenario_parameters(calculation_type, **overrides):
    """Return the appropriate bounded financial scenario for both APIs."""
    builder = (build_trench_mortgage_payload if calculation_type == 'trench'
               else build_mortgage_payload)
    return builder(**overrides)


@pytest.mark.django_db
@pytest.mark.parametrize('calculation_type', ['market', 'trench'])
@pytest.mark.parametrize('export_format', ['excel', 'word'])
@pytest.mark.parametrize('manual', [False, True])
def test_unsaved_exports_include_values_without_database_writes(
    client, saved_calculation_property, calculation_type, export_format, manual,
):
    """Export anonymous scenarios and manual apartments without persisting them."""
    overrides = {}
    if manual:
        overrides['manualProperty'] = manual_parameters(saved_calculation_property)
    prefix = 'unsaved_trench' if calculation_type == 'trench' else 'unsaved_mortgage'
    response = client.post(
        reverse(f'api_v1:{prefix}_export_{export_format}'),
        {'parameters': scenario_parameters(calculation_type, **overrides)},
        content_type='application/json',
    )
    assert response.status_code == 200
    assert Property.objects.count() == 1
    assert MortgageCalculation.objects.count() == 0
    assert TrenchMortgageCalculation.objects.count() == 0
    if export_format == 'excel':
        workbook = openpyxl.load_workbook(BytesIO(response.content))
        values = [cell for row in workbook.active.values for cell in row]
        assert 4500000 in values
        if manual:
            assert 'NEW-42' in values
            assert 51.25 in values
    else:
        document = Document(BytesIO(response.content))
        text = '\n'.join(cell.text for table in document.tables
                         for row in table.rows for cell in row.cells)
        assert '4 500 000' in text.replace('\xa0', ' ')
        if manual:
            assert 'NEW-42' in text
            assert '51,25' in text or '51.25' in text


@pytest.mark.django_db
@pytest.mark.parametrize('calculation_type', ['market', 'trench'])
def test_manual_save_requires_catalog_permissions_and_is_atomic(
    client, calculation_user, saved_calculation_property, calculation_type,
):
    """Keep ordinary users from creating apartments through either calculator."""
    client.force_login(calculation_user)
    url = (reverse('api_v1:saved_trench_mortgage_calculation_create')
           if calculation_type == 'trench'
           else reverse('api_v1:saved_mortgage_calculation_list'))
    payload = {'parameters': scenario_parameters(calculation_type,
        manualProperty=manual_parameters(saved_calculation_property))}
    denied = client.post(url, payload, content_type='application/json')
    assert denied.status_code == 403
    assert Property.objects.count() == 1
    moderator_group = Group.objects.get(name=MODERATOR_GROUP_NAME)
    calculation_user.groups.add(moderator_group)
    saved = client.post(url, payload, content_type='application/json')
    assert saved.status_code == 201
    created = Property.objects.get(apartment_number='NEW-42')
    assert created.area == 51.25
    assert created.property_cost == 5000000
    repeated = client.post(url, payload, content_type='application/json')
    assert repeated.status_code == 201
    assert Property.objects.filter(apartment_number='NEW-42').count() == 1


@pytest.mark.django_db
def test_manual_object_rejects_inconsistent_cascades(client, saved_calculation_property):
    """Validate the same district/city relationships as the Django form."""
    manual = manual_parameters(saved_calculation_property)
    city = saved_calculation_property.building.real_estate_complex.district.city
    other_city = City.objects.create(name='Другой город', region=city.region)
    manual['cityId'] = other_city.pk
    response = client.post(reverse('api_v1:mortgage_calculate'),
        build_mortgage_payload(manualProperty=manual), content_type='application/json')
    assert response.status_code == 400
    assert 'districtId' in response.json()['manualProperty']
    assert Property.objects.count() == 1


@pytest.mark.django_db
def test_unsaved_exports_require_csrf():
    """Generating a file must keep the established unsafe-method protection."""
    response = Client(enforce_csrf_checks=True).post(
        reverse('api_v1:unsaved_mortgage_export_excel'),
        {'parameters': build_mortgage_payload()}, content_type='application/json')
    assert response.status_code == 403
