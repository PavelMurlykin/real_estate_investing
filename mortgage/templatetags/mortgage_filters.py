from django import template

from mortgage.utils import (
    format_currency,
    format_compact_decimal,
    format_term_from_months,
    format_years_label,
)

register = template.Library()


@register.filter
def currency(value):
    return format_currency(value)


@register.filter
def years_label_from_months(value):
    try:
        months = int(value)
    except (TypeError, ValueError):
        return ''

    return format_years_label(months // 12)


@register.filter
def mortgage_years(value):
    """Возвращает количество полных лет из срока в месяцах."""
    try:
        months = int(value)
    except (TypeError, ValueError):
        return ''
    return months // 12


@register.filter
def term_from_months(value):
    return format_term_from_months(value)


@register.filter
def compact_decimal(value):
    """Возвращает число без незначащих нулей после запятой."""
    return format_compact_decimal(value)


@register.filter
def compact_currency(value):
    """Возвращает денежное значение без копеек, когда они равны нулю."""
    formatted_value = format_currency(value)
    if formatted_value.endswith(',00'):
        return formatted_value[:-3]
    return formatted_value


@register.filter
def discount_markup_amount(calculation):
    """Возвращает сумму скидки или удорожания для расчета."""
    return abs(
        calculation.final_property_cost - calculation.base_property_cost
    )


@register.filter
def discount_markup_label(calculation):
    """Возвращает подпись корректировки стоимости объекта."""
    if calculation.discount_markup_type == 'markup':
        return 'Удорожание'
    return 'Скидка'


@register.simple_tag
def calculation_detail_table(calculation):
    """Return rows, dynamic column widths, and layout image for details."""
    rubles = '\u0440\u0443\u0431.'
    months = '\u043c\u0435\u0441.'
    grace_period_labels = (
        '\u0421\u0440\u043e\u043a \u043b\u044c\u0433\u043e\u0442\u043d\u043e\u0433\u043e \u043f\u0435\u0440\u0438\u043e\u0434\u0430',
        '\u0413\u043e\u0434\u043e\u0432\u0430\u044f \u0441\u0442\u0430\u0432\u043a\u0430 \u0432 \u043b\u044c\u0433\u043e\u0442\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434',
        '\u0421\u0443\u043c\u043c\u0430 \u043b\u044c\u0433\u043e\u0442\u043d\u043e\u0433\u043e \u043f\u043b\u0430\u0442\u0435\u0436\u0430',
    )

    def years_text(month_count):
        try:
            years = int(month_count) // 12
        except (TypeError, ValueError):
            return ''

        remainder_100 = years % 100
        remainder_10 = years % 10
        if 11 <= remainder_100 <= 14:
            label = '\u043b\u0435\u0442'
        elif remainder_10 == 1:
            label = '\u0433\u043e\u0434'
        elif 2 <= remainder_10 <= 4:
            label = '\u0433\u043e\u0434\u0430'
        else:
            label = '\u043b\u0435\u0442'
        return f'{years} {label}'

    property_obj = calculation.property
    rows = [
        {
            'label': 'Планировка',
            'value': property_obj.layout.name,
        },
        {
            'label': 'Площадь',
            'value': compact_decimal(property_obj.area),
        },
        {
            'label': '\u0421\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c \u043e\u0431\u044a\u0435\u043a\u0442\u0430',
            'value': f'{compact_currency(calculation.base_property_cost)} {rubles}',
        },
        {
            'label': (
                '\u0423\u0434\u043e\u0440\u043e\u0436\u0430\u043d\u0438\u0435'
                if calculation.discount_markup_type == 'markup'
                else '\u0421\u043a\u0438\u0434\u043a\u0430'
            ),
            'value': (
                f'{compact_currency(discount_markup_amount(calculation))} '
                f'{rubles} ({compact_decimal(calculation.discount_markup_value)} %)'
            ),
        },
        {
            'label': '\u0418\u0442\u043e\u0433\u043e\u0432\u0430\u044f \u0441\u0442\u043e\u0438\u043c\u043e\u0441\u0442\u044c \u043e\u0431\u044a\u0435\u043a\u0442\u0430',
            'value': f'{compact_currency(calculation.final_property_cost)} {rubles}',
        },
        {
            'label': '\u041f\u0435\u0440\u0432\u043e\u043d\u0430\u0447\u0430\u043b\u044c\u043d\u044b\u0439 \u0432\u0437\u043d\u043e\u0441',
            'value': (
                f'{compact_currency(calculation.initial_payment_amount)} '
                f'{rubles} ({compact_decimal(calculation.initial_payment_percent)} %)'
            ),
        },
        {
            'label': '\u0421\u0440\u043e\u043a \u0438\u043f\u043e\u0442\u0435\u043a\u0438',
            'value': f'{years_text(calculation.mortgage_term)} ({calculation.mortgage_term} {months})',
        },
        {
            'label': '\u0413\u043e\u0434\u043e\u0432\u0430\u044f \u0441\u0442\u0430\u0432\u043a\u0430',
            'value': f'{compact_decimal(calculation.annual_rate)} %',
        },
        {
            'label': '\u0421\u0443\u043c\u043c\u0430 \u0435\u0436\u0435\u043c\u0435\u0441\u044f\u0447\u043d\u043e\u0433\u043e \u043f\u043b\u0430\u0442\u0435\u0436\u0430',
            'value': f'{compact_currency(calculation.main_monthly_payment)} {rubles}',
        },
    ]

    if calculation.has_grace_period:
        rows.extend(
            [
                {
                    'label': '\u0421\u0440\u043e\u043a \u043b\u044c\u0433\u043e\u0442\u043d\u043e\u0433\u043e \u043f\u0435\u0440\u0438\u043e\u0434\u0430',
                    'value': f'{years_text(calculation.grace_period_term)} ({calculation.grace_period_term} {months})',
                },
                {
                    'label': '\u0413\u043e\u0434\u043e\u0432\u0430\u044f \u0441\u0442\u0430\u0432\u043a\u0430 \u0432 \u043b\u044c\u0433\u043e\u0442\u043d\u044b\u0439 \u043f\u0435\u0440\u0438\u043e\u0434',
                    'value': f'{compact_decimal(calculation.grace_period_rate)} %',
                },
                {
                    'label': '\u0421\u0443\u043c\u043c\u0430 \u043b\u044c\u0433\u043e\u0442\u043d\u043e\u0433\u043e \u043f\u043b\u0430\u0442\u0435\u0436\u0430',
                    'value': f'{compact_currency(calculation.grace_monthly_payment)} {rubles}',
                },
            ]
        )

    return {
        'rows': rows,
        'label_width': max(
            max(len(row['label']) for row in rows),
            max(len(label) for label in grace_period_labels),
        ) + 4,
        'value_width': max(len(row['value']) for row in rows) + 4,
        'layout_image': calculation.property.layout_image,
    }
