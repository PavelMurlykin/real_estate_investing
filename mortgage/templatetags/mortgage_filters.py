from django import template

from mortgage.utils import (
    format_currency,
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
def term_from_months(value):
    return format_term_from_months(value)
