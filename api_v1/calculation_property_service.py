from rest_framework.exceptions import PermissionDenied, ValidationError

from mortgage.forms import MortgageForm
from mortgage.views import _create_manual_property
from property.models import Property, RealEstateComplexBuilding
from users.roles import can_manage_catalogs


MANUAL_PROPERTY_FIELDS = {
    'cityId': 'OBJECT_CITY',
    'districtId': 'OBJECT_DISTRICT',
    'developerId': 'OBJECT_DEVELOPER',
    'realEstateComplexId': 'OBJECT_COMPLEX',
    'buildingId': 'OBJECT_BUILDING',
    'apartmentNumber': 'OBJECT_APARTMENT_NUMBER',
    'area': 'OBJECT_AREA',
    'layoutId': 'OBJECT_LAYOUT',
    'floor': 'OBJECT_FLOOR',
    'decorationId': 'OBJECT_DECORATION',
}


def validate_manual_property(values):
    """Reuse the established mortgage form for object fields and cascades."""
    data = {field: values.get(name, '')
            for name, field in MANUAL_PROPERTY_FIELDS.items()}
    data.update({
        'PROPERTY_COST': '1000000', 'DISCOUNT_MARKUP_TYPE': 'discount',
        'DISCOUNT_MARKUP_VALUE': '0', 'INITIAL_PAYMENT_PERCENT': '20',
        'INITIAL_PAYMENT_RUBLES': '200000',
        'INITIAL_PAYMENT_DATE': '2026-01-01', 'MORTGAGE_TERM': '360',
        'ANNUAL_RATE': '15', 'TRENCH_COUNT': '1', 'HAS_GRACE_PERIOD': 'no',
    })
    form = MortgageForm(data)
    if not form.is_valid():
        names = {field: name for name, field in MANUAL_PROPERTY_FIELDS.items()}
        raise ValidationError({names.get(field, 'nonFieldErrors'): errors
                               for field, errors in form.errors.items()})
    if not form.has_manual_property_data():
        raise ValidationError('Заполните данные объекта.')
    return {field: form.cleaned_data[field]
            for field in MANUAL_PROPERTY_FIELDS.values()}


def resolve_saved_property(validated_data, user):
    """Resolve an existing apartment or create it under catalog permissions."""
    if validated_data.get('property') is not None:
        return validated_data['property']
    data = validated_data['parameters']['manualProperty']
    # Serialize creation in this building without changing catalog uniqueness.
    RealEstateComplexBuilding.objects.select_for_update().get(
        pk=data['OBJECT_BUILDING'].pk
    )
    existing = Property.objects.filter(
        building=data['OBJECT_BUILDING'],
        apartment_number=data['OBJECT_APARTMENT_NUMBER'],
    ).order_by('pk').first()
    if existing is not None:
        return existing
    if not can_manage_catalogs(user):
        raise PermissionDenied(
            'Создание нового объекта доступно модератору каталога.'
        )
    return _create_manual_property(
        data, validated_data['parameters']['propertyCost']
    )


def build_unsaved_property(parameters):
    """Build a report-only object without writing any catalog records."""
    data = parameters.get('manualProperty')
    if not data:
        return None
    return Property(
        building=data['OBJECT_BUILDING'],
        apartment_number=data['OBJECT_APARTMENT_NUMBER'],
        layout=data['OBJECT_LAYOUT'], decoration=data['OBJECT_DECORATION'],
        area=data['OBJECT_AREA'], floor=data['OBJECT_FLOOR'],
        property_cost=parameters['propertyCost'],
    )
