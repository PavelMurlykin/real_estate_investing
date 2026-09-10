from decimal import Decimal

from customer.models import Customer


def _format_optional_decimal(value):
    """Return a JSON-safe fixed-point string or null."""
    if value is None:
        return None
    return f'{Decimal(value):.2f}'


def build_customer_financial_capacity(customer, key_rate):
    """Calculate the financial indicators shown in a customer profile."""
    maximum_term_years = customer.get_max_mortgage_term_years()
    annual_rate = Decimal(key_rate) + Customer.RATE_MARGIN
    maximum_property_cost = customer.calculate_max_property_cost(
        annual_rate=annual_rate,
        max_term_years=maximum_term_years,
    )
    has_preferential_program = (
        customer.has_selected_preferential_program()
    )
    preferential_credit_limit = None
    preferential_maximum_property_cost = None
    if has_preferential_program:
        preferential_credit_limit = customer.get_preferential_credit_limit()
        preferential_maximum_property_cost = (
            customer.calculate_max_property_cost(
                annual_rate=Customer.DEFAULT_PREFERENTIAL_ANNUAL_RATE,
                max_term_years=maximum_term_years,
                credit_limit=preferential_credit_limit,
            )
        )

    return {
        'maximumTermYears': maximum_term_years,
        'actualKeyRate': _format_optional_decimal(key_rate),
        'annualRate': _format_optional_decimal(annual_rate),
        'maximumPropertyCost': _format_optional_decimal(
            maximum_property_cost
        ),
        'hasPreferentialProgram': has_preferential_program,
        'preferentialAnnualRate': _format_optional_decimal(
            Customer.DEFAULT_PREFERENTIAL_ANNUAL_RATE
        ),
        'preferentialMaximumPropertyCost': _format_optional_decimal(
            preferential_maximum_property_cost
        ),
        'preferentialCreditLimit': _format_optional_decimal(
            preferential_credit_limit
        ),
    }
