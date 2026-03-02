from django import template

register = template.Library()


@register.filter
def get_range(value):
    try:
        return range(int(value))
    except (TypeError, ValueError):
        return range(0)
