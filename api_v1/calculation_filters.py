from decimal import ROUND_CEILING, ROUND_FLOOR

from django.db.models import DecimalField, F, OuterRef, Subquery
from django.db.models.functions import Round

from mortgage.utils import annotate_calculation_table_values
from trench_mortgage.models import Trench


def apply_calculation_ranges(queryset, filters, fields):
    """Filter in PostgreSQL before pagination, with terms entered in years."""
    if filters.get('city'):
        queryset = queryset.filter(**{fields['city']: filters['city']})
    for name in ('cost', 'initialPayment', 'monthlyPayment', 'term', 'rate'):
        for suffix, lookup, rounding in (
            ('From', 'gte', ROUND_CEILING), ('To', 'lte', ROUND_FLOOR),
        ):
            value = filters.get(f'{name}{suffix}')
            if value is None:
                continue
            if name == 'term':
                value = (value * 12).to_integral_value(rounding=rounding)
            queryset = queryset.filter(**{f'{fields[name]}__{lookup}': value})
    return queryset


def filter_saved_calculations(queryset, filters, *, tranche=False):
    """Annotate the legacy down payment and last tranche payment once."""
    queryset = annotate_calculation_table_values(queryset)
    queryset = queryset.annotate(
        table_initial_payment_amount=Round(
            F('table_initial_payment_amount'), precision=2,
        )
    )
    if tranche:
        payments = Trench.objects.filter(calculation_id=OuterRef('pk'))
        money = DecimalField(max_digits=15, decimal_places=2)
        queryset = queryset.annotate(
            monthlyPayment=Subquery(
                payments.order_by('-trench_number', '-pk')
                .values('monthly_payment')[:1], output_field=money,
            ),
            maximumMonthlyPayment=Subquery(
                payments.order_by('-monthly_payment', '-pk')
                .values('monthly_payment')[:1], output_field=money,
            ),
        )
    else:
        queryset = queryset.annotate(monthlyPayment=F('main_monthly_payment'))
    return apply_calculation_ranges(queryset, filters, {
        'city': 'property__building__real_estate_complex__district__city_id',
        'cost': 'final_property_cost',
        'initialPayment': 'table_initial_payment_amount',
        'monthlyPayment': 'monthlyPayment', 'term': 'mortgage_term',
        'rate': 'annual_rate',
    })
