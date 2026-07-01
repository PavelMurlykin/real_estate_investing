# mortgage/views.py
import decimal

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import DecimalField, OuterRef, Subquery
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from location.models import City, District
from property.models import (
    ApartmentDecoration,
    ApartmentLayout,
    Developer,
    Property,
    RealEstateComplex,
    RealEstateComplexBuilding,
)
from trench_mortgage.views import (
    _build_trench_payment_schedule,
    _build_trench_input_rows,
    _calculate_trench_mortgage,
    _calculate_months_remaining,
    _calculate_trench_overpayment,
    _export_trench_excel,
    _format_payment_schedule as _format_trench_payment_schedule,
    _format_result as _format_trench_result,
    _parse_trench_inputs,
    _prepare_mortgage_data as _prepare_trench_mortgage_data,
    _resolve_default_rate as _resolve_trench_default_rate,
    _resolve_trench_count,
    _save_trench_calculation,
)
from trench_mortgage.models import Trench, TrenchMortgageCalculation
from users.roles import can_manage_catalogs, can_view_all_private_records

from bank.models import Bank, BankProgram, KeyRate

from .excel import (
    MortgageExcelData,
    export_mortgage_excel,
    export_saved_mortgage_calculation_excel,
)
from .forms import MortgageForm
from .models import MortgageCalculation
from .mortgage_calculator import MortgageCalculator
from .utils import (
    apply_calculation_filters,
    apply_calculation_sort,
    annotate_calculation_table_values,
    build_calculation_table_headers,
    format_currency,
    get_calculation_city_choices,
    get_calculation_filters,
    get_calculation_sort,
)
from .word import (
    export_mortgage_word,
    export_saved_mortgage_calculation_word,
    export_trench_mortgage_word,
)


CALCULATION_LIST_PAGE_SIZE = 20
FORM_DATA_CACHE_TIMEOUT = 600
PROPERTY_FORM_DATA_CACHE_KEY = 'mortgage:property_form_data:v1'
MORTGAGE_PROGRAM_FORM_DATA_CACHE_KEY = 'mortgage:program_form_data:v1'


def _get_target_customer(request):
    customer_id = request.POST.get('customer') or request.GET.get('customer')
    if not customer_id or not request.user.is_authenticated:
        return None

    from customer.models import Customer

    queryset = Customer.objects.all()
    if not can_view_all_private_records(request.user):
        queryset = queryset.filter(user=request.user)
    return get_object_or_404(queryset, pk=customer_id)


def _filter_private_queryset_for_user(queryset, user):
    """Scope private records to the current user unless they are admin."""
    if not getattr(user, 'is_authenticated', False):
        return queryset.none()
    if can_view_all_private_records(user):
        return queryset
    return queryset.filter(user=user)


def _get_calculation_owner(request, target_customer=None):
    """Return the user who should own a newly saved calculation."""
    if target_customer is not None:
        return target_customer.user
    return request.user


def _can_save_calculation_for_property(request, property_obj, mortgage_form):
    """Return whether the current request may persist a calculation."""
    if not request.user.is_authenticated:
        return False
    if property_obj is not None:
        return True
    return (
        mortgage_form.has_manual_property_data()
        and can_manage_catalogs(request.user)
    )


def _attach_calculation_to_customer(customer, calculation):
    if customer is None:
        return

    from customer.models import CustomerCalculation

    CustomerCalculation.objects.get_or_create(
        customer=customer,
        calculation=calculation,
    )


def _attach_trench_calculation_to_customer(customer, calculation):
    """Attach a saved trench mortgage calculation to a customer."""
    if customer is None:
        return

    from customer.models import CustomerTrenchCalculation

    CustomerTrenchCalculation.objects.get_or_create(
        customer=customer,
        calculation=calculation,
    )


def _attach_calculations_to_customer(customer, calculations):
    """Attach calculations to a customer using one read and one bulk insert."""
    if customer is None:
        return

    from customer.models import CustomerCalculation

    calculation_ids = [calculation.pk for calculation in calculations]
    if not calculation_ids:
        return

    existing_calculation_ids = set(
        CustomerCalculation.objects.filter(
            customer=customer,
            calculation_id__in=calculation_ids,
        ).values_list('calculation_id', flat=True)
    )
    CustomerCalculation.objects.bulk_create(
        [
            CustomerCalculation(
                customer=customer,
                calculation=calculation,
            )
            for calculation in calculations
            if calculation.pk not in existing_calculation_ids
        ],
        ignore_conflicts=True,
    )


def _attach_trench_calculations_to_customer(customer, calculations):
    """Attach trench calculations to a customer in bulk."""
    if customer is None:
        return

    from customer.models import CustomerTrenchCalculation

    calculation_ids = [calculation.pk for calculation in calculations]
    if not calculation_ids:
        return

    existing_calculation_ids = set(
        CustomerTrenchCalculation.objects.filter(
            customer=customer,
            calculation_id__in=calculation_ids,
        ).values_list('calculation_id', flat=True)
    )
    CustomerTrenchCalculation.objects.bulk_create(
        [
            CustomerTrenchCalculation(
                customer=customer,
                calculation=calculation,
            )
            for calculation in calculations
            if calculation.pk not in existing_calculation_ids
        ],
        ignore_conflicts=True,
    )


def _build_pagination_querystring(request):
    """Return current query parameters without the page parameter."""
    query_parameters = request.GET.copy()
    query_parameters.pop('page', None)
    return query_parameters.urlencode()


def _normalize_discount_markup_values(cleaned_data):
    """Возвращает процент, рубли и итоговую стоимость после корректировки."""
    property_cost = float(cleaned_data['PROPERTY_COST'])
    discount_markup_percent = float(
        cleaned_data.get('DISCOUNT_MARKUP_VALUE', 0) or 0
    )
    discount_markup_rubles = float(
        cleaned_data.get('DISCOUNT_MARKUP_RUBLES', 0) or 0
    )
    discount_markup_source = cleaned_data.get('DISCOUNT_MARKUP_SOURCE')

    if discount_markup_source == 'rubles':
        if property_cost > 0:
            discount_markup_percent = (
                discount_markup_rubles / property_cost
            ) * 100
        else:
            discount_markup_percent = 0
    else:
        discount_markup_rubles = (
            property_cost * discount_markup_percent / 100
        )

    if cleaned_data['DISCOUNT_MARKUP_TYPE'] == 'discount':
        final_property_cost = property_cost - discount_markup_rubles
    else:
        final_property_cost = property_cost + discount_markup_rubles

    return (
        discount_markup_percent,
        discount_markup_rubles,
        final_property_cost,
    )


def _normalize_initial_payment_values(cleaned_data, final_property_cost):
    """Возвращает согласованные значения первоначального взноса."""
    initial_payment_percent = float(
        cleaned_data.get('INITIAL_PAYMENT_PERCENT', 0) or 0
    )
    initial_payment_rubles = float(
        cleaned_data.get('INITIAL_PAYMENT_RUBLES', 0) or 0
    )
    initial_payment_source = cleaned_data.get('INITIAL_PAYMENT_SOURCE')

    if initial_payment_source == 'rubles':
        initial_payment_percent = (
            initial_payment_rubles / final_property_cost * 100
            if final_property_cost > 0
            else 0
        )
    else:
        initial_payment_rubles = (
            final_property_cost * initial_payment_percent / 100
        )

    return initial_payment_percent, initial_payment_rubles


def _populate_market_report_context(
    context,
    data,
    final_property_cost,
    initial_payment_percent,
):
    """Add a formatted market mortgage report to the template context."""
    if (
        data.get('HAS_GRACE_PERIOD') == 'yes'
        and (
            data.get('GRACE_PERIOD_TERM') in (None, '')
            or data.get('GRACE_PERIOD_RATE') in (None, '')
        )
    ):
        return False

    calculator = MortgageCalculator(
        property_cost=float(final_property_cost),
        initial_payment_percent=float(initial_payment_percent),
        initial_payment_date=data['INITIAL_PAYMENT_DATE'],
        mortgage_term=int(data['MORTGAGE_TERM']),
        annual_rate=float(data['ANNUAL_RATE']),
        has_grace_period=data['HAS_GRACE_PERIOD'] == 'yes',
        grace_period_term=int(data['GRACE_PERIOD_TERM'] or 0),
        grace_period_rate=float(data['GRACE_PERIOD_RATE'] or 0),
    )
    result = calculator.calculate()

    formatted_result = {}
    for key, value in result.items():
        if key in ['grace_payments_count', 'main_payments_count']:
            formatted_result[key] = int(value) if value else 0
        elif isinstance(value, (int, float, decimal.Decimal)):
            formatted_result[key] = format_currency(value)
        else:
            formatted_result[key] = value

    payment_schedule = calculator.get_payment_schedule()
    for payment in payment_schedule:
        for key in [
            'payment_amount',
            'interest_amount',
            'principal_amount',
            'remaining_debt',
        ]:
            if key in payment:
                payment[key] = format_currency(payment[key])

    context['result'] = formatted_result
    context['market_result'] = formatted_result
    context['has_grace_period'] = data['HAS_GRACE_PERIOD'] == 'yes'
    context['payment_schedule'] = payment_schedule
    context['market_payment_schedule'] = payment_schedule
    return result


def _populate_trench_report_context(
    context,
    request,
    data,
    property_obj,
    report_errors=False,
):
    """Add a formatted trench mortgage report to the template context."""
    trench_mortgage_data, prep_errors = (
        _prepare_trench_mortgage_data(data)
    )
    trench_entries, input_rows, trench_errors = _parse_trench_inputs(
        post_data=request.POST,
        trench_count=trench_mortgage_data['trench_count'],
        loan_amount=trench_mortgage_data['total_loan_amount'],
        default_annual_rate=trench_mortgage_data['annual_rate'],
    )
    context['trench_input_rows'] = input_rows
    all_errors = prep_errors + trench_errors
    if all_errors:
        if report_errors:
            context['error_message'] = ' '.join(all_errors)
            context['active_calculation_type'] = 'trench'
        return None

    trench_calculation, calc_errors = _calculate_trench_mortgage(
        trench_mortgage_data, trench_entries
    )
    if calc_errors:
        if report_errors:
            context['error_message'] = ' '.join(calc_errors)
            context['active_calculation_type'] = 'trench'
        return None

    context['trench_result'] = _format_trench_result(trench_calculation)
    context['trench_payment_schedule'] = _format_trench_payment_schedule(
        trench_calculation['payment_schedule']
    )
    context['can_export_trench_result'] = True
    return trench_calculation


def _get_property_initial(property_obj):
    """Return calculator form initial data from an existing property."""
    real_estate_complex = property_obj.building.real_estate_complex
    district = real_estate_complex.district

    return {
        'OBJECT_CITY': district.city_id,
        'OBJECT_DISTRICT': district.pk,
        'OBJECT_DEVELOPER': real_estate_complex.developer_id,
        'OBJECT_COMPLEX': real_estate_complex.pk,
        'OBJECT_BUILDING': property_obj.building_id,
        'OBJECT_APARTMENT_NUMBER': property_obj.apartment_number,
        'OBJECT_AREA': property_obj.area,
        'OBJECT_LAYOUT': property_obj.layout_id,
        'OBJECT_FLOOR': property_obj.floor,
        'OBJECT_DECORATION': property_obj.decoration_id,
    }


def _get_property_calculator_initial(property_obj):
    """Return mortgage calculator initial data for a selected property."""
    initial = {
        'PROPERTY': property_obj.pk,
        'PROPERTY_COST': property_obj.property_cost,
    }
    initial.update(_get_property_initial(property_obj))
    return initial


def _get_property_payload(property_obj):
    """Return property data used by the calculator UI."""
    real_estate_complex = property_obj.building.real_estate_complex
    district = real_estate_complex.district

    return {
        'id': property_obj.pk,
        'property_cost': str(property_obj.property_cost),
        'city_id': district.city_id,
        'district_id': district.pk,
        'developer_id': real_estate_complex.developer_id,
        'complex_id': real_estate_complex.pk,
        'building_id': property_obj.building_id,
        'apartment_number': property_obj.apartment_number,
        'area': str(property_obj.area),
        'layout_id': property_obj.layout_id,
        'floor': property_obj.floor,
        'decoration_id': property_obj.decoration_id,
    }


def _get_property_form_data():
    """Return cached selector data for the mortgage object block."""
    return cache.get_or_set(
        PROPERTY_FORM_DATA_CACHE_KEY,
        _build_property_form_data,
        FORM_DATA_CACHE_TIMEOUT,
    )


def _build_property_form_data():
    """Build reusable selector data for the mortgage object block."""
    districts = District.objects.select_related('city').order_by('name')
    complexes = RealEstateComplex.objects.select_related(
        'developer',
        'district__city',
    ).order_by('name')
    buildings = RealEstateComplexBuilding.objects.select_related(
        'real_estate_complex'
    ).order_by('real_estate_complex__name', 'number')
    properties = Property.objects.select_related(
        'building',
        'building__real_estate_complex__developer',
        'building__real_estate_complex__district__city',
        'layout',
        'decoration',
    ).order_by('building_id', 'apartment_number')

    return {
        'cities': list(
            City.objects.order_by('name').values('id', 'name', 'region_id')
        ),
        'districts': list(districts.values('id', 'name', 'city_id')),
        'complexes': list(
            complexes.values(
                'id',
                'name',
                'developer_id',
                'district_id',
                'district__city_id',
            )
        ),
        'buildings': list(
            buildings.values('id', 'number', 'real_estate_complex_id')
        ),
        'properties': [
            _get_property_payload(property_obj)
            for property_obj in properties
        ],
    }


def _get_latest_key_rate():
    """Return the latest stored CBR key rate."""
    return (
        KeyRate.objects.filter(is_active=True)
        .order_by('-meeting_date')
        .values_list('key_rate', flat=True)
        .first()
        or decimal.Decimal('0')
    )


def _decimal_to_json_value(value):
    """Convert decimal values to frontend-friendly strings."""
    if value in (None, ''):
        return ''
    return str(value)


def _get_mortgage_program_form_data():
    """Return cached bank mortgage program selector data."""
    return cache.get_or_set(
        MORTGAGE_PROGRAM_FORM_DATA_CACHE_KEY,
        _build_mortgage_program_form_data,
        FORM_DATA_CACHE_TIMEOUT,
    )


def _build_mortgage_program_form_data():
    """Build bank mortgage program data for the calculator UI."""
    banks = Bank.objects.filter(
        is_active=True,
        mortgage_programs__isnull=False,
    ).distinct().order_by('name')
    bank_programs = (
        BankProgram.objects.select_related('bank', 'mortgage_program')
        .prefetch_related('mortgage_program__regional_credit_limits')
        .filter(bank__in=banks, is_active=True)
        .order_by('bank__name', 'mortgage_program__name')
    )

    return {
        'key_rate': _decimal_to_json_value(_get_latest_key_rate()),
        'banks': list(banks.values('id', 'name', 'logo_url')),
        'programs': [
            {
                'id': bank_program.pk,
                'bank_id': bank_program.bank_id,
                'program_id': bank_program.mortgage_program_id,
                'program_name': bank_program.mortgage_program.name,
                'interest_rate': _decimal_to_json_value(
                    bank_program.interest_rate
                ),
                'minimum_initial_payment_percent': _decimal_to_json_value(
                    bank_program.minimum_initial_payment_percent
                ),
                'maximum_loan_term_years': (
                    bank_program.maximum_loan_term_years or ''
                ),
                'is_preferential': (
                    bank_program.mortgage_program.is_preferential
                ),
                'credit_limit': _decimal_to_json_value(
                    bank_program.mortgage_program.credit_limit
                ),
                'regional_credit_limits': [
                    {
                        'region_id': regional_limit.region_id,
                        'credit_limit': _decimal_to_json_value(
                            regional_limit.credit_limit
                        ),
                    }
                    for regional_limit in (
                        bank_program.mortgage_program
                        .regional_credit_limits.all()
                    )
                    if regional_limit.is_active
                ],
            }
            for bank_program in bank_programs
        ],
    }


def _get_selected_property_from_form_data(form_data):
    """Return a selected property from hidden id or apartment number."""
    selected_id = form_data.get('PROPERTY')
    if selected_id:
        return (
            Property.objects.select_related(
                'building__real_estate_complex__developer',
                'building__real_estate_complex__district__city',
                'building',
                'layout',
                'decoration',
            )
            .filter(id=selected_id)
            .first()
        )

    building_id = form_data.get('OBJECT_BUILDING')
    apartment_number = (form_data.get('OBJECT_APARTMENT_NUMBER') or '').strip()
    if not building_id or not apartment_number:
        return None

    return (
        Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex__district__city',
            'building',
            'layout',
            'decoration',
        )
        .filter(
            building_id=building_id,
            apartment_number=apartment_number,
        )
        .order_by('pk')
        .first()
    )


def _create_manual_property(cleaned_data, property_cost):
    """Create a property from manually filled calculator object data."""
    return Property.objects.create(
        apartment_number=cleaned_data['OBJECT_APARTMENT_NUMBER'],
        building=cleaned_data['OBJECT_BUILDING'],
        decoration=cleaned_data['OBJECT_DECORATION'],
        layout=cleaned_data['OBJECT_LAYOUT'],
        area=cleaned_data['OBJECT_AREA'],
        floor=cleaned_data['OBJECT_FLOOR'],
        property_cost=decimal.Decimal(str(property_cost)),
    )


def _build_calculation(property_obj, data, result, values, user=None):
    """Build a saved mortgage calculation for a property-backed scenario."""
    return MortgageCalculation(
        user=user,
        property=property_obj,
        base_property_cost=decimal.Decimal(str(values['base_property_cost'])),
        initial_payment_percent=decimal.Decimal(
            str(values['initial_payment_percent'])
        ),
        initial_payment_date=data['INITIAL_PAYMENT_DATE'],
        mortgage_term=data['MORTGAGE_TERM'],
        annual_rate=decimal.Decimal(str(data['ANNUAL_RATE'])),
        has_grace_period=data['HAS_GRACE_PERIOD'] == 'yes',
        grace_period_term=data['GRACE_PERIOD_TERM'],
        grace_period_rate=decimal.Decimal(
            str(data['GRACE_PERIOD_RATE'] or 0)
        ),
        discount_markup_type=data['DISCOUNT_MARKUP_TYPE'],
        discount_markup_value=decimal.Decimal(
            str(values['discount_markup_value'])
        ),
        final_property_cost=decimal.Decimal(
            str(values['final_property_cost'])
        ),
        grace_payments_count=result['grace_payments_count'],
        grace_period_end_date=result['grace_period_end_date'],
        grace_monthly_payment=decimal.Decimal(
            str(result['grace_monthly_payment'])
        ),
        loan_after_grace=decimal.Decimal(str(result['loan_after_grace'])),
        main_payments_count=result['main_payments_count'],
        mortgage_end_date=result['mortgage_end_date'],
        main_monthly_payment=decimal.Decimal(
            str(result['main_monthly_payment'])
        ),
        total_loan_amount=decimal.Decimal(str(result['total_loan_amount'])),
        total_overpayment=decimal.Decimal(str(result['total_overpayment'])),
    )


def _get_property_from_query(request):
    """Return the property requested for calculator prefill."""
    property_id = (request.GET.get('property_id') or '').strip()
    if not property_id or not property_id.isdecimal():
        return None

    return get_object_or_404(
        Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex__district__city',
            'building',
            'layout',
            'decoration',
        ),
        pk=property_id,
    )


def _get_sample_calculation(request):
    """Возвращает расчет-образец для предзаполнения формы калькулятора."""
    sample_calculation_id = (request.GET.get('sample') or '').strip()
    if not sample_calculation_id or not sample_calculation_id.isdecimal():
        return None

    queryset = MortgageCalculation.objects.select_related(
        'property',
        'property__building',
        'property__building__real_estate_complex',
        'property__building__real_estate_complex__district',
        'property__layout',
        'property__decoration',
    )
    return get_object_or_404(
        _filter_private_queryset_for_user(queryset, request.user),
        pk=sample_calculation_id,
    )


def _get_calculation_form_initial(calculation):
    """Формирует initial-данные формы из сохраненного расчета."""
    discount_markup_rubles = (
        calculation.base_property_cost
        * calculation.discount_markup_value
        / decimal.Decimal('100')
    )
    initial_payment_rubles = calculation.initial_payment_amount
    grace_period_term = calculation.grace_period_term or 0
    has_grace_period = 'yes' if calculation.has_grace_period else 'no'

    initial = {
        'PROPERTY': calculation.property_id,
        'PROPERTY_COST': calculation.base_property_cost,
        'DISCOUNT_MARKUP_TYPE': calculation.discount_markup_type,
        'DISCOUNT_MARKUP_VALUE': calculation.discount_markup_value,
        'DISCOUNT_MARKUP_RUBLES': discount_markup_rubles,
        'DISCOUNT_MARKUP_SOURCE': 'percent',
        'INITIAL_PAYMENT_PERCENT': calculation.initial_payment_percent,
        'INITIAL_PAYMENT_RUBLES': initial_payment_rubles,
        'INITIAL_PAYMENT_SOURCE': 'percent',
        'INITIAL_PAYMENT_DATE': calculation.initial_payment_date,
        'MORTGAGE_TERM_YEARS': calculation.mortgage_term // 12,
        'MORTGAGE_TERM': calculation.mortgage_term,
        'ANNUAL_RATE': calculation.annual_rate,
        'HAS_GRACE_PERIOD': has_grace_period,
        'GRACE_PERIOD_TERM_YEARS': grace_period_term // 12,
        'GRACE_PERIOD_TERM': grace_period_term,
        'GRACE_PERIOD_RATE': calculation.grace_period_rate,
    }
    initial.update(_get_property_initial(calculation.property))
    return initial


def mortgage_calculator(request):
    # Инициализация формы
    """Описание метода mortgage_calculator.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        request: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    target_customer = _get_target_customer(request)
    sample_calculation = (
        _get_sample_calculation(request)
        if request.method == 'GET'
        else None
    )
    selected_property = (
        _get_property_from_query(request)
        if request.method == 'GET' and sample_calculation is None
        else None
    )

    if request.method == 'POST':
        form_data = request.POST.copy()
        submitted_calculation_type = (
            form_data.get('calculate') or form_data.get('export')
            or form_data.get('export_word')
        )
        if submitted_calculation_type in ('market', 'trench'):
            form_data['CALCULATION_TYPE'] = submitted_calculation_type
        selected_property = _get_selected_property_from_form_data(form_data)
        if selected_property:
            form_data['PROPERTY'] = str(selected_property.pk)
            if not form_data.get('PROPERTY_COST'):
                form_data['PROPERTY_COST'] = str(
                    selected_property.property_cost
                )
            for field_name, value in _get_property_initial(
                selected_property
            ).items():
                if not form_data.get(field_name):
                    form_data[field_name] = str(value)
        mortgage_form = MortgageForm(form_data)
    elif sample_calculation is not None:
        mortgage_form = MortgageForm(
            initial=_get_calculation_form_initial(sample_calculation)
        )
    elif selected_property is not None:
        mortgage_form = MortgageForm(
            initial=_get_property_calculator_initial(selected_property)
        )
    else:
        mortgage_form = MortgageForm()

    posted_calculation_type = (
        request.POST.get('calculate')
        or request.POST.get('export')
        or request.POST.get('export_word')
    )
    active_calculation_type = (
        posted_calculation_type
        if posted_calculation_type in ('market', 'trench')
        else (
            mortgage_form.data.get('CALCULATION_TYPE')
            if mortgage_form.is_bound
            else mortgage_form.initial.get('CALCULATION_TYPE', 'market')
        )
    )
    if active_calculation_type not in ('market', 'trench'):
        active_calculation_type = 'market'
    trench_count = _resolve_trench_count(mortgage_form)
    trench_default_rate = _resolve_trench_default_rate(mortgage_form)
    can_save_calculations = request.user.is_authenticated

    context = {
        'mortgage_form': mortgage_form,
        'target_customer': target_customer,
        'sample_calculation': sample_calculation,
        'property_form_data': _get_property_form_data(),
        'mortgage_program_form_data': _get_mortgage_program_form_data(),
        'active_calculation_type': active_calculation_type,
        'trench_count': trench_count,
        'trench_input_rows': _build_trench_input_rows(
            trench_count=trench_count,
            post_data=mortgage_form.data if mortgage_form.is_bound else None,
            default_annual_rate=trench_default_rate,
        ),
        'can_save_calculations': can_save_calculations,
    }

    if request.method == 'POST':
        if 'calculate' in request.POST:
            if mortgage_form.is_valid():
                # Получаем данные из формы
                data = mortgage_form.cleaned_data
                selected_calculation_type = request.POST.get('calculate')
                if selected_calculation_type not in ('market', 'trench'):
                    selected_calculation_type = (
                        data.get('CALCULATION_TYPE') or 'market'
                    )
                data['CALCULATION_TYPE'] = selected_calculation_type
                context['active_calculation_type'] = selected_calculation_type

                # Получаем выбранный объект недвижимости
                property_obj = data['PROPERTY']

                # Получаем базовую стоимость из скрытого поля
                base_property_cost = float(data['PROPERTY_COST'])

                (
                    discount_markup_value,
                    discount_markup_rubles,
                    final_property_cost,
                ) = _normalize_discount_markup_values(data)
                (
                    initial_payment_percent,
                    initial_payment_rubles,
                ) = _normalize_initial_payment_values(
                    data, final_property_cost
                )

                # Создаем экземпляр калькулятора.
                # Все значения преобразуем к float.
                if data.get('CALCULATION_TYPE') == 'trench':
                    trench_mortgage_data, prep_errors = (
                        _prepare_trench_mortgage_data(data)
                    )
                    trench_entries, input_rows, trench_errors = (
                        _parse_trench_inputs(
                            post_data=request.POST,
                            trench_count=trench_mortgage_data[
                                'trench_count'
                            ],
                            loan_amount=trench_mortgage_data[
                                'total_loan_amount'
                            ],
                            default_annual_rate=trench_mortgage_data[
                                'annual_rate'
                            ],
                        )
                    )
                    context['trench_input_rows'] = input_rows
                    all_errors = prep_errors + trench_errors
                    if all_errors:
                        context['error_message'] = ' '.join(all_errors)
                        context['active_calculation_type'] = 'trench'
                        return render(
                            request,
                            'mortgage/mortgage_form.html',
                            context,
                        )

                    trench_calculation, calc_errors = (
                        _calculate_trench_mortgage(
                            trench_mortgage_data,
                            trench_entries,
                        )
                    )
                    if calc_errors:
                        context['error_message'] = ' '.join(calc_errors)
                        context['active_calculation_type'] = 'trench'
                        return render(
                            request,
                            'mortgage/mortgage_form.html',
                            context,
                        )

                    should_save_calculation = (
                        _can_save_calculation_for_property(
                            request,
                            property_obj,
                            mortgage_form,
                        )
                    )
                    if should_save_calculation:
                        calculation_owner = _get_calculation_owner(
                            request,
                            target_customer,
                        )
                        with transaction.atomic():
                            if property_obj is None:
                                property_obj = _create_manual_property(
                                    data,
                                    base_property_cost,
                                )
                            trench_calculation['property_obj'] = property_obj
                            saved_trench_calculation = (
                                _save_trench_calculation(
                                    trench_calculation,
                                    user=calculation_owner,
                                )
                            )
                            _attach_trench_calculation_to_customer(
                                target_customer,
                                saved_trench_calculation,
                            )

                    context['trench_result'] = _format_trench_result(
                        trench_calculation
                    )
                    context['trench_payment_schedule'] = (
                        _format_trench_payment_schedule(
                            trench_calculation['payment_schedule']
                        )
                    )
                    context['can_export_trench_result'] = True
                    context['active_calculation_type'] = 'trench'
                    context['final_property_cost'] = format_currency(
                        final_property_cost
                    )
                    context['discount_markup_type'] = data[
                        'DISCOUNT_MARKUP_TYPE'
                    ]
                    context['discount_markup_value'] = discount_markup_value
                    context['discount_markup_rubles'] = discount_markup_rubles
                    context['selected_property'] = property_obj
                    context['initial_payment_percent'] = (
                        initial_payment_percent
                    )
                    context['initial_payment_rubles'] = initial_payment_rubles
                    _populate_market_report_context(
                        context,
                        data,
                        final_property_cost,
                        initial_payment_percent,
                    )
                    context['active_calculation_type'] = 'trench'
                    context['mortgage_form'] = mortgage_form
                    return render(
                        request,
                        'mortgage/mortgage_form.html',
                        context,
                    )

                calculator = MortgageCalculator(
                    property_cost=float(final_property_cost),
                    initial_payment_percent=float(initial_payment_percent),
                    initial_payment_date=data['INITIAL_PAYMENT_DATE'],
                    mortgage_term=int(data['MORTGAGE_TERM']),
                    annual_rate=float(data['ANNUAL_RATE']),
                    has_grace_period=data['HAS_GRACE_PERIOD'] == 'yes',
                    grace_period_term=int(data['GRACE_PERIOD_TERM'] or 0),
                    grace_period_rate=float(data['GRACE_PERIOD_RATE'] or 0),
                )

                # Выполняем расчет
                result = calculator.calculate()

                # Форматируем числовые значения для отображения
                formatted_result = {}
                for key, value in result.items():
                    if key in ['grace_payments_count', 'main_payments_count']:
                        # Целые числа
                        formatted_result[key] = int(value) if value else 0
                    elif isinstance(value, (int, float, decimal.Decimal)):
                        # Денежные значения
                        formatted_result[key] = format_currency(value)
                    else:
                        formatted_result[key] = value

                # Получаем график платежей
                payment_schedule = calculator.get_payment_schedule()

                # Форматируем числовые значения в графике платежей
                for payment in payment_schedule:
                    for key in [
                        'payment_amount',
                        'interest_amount',
                        'principal_amount',
                        'remaining_debt',
                    ]:
                        if key in payment:
                            payment[key] = format_currency(payment[key])

                calculation = None
                should_save_calculation = (
                    _can_save_calculation_for_property(
                        request,
                        property_obj,
                        mortgage_form,
                    )
                )
                if should_save_calculation:
                    calculation_owner = _get_calculation_owner(
                        request,
                        target_customer,
                    )
                    calculation_values = {
                        'base_property_cost': base_property_cost,
                        'initial_payment_percent': initial_payment_percent,
                        'discount_markup_value': discount_markup_value,
                        'final_property_cost': final_property_cost,
                    }
                    with transaction.atomic():
                        if property_obj is None:
                            property_obj = _create_manual_property(
                                data,
                                base_property_cost,
                            )
                        calculation = _build_calculation(
                            property_obj,
                            data,
                            result,
                            calculation_values,
                            user=calculation_owner,
                        )
                        calculation.save()
                        _attach_calculation_to_customer(
                            target_customer,
                            calculation,
                        )

                    if target_customer is not None:
                        messages.success(
                            request,
                            'Расчет сохранен и привязан к клиенту.',
                        )

                # Сохраняем расчет в контекст
                context['result'] = formatted_result
                context['market_result'] = formatted_result
                context['has_grace_period'] = data['HAS_GRACE_PERIOD'] == 'yes'
                context['payment_schedule'] = payment_schedule
                context['market_payment_schedule'] = payment_schedule
                context['active_calculation_type'] = 'market'
                context['final_property_cost'] = format_currency(
                    final_property_cost
                )
                context['discount_markup_type'] = data['DISCOUNT_MARKUP_TYPE']
                context['discount_markup_value'] = discount_markup_value
                context['discount_markup_rubles'] = discount_markup_rubles
                context['selected_property'] = property_obj
                context['initial_payment_percent'] = initial_payment_percent
                context['initial_payment_rubles'] = initial_payment_rubles

                # Передаем заполненную форму в контекст
                _populate_trench_report_context(
                    context,
                    request,
                    data,
                    property_obj,
                    report_errors=False,
                )
                context['active_calculation_type'] = 'market'
                context['mortgage_form'] = mortgage_form

        elif 'export' in request.POST or 'export_word' in request.POST:
            # Аналогичные изменения для блока экспорта
            if mortgage_form.is_valid():
                # Получаем данные из формы
                mortgage_data = mortgage_form.cleaned_data
                export_format = (
                    'word' if 'export_word' in request.POST else 'excel'
                )
                selected_export_type = (
                    request.POST.get('export')
                    or request.POST.get('export_word')
                )
                if selected_export_type not in ('market', 'trench'):
                    selected_export_type = (
                        mortgage_data.get('CALCULATION_TYPE') or 'market'
                    )
                mortgage_data['CALCULATION_TYPE'] = selected_export_type
                context['active_calculation_type'] = selected_export_type

                # Получаем выбранный объект недвижимости
                property_obj = mortgage_data['PROPERTY']

                # Получаем стоимость из формы и преобразуем в float
                property_cost = float(mortgage_data['PROPERTY_COST'])

                (
                    discount_markup_value,
                    discount_markup_rubles,
                    final_property_cost,
                ) = _normalize_discount_markup_values(mortgage_data)
                (
                    initial_payment_percent,
                    initial_payment_rubles,
                ) = _normalize_initial_payment_values(
                    mortgage_data, final_property_cost
                )

                # Создаем экземпляр калькулятора.
                # Все значения преобразуем к float.
                if mortgage_data.get('CALCULATION_TYPE') == 'trench':
                    trench_mortgage_data, prep_errors = (
                        _prepare_trench_mortgage_data(mortgage_data)
                    )
                    trench_entries, input_rows, trench_errors = (
                        _parse_trench_inputs(
                            post_data=request.POST,
                            trench_count=(
                                trench_mortgage_data['trench_count']
                            ),
                            loan_amount=(
                                trench_mortgage_data['total_loan_amount']
                            ),
                            default_annual_rate=(
                                trench_mortgage_data['annual_rate']
                            ),
                        )
                    )
                    context['trench_input_rows'] = input_rows
                    all_errors = prep_errors + trench_errors
                    if all_errors:
                        context['error_message'] = ' '.join(all_errors)
                        context['active_calculation_type'] = 'trench'
                        return render(
                            request,
                            'mortgage/mortgage_form.html',
                            context,
                        )

                    trench_calculation, calc_errors = (
                        _calculate_trench_mortgage(
                            trench_mortgage_data,
                            trench_entries,
                        )
                    )
                    if calc_errors:
                        context['error_message'] = ' '.join(calc_errors)
                        context['active_calculation_type'] = 'trench'
                        return render(
                            request,
                            'mortgage/mortgage_form.html',
                            context,
                        )
                    trench_calculation['property_obj'] = property_obj
                    if export_format == 'word':
                        return export_trench_mortgage_word(
                            trench_calculation
                        )
                    return _export_trench_excel(trench_calculation)
                calculator = MortgageCalculator(
                    property_cost=float(final_property_cost),
                    initial_payment_percent=float(initial_payment_percent),
                    initial_payment_date=mortgage_data['INITIAL_PAYMENT_DATE'],
                    mortgage_term=int(mortgage_data['MORTGAGE_TERM']),
                    annual_rate=float(mortgage_data['ANNUAL_RATE']),
                    has_grace_period=mortgage_data['HAS_GRACE_PERIOD']
                    == 'yes',
                    grace_period_term=int(
                        mortgage_data['GRACE_PERIOD_TERM'] or 0
                    ),
                    grace_period_rate=float(
                        mortgage_data['GRACE_PERIOD_RATE'] or 0
                    ),
                )

                # Выполняем расчет
                result = calculator.calculate()
                payment_schedule = calculator.get_payment_schedule()

                report_data = MortgageExcelData(
                    property_obj=property_obj,
                    mortgage_data=mortgage_data,
                    property_cost=property_cost,
                    discount_markup_value=discount_markup_value,
                    discount_markup_rubles=discount_markup_rubles,
                    final_property_cost=final_property_cost,
                    initial_payment_percent=initial_payment_percent,
                    result=result,
                    payment_schedule=payment_schedule,
                    has_manual_property_data=(
                        mortgage_form.has_manual_property_data()
                    ),
                )
                if export_format == 'word':
                    return export_mortgage_word(report_data)
                return export_mortgage_excel(report_data)

    return render(request, 'mortgage/mortgage_form.html', context)


@require_GET
def property_cost_api(request, pk):
    """Описание метода property_cost_api.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        request: Входной параметр, влияющий на работу метода.
        pk: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    property_obj = get_object_or_404(
        Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex__district__city',
            'building',
            'layout',
            'decoration',
        ),
        pk=pk,
    )
    return JsonResponse(_get_property_payload(property_obj))


@login_required
def calculation_list(request):
    """Список всех расчетов"""
    target_customer = _get_target_customer(request)

    if request.method == 'POST' and target_customer is not None:
        selected_ids = request.POST.getlist('calculations')
        calculations = _filter_private_queryset_for_user(
            MortgageCalculation.objects.filter(pk__in=selected_ids),
            request.user,
        )

        _attach_calculations_to_customer(target_customer, calculations)

        if selected_ids:
            messages.success(
                request,
                'Выбранные расчеты добавлены в карточку клиента.',
            )
        else:
            messages.info(request, 'Расчеты для добавления не выбраны.')
        return redirect('customer:detail', pk=target_customer.pk)

    calculation_filters = get_calculation_filters(request)
    calculation_sort, calculation_order = get_calculation_sort(request)
    calculations = _filter_private_queryset_for_user(
        MortgageCalculation.objects.select_related(
            'property',
            'property__layout',
            'property__building',
            'property__building__real_estate_complex',
            'property__building__real_estate_complex__district',
            'property__building__real_estate_complex__district__city',
        ),
        request.user,
    )
    calculation_cities = get_calculation_city_choices(calculations)
    calculations = apply_calculation_filters(
        annotate_calculation_table_values(calculations), calculation_filters
    )
    calculations = apply_calculation_sort(
        calculations, calculation_sort, calculation_order
    )
    page_obj = Paginator(
        calculations, CALCULATION_LIST_PAGE_SIZE
    ).get_page(request.GET.get('page'))
    linked_calculation_ids = []
    if target_customer is not None:
        linked_calculation_ids = list(
            target_customer.saved_calculations.values_list('pk', flat=True)
        )
    calculation_filter_reset_url = request.path
    if target_customer is not None:
        calculation_filter_reset_url = (
            f'{request.path}?customer={target_customer.pk}'
        )

    return render(
        request,
        'mortgage/mortgage_list.html',
        {
            'calculations': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.paginator.num_pages > 1,
            'pagination_querystring': _build_pagination_querystring(request),
            'target_customer': target_customer,
            'linked_calculation_ids': linked_calculation_ids,
            'calculation_filters': calculation_filters,
            'calculation_cities': calculation_cities,
            'calculation_sort': calculation_sort,
            'calculation_order': calculation_order,
            'calculation_filter_reset_url': calculation_filter_reset_url,
            'calculation_table_headers': build_calculation_table_headers(
                request,
                excluded_fields=('timestamp',),
            ),
        },
    )


@require_POST
@login_required
def calculation_delete(request, pk):
    """Удаление сохраненного ипотечного расчета."""
    calculation = get_object_or_404(
        _filter_private_queryset_for_user(
            MortgageCalculation.objects.all(),
            request.user,
        ),
        pk=pk,
    )
    calculation.delete()
    return redirect('mortgage:calculation_list')


@login_required
def calculation_detail(request, pk):
    """Детальная информация о расчете"""
    calculation_queryset = MortgageCalculation.objects.select_related(
        'property',
        'property__layout',
        'property__building',
        'property__building__real_estate_complex',
        'property__building__real_estate_complex__developer__company_group',
        'property__building__real_estate_complex__district',
        'property__building__real_estate_complex__district__city',
        'property__building__real_estate_complex__real_estate_class',
    )
    calculation = get_object_or_404(
        _filter_private_queryset_for_user(calculation_queryset, request.user),
        pk=pk,
    )
    calculator = MortgageCalculator(
        property_cost=float(calculation.final_property_cost),
        initial_payment_percent=float(calculation.initial_payment_percent),
        initial_payment_date=calculation.initial_payment_date,
        mortgage_term=int(calculation.mortgage_term),
        annual_rate=float(calculation.annual_rate),
        has_grace_period=calculation.has_grace_period,
        grace_period_term=int(calculation.grace_period_term or 0),
        grace_period_rate=float(calculation.grace_period_rate or 0),
    )
    payment_schedule = calculator.get_payment_schedule()

    if request.method == 'POST' and request.POST.get('export') == 'market':
        return export_saved_mortgage_calculation_excel(
            calculation, payment_schedule
        )
    if (
        request.method == 'POST'
        and request.POST.get('export_word') == 'market'
    ):
        return export_saved_mortgage_calculation_word(
            calculation,
            payment_schedule,
        )

    return render(
        request,
        'mortgage/mortgage_detail.html',
        {
            'calculation': calculation,
            'payment_schedule': payment_schedule,
        },
    )



def _get_trench_calculation_queryset(user=None):
    """Return trench mortgage calculations with related objects loaded."""
    queryset = TrenchMortgageCalculation.objects.select_related(
        'property',
        'property__layout',
        'property__decoration',
        'property__building',
        'property__building__real_estate_complex',
        'property__building__real_estate_complex__developer__company_group',
        'property__building__real_estate_complex__district',
        'property__building__real_estate_complex__district__city',
        'property__building__real_estate_complex__real_estate_class',
    ).prefetch_related('trenches')
    if user is None:
        return queryset
    return _filter_private_queryset_for_user(queryset, user)


def _annotate_trench_calculation_table_values(queryset):
    """Annotate trench calculations for the saved calculations table."""
    last_trench_monthly_payment = (
        Trench.objects.filter(calculation=OuterRef('pk'))
        .order_by('-trench_number', '-pk')
        .values('monthly_payment')[:1]
    )
    return annotate_calculation_table_values(queryset).annotate(
        main_monthly_payment=Subquery(
            last_trench_monthly_payment,
            output_field=DecimalField(max_digits=15, decimal_places=2),
        )
    )


def _build_saved_trench_calculation_data(calculation):
    """Build an export/report payload from a saved trench calculation."""
    trenches = []
    previous_monthly_payment = 0.0
    mortgage_end_date = calculation.initial_payment_date + relativedelta(
        months=calculation.mortgage_term
    )
    for trench in calculation.trenches.all():
        monthly_payment = float(trench.monthly_payment)
        trench_monthly_payment = monthly_payment - previous_monthly_payment
        previous_monthly_payment = monthly_payment
        months_remaining = _calculate_months_remaining(
            trench.trench_date, mortgage_end_date
        )
        overpayment = _calculate_trench_overpayment(
            trench_monthly_payment,
            float(trench.trench_amount),
            months_remaining,
        )
        trenches.append(
            {
                'number': trench.trench_number,
                'date': trench.trench_date,
                'percent': float(trench.trench_percent),
                'amount': float(trench.trench_amount),
                'annual_rate': float(trench.annual_rate),
                'trench_monthly_payment': trench_monthly_payment,
                'monthly_payment': monthly_payment,
                'payments_count': trench.payments_count,
                'remaining_debt': float(trench.remaining_debt),
                'overpayment': overpayment,
            }
        )

    return {
        'property_obj': calculation.property,
        'property_cost': float(calculation.final_property_cost),
        'base_property_cost': float(calculation.base_property_cost),
        'discount_markup_type': calculation.discount_markup_type,
        'discount_markup_value': float(calculation.discount_markup_value),
        'final_property_cost': float(calculation.final_property_cost),
        'initial_payment_percent': float(calculation.initial_payment_percent),
        'initial_payment': float(calculation.initial_payment_amount),
        'initial_payment_date': calculation.initial_payment_date,
        'mortgage_term': calculation.mortgage_term,
        'mortgage_end_date': mortgage_end_date,
        'annual_rate': float(calculation.annual_rate),
        'trench_count': calculation.trench_count,
        'total_loan_amount': float(calculation.total_loan_amount),
        'total_overpayment': float(calculation.total_overpayment),
        'trenches': trenches,
        'payment_schedule': _build_trench_payment_schedule(
            trenches, mortgage_end_date
        ),
    }


@login_required
def trench_calculation_list(request):
    """Show saved trench mortgage calculations."""
    target_customer = _get_target_customer(request)

    if request.method == 'POST' and target_customer is not None:
        selected_ids = request.POST.getlist('calculations')
        calculations = _get_trench_calculation_queryset(request.user).filter(
            pk__in=selected_ids
        )

        _attach_trench_calculations_to_customer(
            target_customer, calculations
        )

        if selected_ids:
            messages.success(
                request,
                'Выбранные траншевые расчеты добавлены в карточку клиента.',
            )
        else:
            messages.info(
                request,
                'Траншевые расчеты для добавления не выбраны.',
            )
        return redirect('customer:detail', pk=target_customer.pk)

    calculation_filters = get_calculation_filters(request)
    calculation_sort, calculation_order = get_calculation_sort(request)
    calculations = _get_trench_calculation_queryset(request.user)
    calculation_cities = get_calculation_city_choices(calculations)
    calculations = apply_calculation_filters(
        _annotate_trench_calculation_table_values(calculations),
        calculation_filters,
    )
    calculations = apply_calculation_sort(
        calculations, calculation_sort, calculation_order
    )
    page_obj = Paginator(
        calculations, CALCULATION_LIST_PAGE_SIZE
    ).get_page(request.GET.get('page'))
    linked_calculation_ids = []
    if target_customer is not None:
        linked_calculation_ids = list(
            target_customer.saved_trench_calculations.values_list(
                'pk', flat=True
            )
        )
    calculation_filter_reset_url = request.path
    if target_customer is not None:
        calculation_filter_reset_url = (
            f'{request.path}?customer={target_customer.pk}'
        )

    return render(
        request,
        'mortgage/trench_calculation_list.html',
        {
            'calculations': page_obj.object_list,
            'page_obj': page_obj,
            'is_paginated': page_obj.paginator.num_pages > 1,
            'pagination_querystring': _build_pagination_querystring(request),
            'target_customer': target_customer,
            'linked_calculation_ids': linked_calculation_ids,
            'calculation_filters': calculation_filters,
            'calculation_cities': calculation_cities,
            'calculation_sort': calculation_sort,
            'calculation_order': calculation_order,
            'calculation_filter_reset_url': calculation_filter_reset_url,
            'calculation_table_headers': build_calculation_table_headers(
                request,
                excluded_fields=('timestamp',),
            ),
        },
    )


@require_POST
@login_required
def trench_calculation_delete(request, pk):
    """Delete a saved trench mortgage calculation."""
    calculation = get_object_or_404(
        _get_trench_calculation_queryset(request.user),
        pk=pk,
    )
    calculation.delete()
    return redirect('mortgage:trench_calculation_list')


@login_required
def trench_calculation_detail(request, pk):
    """Show detailed information about a saved trench mortgage calculation."""
    calculation = get_object_or_404(
        _get_trench_calculation_queryset(request.user),
        pk=pk,
    )
    calculation_data = _build_saved_trench_calculation_data(calculation)

    if request.method == 'POST' and request.POST.get('export') == 'trench':
        return _export_trench_excel(calculation_data)
    if (
        request.method == 'POST'
        and request.POST.get('export_word') == 'trench'
    ):
        return export_trench_mortgage_word(calculation_data)

    return render(
        request,
        'mortgage/trench_calculation_detail.html',
        {
            'calculation': calculation,
            'calculation_data': calculation_data,
            'trench_result': _format_trench_result(calculation_data),
            'payment_schedule': _format_trench_payment_schedule(
                calculation_data['payment_schedule']
            ),
        },
    )
