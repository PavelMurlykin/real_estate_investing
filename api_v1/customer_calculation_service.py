from decimal import Decimal, ROUND_HALF_UP

from django.db.models import (
    CharField,
    DecimalField,
    ExpressionWrapper,
    F,
    IntegerField,
    OuterRef,
    Q,
    Subquery,
    Value,
)

from customer.models import CustomerCalculation, CustomerTrenchCalculation
from trench_mortgage.models import Trench
from users.roles import can_view_all_private_records


MONEY_QUANTUM = Decimal('0.01')
PERCENT_QUANTUM = Decimal('0.01')
CUSTOMER_CALCULATION_VALUE_FIELDS = (
    'linkId',
    'calculationId',
    'programType',
    'createdAt',
    'propertyId',
    'city',
    'realEstateComplex',
    'building',
    'apartmentNumber',
    'finalPropertyCost',
    'initialPaymentRubles',
    'monthlyPayment',
    'mortgageTermMonths',
    'annualRate',
    'trenchCount',
)


def _format_decimal(value, quantum=MONEY_QUANTUM):
    """Return a stable decimal string for the React API contract."""
    if value is None:
        return None
    decimal_value = Decimal(str(value)).quantize(
        quantum,
        rounding=ROUND_HALF_UP,
    )
    return format(decimal_value, 'f')


def _initial_payment_expression():
    """Return a database expression for the initial payment in rubles."""
    return ExpressionWrapper(
        F('calculation__final_property_cost')
        * F('calculation__initial_payment_percent')
        / Value(Decimal('100')),
        output_field=DecimalField(max_digits=15, decimal_places=2),
    )


def _filter_link_queryset(queryset, user, search):
    """Scope links by owner and apply a case-insensitive object search."""
    if not can_view_all_private_records(user):
        queryset = queryset.filter(calculation__user=user)
    if search:
        queryset = queryset.filter(
            Q(calculation__property__apartment_number__icontains=search)
            | Q(
                calculation__property__building__number__icontains=search
            )
            | Q(
                calculation__property__building__real_estate_complex__name__icontains=(
                    search
                )
            )
            | Q(
                calculation__property__building__real_estate_complex__district__city__name__icontains=(
                    search
                )
            )
        )
    return queryset


def _annotate_link_values(
    queryset,
    program_type,
    monthly_payment_expression,
    trench_count_expression,
):
    """Normalize one mortgage program queryset for a database union."""
    return queryset.annotate(
        linkId=F('pk'),
        calculationId=F('calculation_id'),
        programType=Value(program_type, output_field=CharField()),
        createdAt=F('calculation__timestamp'),
        propertyId=F('calculation__property_id'),
        city=F(
            'calculation__property__building__real_estate_complex'
            '__district__city__name'
        ),
        realEstateComplex=F(
            'calculation__property__building__real_estate_complex__name'
        ),
        building=F('calculation__property__building__number'),
        apartmentNumber=F('calculation__property__apartment_number'),
        finalPropertyCost=F('calculation__final_property_cost'),
        initialPaymentRubles=_initial_payment_expression(),
        monthlyPayment=monthly_payment_expression,
        mortgageTermMonths=F('calculation__mortgage_term'),
        annualRate=F('calculation__annual_rate'),
        trenchCount=trench_count_expression,
    ).values(*CUSTOMER_CALCULATION_VALUE_FIELDS)


def build_customer_calculation_queryset(customer, user, filters):
    """Return a filterable union of a customer's two calculation types."""
    search = filters.get('q', '')
    market_links = _filter_link_queryset(
        CustomerCalculation.objects.filter(customer=customer),
        user,
        search,
    )
    trench_links = _filter_link_queryset(
        CustomerTrenchCalculation.objects.filter(customer=customer),
        user,
        search,
    )
    last_trench_monthly_payment = (
        Trench.objects.filter(calculation_id=OuterRef('calculation_id'))
        .order_by('-trench_number', '-pk')
        .values('monthly_payment')[:1]
    )
    market_values = _annotate_link_values(
        market_links,
        'market',
        F('calculation__main_monthly_payment'),
        Value(1, output_field=IntegerField()),
    )
    trench_values = _annotate_link_values(
        trench_links,
        'trench',
        Subquery(
            last_trench_monthly_payment,
            output_field=DecimalField(max_digits=15, decimal_places=2),
        ),
        F('calculation__trench_count'),
    )

    program_type = filters['programType']
    if program_type == 'market':
        queryset = market_values
    elif program_type == 'trench':
        queryset = trench_values
    else:
        queryset = market_values.union(trench_values, all=True)

    ordering = filters['ordering']
    ordering_fields = [ordering]
    if ordering.removeprefix('-') != 'createdAt':
        ordering_fields.append('-createdAt')
    ordering_fields.extend(('-linkId', 'programType'))
    return queryset.order_by(*ordering_fields)


def serialize_customer_calculation_link(row):
    """Serialize one normalized linked-calculation row."""
    return {
        'linkId': row['linkId'],
        'calculationId': row['calculationId'],
        'programType': row['programType'],
        'createdAt': row['createdAt'].isoformat(),
        'property': {
            'id': row['propertyId'],
            'city': row['city'],
            'realEstateComplex': row['realEstateComplex'],
            'building': row['building'],
            'apartmentNumber': row['apartmentNumber'],
        },
        'finalPropertyCost': _format_decimal(row['finalPropertyCost']),
        'initialPaymentRubles': _format_decimal(
            row['initialPaymentRubles']
        ),
        'monthlyPayment': _format_decimal(row['monthlyPayment']),
        'mortgageTermMonths': row['mortgageTermMonths'],
        'annualRate': _format_decimal(
            row['annualRate'],
            PERCENT_QUANTUM,
        ),
        'trenchCount': row['trenchCount'],
    }
