from django import template

register = template.Library()

@register.filter
def get_range(value):
    """
    Фильтр для создания диапазона чисел в шаблоне
    Использование: {% for i in 5|get_range %}
    """
    return range(value)