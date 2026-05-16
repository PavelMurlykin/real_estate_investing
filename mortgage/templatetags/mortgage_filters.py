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
