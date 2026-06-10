from decimal import Decimal, InvalidOperation

from django import forms


def normalize_grouped_decimal_value(value):
    """Return a decimal string without visual thousand separators."""
    if isinstance(value, str):
        return (
            value.replace('\xa0', '')
            .replace(' ', '')
            .replace(',', '.')
        )
    return value


def format_grouped_decimal_value(value, decimal_places=2):
    """Format a decimal value with space groups and comma decimals."""
    if value in (None, ''):
        return ''

    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError):
        return str(value)

    quant = Decimal('1').scaleb(-decimal_places)
    decimal_value = decimal_value.quantize(quant)
    formatted_value = f'{decimal_value:,.{decimal_places}f}'
    return formatted_value.replace(',', ' ').replace('.', ',')


class GroupedDecimalInput(forms.TextInput):
    """Render decimal values with grouped thousands for user-facing forms."""

    input_type = 'text'

    def __init__(self, attrs=None, decimal_places=2):
        """Initialize the widget with mobile-friendly decimal input attrs."""
        default_attrs = {
            'autocomplete': 'off',
            'data-grouped-decimal-input': '',
            'inputmode': 'decimal',
        }
        if attrs:
            default_attrs.update(attrs)
        self.decimal_places = decimal_places
        super().__init__(attrs=default_attrs)

    def format_value(self, value):
        """Return a grouped decimal value for HTML rendering."""
        return format_grouped_decimal_value(
            value,
            decimal_places=self.decimal_places,
        )


class GroupedDecimalField(forms.DecimalField):
    """Accept grouped decimal input while preserving Decimal validation."""

    widget = GroupedDecimalInput

    def __init__(self, *args, **kwargs):
        """Initialize the field with a grouped decimal widget."""
        decimal_places = kwargs.get('decimal_places', 2)
        kwargs.setdefault(
            'widget',
            GroupedDecimalInput(decimal_places=decimal_places),
        )
        super().__init__(*args, **kwargs)

    def to_python(self, value):
        """Normalize grouped user input before Django decimal parsing."""
        normalized_value = normalize_grouped_decimal_value(value)
        return super().to_python(normalized_value)
