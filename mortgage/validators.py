from dateutil.relativedelta import relativedelta


MORTGAGE_DATE_RANGE_ERROR = (
    'Дата первоначального взноса слишком поздняя для указанного срока ипотеки.'
)


def is_mortgage_end_date_supported(initial_payment_date, mortgage_term_months):
    """Check that the entire mortgage term fits in the supported calendar."""
    try:
        initial_payment_date + relativedelta(months=mortgage_term_months)
    except (ValueError, OverflowError):
        return False
    return True
