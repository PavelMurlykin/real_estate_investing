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