def format_currency(value):
    """
    Форматирует число как валюту с разделителями разрядов и двумя десятичными знаками
    """
    if value is None:
        return ""

    try:
        # Преобразуем в число
        num = float(value)
        # Форматируем с разделителями тысяч и двумя знаками после запятой
        return f"{num:,.2f}".replace(",", " ").replace(".", ",")
    except (ValueError, TypeError):
        return str(value)


def format_integer(value):
    """
    Форматирует целое число с разделителями разрядов
    """
    if value is None:
        return ""

    try:
        # Преобразуем в целое число
        num = int(value)
        # Форматируем с разделителями тысяч
        return f"{num:,}".replace(",", " ")
    except (ValueError, TypeError):
        return str(value)
