# mortgage/utils.py
from decimal import Decimal, InvalidOperation

from django.db.models import DecimalField, ExpressionWrapper, F, Q, Value


CALCULATION_SORT_FIELDS = {
    'timestamp': 'timestamp',
    'object': 'property__building__real_estate_complex__name',
    'cost': 'final_property_cost',
    'initial_payment': 'table_initial_payment_amount',
    'monthly_payment': 'main_monthly_payment',
    'term': 'mortgage_term',
    'rate': 'annual_rate',
}

CALCULATION_TABLE_HEADERS = (
    ('timestamp', 'Дата расчета'),
    ('object', 'Объект'),
    ('cost', 'Стоимость объекта'),
    ('initial_payment', 'Первоначальный взнос'),
    ('monthly_payment', 'Ежемесячный платеж'),
    ('term', 'Срок'),
    ('rate', 'Ставка'),
)


def _prefixed(field, prefix):
    if field == 'table_initial_payment_amount':
        return field
    return f'{prefix}{field}' if prefix else field


def annotate_calculation_table_values(queryset, prefix=''):
    return queryset.annotate(
        table_initial_payment_amount=ExpressionWrapper(
            F(_prefixed('final_property_cost', prefix))
            * F(_prefixed('initial_payment_percent', prefix))
            / Value(Decimal('100')),
            output_field=DecimalField(max_digits=15, decimal_places=2),
        )
    )


def _parse_decimal(value):
    if not value:
        return None
    try:
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None


def get_calculation_filters(request):
    return {
        'q': (request.GET.get('q') or '').strip(),
        'cost_from': (request.GET.get('cost_from') or '').strip(),
        'cost_to': (request.GET.get('cost_to') or '').strip(),
        'initial_payment_from': (
            request.GET.get('initial_payment_from') or ''
        ).strip(),
        'initial_payment_to': (
            request.GET.get('initial_payment_to') or ''
        ).strip(),
        'monthly_payment_from': (
            request.GET.get('monthly_payment_from') or ''
        ).strip(),
        'monthly_payment_to': (
            request.GET.get('monthly_payment_to') or ''
        ).strip(),
        'term_from': (request.GET.get('term_from') or '').strip(),
        'term_to': (request.GET.get('term_to') or '').strip(),
        'rate_from': (request.GET.get('rate_from') or '').strip(),
        'rate_to': (request.GET.get('rate_to') or '').strip(),
    }


def _apply_decimal_range(queryset, filters, prefix, field, filter_name):
    from_value = _parse_decimal(filters.get(f'{filter_name}_from'))
    if from_value is not None:
        queryset = queryset.filter(
            **{f'{_prefixed(field, prefix)}__gte': from_value}
        )

    to_value = _parse_decimal(filters.get(f'{filter_name}_to'))
    if to_value is not None:
        queryset = queryset.filter(
            **{f'{_prefixed(field, prefix)}__lte': to_value}
        )

    return queryset


def _apply_years_range(queryset, filters, prefix, field, filter_name):
    from_value = _parse_decimal(filters.get(f'{filter_name}_from'))
    if from_value is not None:
        queryset = queryset.filter(
            **{f'{_prefixed(field, prefix)}__gte': from_value * 12}
        )

    to_value = _parse_decimal(filters.get(f'{filter_name}_to'))
    if to_value is not None:
        queryset = queryset.filter(
            **{f'{_prefixed(field, prefix)}__lte': to_value * 12}
        )

    return queryset


def apply_calculation_filters(queryset, filters, prefix=''):
    search = filters.get('q')
    if search:
        queryset = queryset.filter(
            Q(
                **{
                    (
                        f'{_prefixed("property", prefix)}'
                        '__apartment_number__icontains'
                    ): search
                }
            )
            | Q(
                **{
                    (
                        f'{_prefixed("property", prefix)}__building'
                        '__real_estate_complex__name__icontains'
                    ): search
                }
            )
        )

    queryset = _apply_decimal_range(
        queryset, filters, prefix, 'final_property_cost', 'cost'
    )
    queryset = _apply_decimal_range(
        queryset,
        filters,
        prefix,
        'table_initial_payment_amount',
        'initial_payment',
    )
    queryset = _apply_decimal_range(
        queryset, filters, prefix, 'main_monthly_payment', 'monthly_payment'
    )
    queryset = _apply_years_range(
        queryset, filters, prefix, 'mortgage_term', 'term'
    )
    queryset = _apply_decimal_range(
        queryset, filters, prefix, 'annual_rate', 'rate'
    )

    return queryset


def get_calculation_sort(request):
    sort = request.GET.get('sort') or 'timestamp'
    if sort not in CALCULATION_SORT_FIELDS:
        sort = 'timestamp'

    order = request.GET.get('order') or 'desc'
    if order not in ('asc', 'desc'):
        order = 'desc'

    return sort, order


def apply_calculation_sort(queryset, sort, order, prefix=''):
    sort_field = _prefixed(CALCULATION_SORT_FIELDS[sort], prefix)
    if order == 'desc':
        sort_field = f'-{sort_field}'
    return queryset.order_by(sort_field)


def build_calculation_table_headers(request):
    current_sort, current_order = get_calculation_sort(request)
    headers = []

    for field, label in CALCULATION_TABLE_HEADERS:
        next_order = 'desc'
        indicator = ''
        if field == current_sort:
            next_order = 'desc' if current_order == 'asc' else 'asc'
            indicator = '↑' if current_order == 'asc' else '↓'

        query = request.GET.copy()
        query['sort'] = field
        query['order'] = next_order

        headers.append(
            {
                'field': field,
                'label': label,
                'url': f'?{query.urlencode()}',
                'is_active': field == current_sort,
                'indicator': indicator,
            }
        )

    return headers


def format_currency(value):
    """
    Форматирует число как валюту с разделителями разрядов и двумя
    десятичными знаками.
    """
    if value is None:
        return ''

    try:
        # Преобразуем в число
        num = float(value)
        # Форматируем с разделителями тысяч и двумя знаками после запятой
        return f'{num:,.2f}'.replace(',', ' ').replace('.', ',')
    except (ValueError, TypeError):
        return str(value)


def format_integer(value):
    """
    Форматирует целое число с разделителями разрядов
    """
    if value is None:
        return ''

    try:
        # Преобразуем в целое число
        num = int(value)
        # Форматируем с разделителями тысяч
        return f'{num:,}'.replace(',', ' ')
    except (ValueError, TypeError):
        return str(value)


def format_years_label(value):
    try:
        years = int(value)
    except (TypeError, ValueError):
        return ''

    remainder_100 = years % 100
    remainder_10 = years % 10
    if 11 <= remainder_100 <= 14:
        label = 'лет'
    elif remainder_10 == 1:
        label = 'год'
    elif 2 <= remainder_10 <= 4:
        label = 'года'
    else:
        label = 'лет'

    return f'{years} {label}'


def format_months_label(value):
    try:
        months = int(value)
    except (TypeError, ValueError):
        return ''

    remainder_100 = months % 100
    remainder_10 = months % 10
    if 11 <= remainder_100 <= 14:
        label = 'месяцев'
    elif remainder_10 == 1:
        label = 'месяц'
    elif 2 <= remainder_10 <= 4:
        label = 'месяца'
    else:
        label = 'месяцев'

    return f'{months} {label}'


def format_term_from_months(value):
    try:
        total_months = int(value)
    except (TypeError, ValueError):
        return ''

    years = total_months // 12
    months = total_months % 12
    parts = []

    if years:
        parts.append(format_years_label(years))
    if months:
        parts.append(format_months_label(months))

    return ' '.join(parts) if parts else format_months_label(0)
