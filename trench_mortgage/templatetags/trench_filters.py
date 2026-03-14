from django import template

register = template.Library()


@register.filter
def get_range(value):
    """Описание метода get_range.

    Возвращает подготовленные данные для дальнейшей обработки.

    Аргументы:
        value: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата зависит от контекста использования.
    """
    try:
        return range(int(value))
    except (TypeError, ValueError):
        return range(0)
