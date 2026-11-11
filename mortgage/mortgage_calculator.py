from decimal import Decimal, ROUND_HALF_UP, localcontext

from dateutil.relativedelta import relativedelta


MONEY_QUANTUM = Decimal('0.01')


def _money(value):
    """Round one accounting amount to kopecks."""
    return value.quantize(MONEY_QUANTUM, rounding=ROUND_HALF_UP)


def _annuity_coefficient(monthly_rate, month_count):
    """Calculate an annuity factor without subtracting large powers."""
    if monthly_rate == 0:
        return Decimal(1) / month_count
    return monthly_rate / (1 - (1 + monthly_rate) ** -month_count)


class MortgageCalculator:
    """Calculate market mortgage installments with balanced monetary rows."""

    def __init__(
        self,
        property_cost,
        initial_payment_percent,
        initial_payment_date,
        mortgage_term,
        annual_rate,
        has_grace_period=False,
        grace_period_term=0,
        grace_period_rate=0,
    ):
        """Keep the existing calculator input and result contracts."""
        self.property_cost = Decimal(str(property_cost))
        self.initial_payment_percent = Decimal(str(initial_payment_percent))
        self.initial_payment_date = initial_payment_date
        self.mortgage_term = mortgage_term
        self.annual_rate = Decimal(str(annual_rate))
        self.has_grace_period = has_grace_period
        self.grace_period_term = grace_period_term
        self.grace_period_rate = Decimal(str(grace_period_rate))
        with localcontext() as context:
            context.prec = 60
            self.initial_payment = (
                self.property_cost * self.initial_payment_percent / 100
            )
            self.loan_amount = self.property_cost - self.initial_payment
        self.current_loan_balance = self.loan_amount
        self.payment_schedule = []
        self._result = None

    def calculate(self):
        """Return the summary of the same installments used by all exporters."""
        if self._result is None:
            self._generate_payment_schedule()
        return self._result.copy()

    def get_payment_schedule(self):
        """Return the lazily calculated schedule in the established format."""
        if self._result is None:
            self._generate_payment_schedule()
        return self.payment_schedule

    def _append_period(
        self, initial_balance, monthly_rate, total_months,
        payment_count, first_payment_date,
    ):
        """Derive each balance directly and preserve kopeck accounting identities."""
        monthly_payment = (
            initial_balance * _annuity_coefficient(monthly_rate, total_months)
        )
        discount = (1 + monthly_rate) ** -total_months
        current_balance = initial_balance
        payment_date = first_payment_date
        payment_offset = len(self.payment_schedule)
        for payment_number in range(1, payment_count + 1):
            months_remaining = total_months - payment_number
            if monthly_rate == 0:
                next_balance = initial_balance * months_remaining / total_months
            else:
                next_balance = initial_balance * (
                    1 - (1 + monthly_rate) ** -months_remaining
                ) / (1 - discount)
            interest = _money(current_balance * monthly_rate)
            principal = _money(current_balance) - _money(next_balance)
            self.payment_schedule.append({
                'payment_number': payment_offset + payment_number,
                'payment_date': payment_date,
                'payment_amount': float(principal + interest),
                'interest_amount': float(interest),
                'principal_amount': float(principal),
                'remaining_debt': float(_money(next_balance)),
            })
            current_balance = next_balance
            payment_date += relativedelta(months=1)
        return current_balance, monthly_payment, payment_date

    def _generate_payment_schedule(self):
        """Build both periods using high precision and total the displayed rows."""
        with localcontext() as context:
            context.prec = 60
            grace_months = (
                self.grace_period_term
                if self.has_grace_period and self.grace_period_term > 0
                else 0
            )
            balance = self.loan_amount
            payment_date = self.initial_payment_date
            grace_payment = Decimal(0)
            if grace_months:
                balance, grace_payment, payment_date = self._append_period(
                    balance, self.grace_period_rate / 1200,
                    self.mortgage_term, grace_months, payment_date,
                )
            loan_after_grace = _money(balance)
            main_months = self.mortgage_term - grace_months
            main_payment = Decimal(0)
            if main_months > 0:
                _, main_payment, _ = self._append_period(
                    balance, self.annual_rate / 1200,
                    main_months, main_months, payment_date,
                )
            overpayment = sum(
                (Decimal(str(row['interest_amount']))
                 for row in self.payment_schedule),
                Decimal(0),
            )
            self._result = {
                'grace_payments_count': grace_months,
                'grace_period_end_date': (
                    self.initial_payment_date + relativedelta(
                        months=grace_months,
                    ) if grace_months else None
                ),
                'grace_monthly_payment': float(_money(grace_payment)),
                'loan_after_grace': float(loan_after_grace),
                'main_payments_count': main_months,
                'mortgage_end_date': (
                    self.initial_payment_date + relativedelta(
                        months=self.mortgage_term,
                    )
                ),
                'main_monthly_payment': float(_money(main_payment)),
                'total_loan_amount': float(_money(self.loan_amount)),
                # Large totals can exceed float's kopeck precision.
                'total_overpayment': overpayment,
            }
