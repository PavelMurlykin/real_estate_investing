from math import pow

from dateutil.relativedelta import relativedelta


class MortgageCalculator:
    def __init__(self, property_cost, initial_payment_percent, initial_payment_date,
                 mortgage_term, annual_rate, has_grace_period=False,
                 grace_period_term=0, grace_period_rate=0):
        self.property_cost = property_cost
        self.initial_payment_percent = initial_payment_percent
        self.initial_payment_date = initial_payment_date
        self.mortgage_term = mortgage_term
        self.annual_rate = annual_rate
        self.has_grace_period = has_grace_period
        self.grace_period_term = grace_period_term
        self.grace_period_rate = grace_period_rate

        # Расчетные поля
        self.initial_payment = property_cost * initial_payment_percent / 100
        self.loan_amount = property_cost - self.initial_payment
        self.current_loan_balance = self.loan_amount
        self.payment_schedule = []

    def calculate(self):
        # Основные параметры
        total_months = self.mortgage_term * 12

        if self.has_grace_period and self.grace_period_term > 0:
            # Расчет льготного периода
            grace_months = self.grace_period_term * 12
            monthly_grace_rate = self.grace_period_rate / 100 / 12

            # Расчет аннуитетного платежа для льготного периода на полный срок
            annuity_coefficient_grace = (monthly_grace_rate * pow(1 + monthly_grace_rate, total_months)) / \
                                        (pow(1 + monthly_grace_rate, total_months) - 1)
            grace_monthly_payment = self.loan_amount * annuity_coefficient_grace

            # Расчет остатка долга после льготного периода
            remaining_debt_after_grace = self._calculate_remaining_debt(
                self.loan_amount, monthly_grace_rate, grace_monthly_payment, grace_months
            )

            # Расчет основного периода
            main_months = total_months - grace_months
            monthly_main_rate = self.annual_rate / 100 / 12

            # Расчет аннуитетного платежа для основного периода на оставшийся срок
            if main_months > 0:
                annuity_coefficient_main = (monthly_main_rate * pow(1 + monthly_main_rate, main_months)) / \
                                           (pow(1 + monthly_main_rate, main_months) - 1)
                main_monthly_payment = remaining_debt_after_grace * annuity_coefficient_main
            else:
                main_monthly_payment = 0

            # Даты
            grace_period_end_date = self.initial_payment_date + relativedelta(months=grace_months)
            mortgage_end_date = self.initial_payment_date + relativedelta(months=total_months)

            # Переплата
            total_grace_payments = grace_monthly_payment * grace_months
            total_main_payments = main_monthly_payment * main_months if main_months > 0 else 0
            total_overpayment = total_grace_payments + total_main_payments - self.loan_amount

            return {
                'grace_payments_count': grace_months,
                'grace_period_end_date': grace_period_end_date,
                'grace_monthly_payment': round(grace_monthly_payment, 2),
                'loan_after_grace': round(remaining_debt_after_grace, 2),
                'main_payments_count': main_months,
                'mortgage_end_date': mortgage_end_date,
                'main_monthly_payment': round(main_monthly_payment, 2),
                'total_loan_amount': round(self.loan_amount, 2),
                'total_overpayment': round(total_overpayment, 2)
            }
        else:
            # Расчет без льготного периода
            monthly_rate = self.annual_rate / 100 / 12
            annuity_coefficient = (monthly_rate * pow(1 + monthly_rate, total_months)) / \
                                  (pow(1 + monthly_rate, total_months) - 1)
            monthly_payment = self.loan_amount * annuity_coefficient

            # Даты
            mortgage_end_date = self.initial_payment_date + relativedelta(months=total_months)

            # Переплата
            total_payments = monthly_payment * total_months
            total_overpayment = total_payments - self.loan_amount

            return {
                'grace_payments_count': 0,
                'grace_period_end_date': None,
                'grace_monthly_payment': 0,
                'loan_after_grace': round(self.loan_amount, 2),
                'main_payments_count': total_months,
                'mortgage_end_date': mortgage_end_date,
                'main_monthly_payment': round(monthly_payment, 2),
                'total_loan_amount': round(self.loan_amount, 2),
                'total_overpayment': round(total_overpayment, 2)
            }

    def _calculate_remaining_debt(self, initial_debt, monthly_rate, monthly_payment, months):
        """Рассчитывает остаток долга после указанного количества месяцев"""
        debt = initial_debt
        for _ in range(months):
            interest = debt * monthly_rate
            principal = monthly_payment - interest
            debt -= principal
        return max(debt, 0)  # Не может быть отрицательным

    def get_payment_schedule(self):
        if not self.payment_schedule:
            self._generate_payment_schedule()
        return self.payment_schedule

    def _generate_payment_schedule(self):
        total_months = self.mortgage_term * 12
        current_date = self.initial_payment_date
        current_balance = self.loan_amount

        if self.has_grace_period and self.grace_period_term > 0:
            # Льготный период
            grace_months = self.grace_period_term * 12
            monthly_grace_rate = self.grace_period_rate / 100 / 12

            # Расчет аннуитетного платежа для льготного периода на полный срок
            annuity_coefficient_grace = (monthly_grace_rate * pow(1 + monthly_grace_rate, total_months)) / \
                                        (pow(1 + monthly_grace_rate, total_months) - 1)
            grace_monthly_payment = current_balance * annuity_coefficient_grace

            for month in range(1, grace_months + 1):
                interest = current_balance * monthly_grace_rate
                principal = grace_monthly_payment - interest
                payment_amount = grace_monthly_payment
                current_balance -= principal

                self.payment_schedule.append({
                    'payment_number': month,
                    'payment_date': current_date,
                    'payment_amount': round(payment_amount, 2),
                    'interest_amount': round(interest, 2),
                    'principal_amount': round(principal, 2),
                    'remaining_debt': round(current_balance, 2)
                })

                current_date += relativedelta(months=1)

            # Основной период
            main_months = total_months - grace_months
            monthly_main_rate = self.annual_rate / 100 / 12

            if main_months > 0:
                # Расчет аннуитетного платежа для основного периода на оставшийся срок
                annuity_coefficient_main = (monthly_main_rate * pow(1 + monthly_main_rate, main_months)) / \
                                           (pow(1 + monthly_main_rate, main_months) - 1)
                main_monthly_payment = current_balance * annuity_coefficient_main

                for month in range(1, main_months + 1):
                    interest = current_balance * monthly_main_rate
                    principal = main_monthly_payment - interest
                    payment_amount = main_monthly_payment
                    current_balance -= principal

                    self.payment_schedule.append({
                        'payment_number': grace_months + month,
                        'payment_date': current_date,
                        'payment_amount': round(payment_amount, 2),
                        'interest_amount': round(interest, 2),
                        'principal_amount': round(principal, 2),
                        'remaining_debt': round(current_balance, 2) if current_balance > 0 else 0
                    })

                    current_date += relativedelta(months=1)
        else:
            # Без льготного периода
            monthly_rate = self.annual_rate / 100 / 12
            annuity_coefficient = (monthly_rate * pow(1 + monthly_rate, total_months)) / \
                                  (pow(1 + monthly_rate, total_months) - 1)
            monthly_payment = current_balance * annuity_coefficient

            for month in range(1, total_months + 1):
                interest = current_balance * monthly_rate
                principal = monthly_payment - interest
                payment_amount = monthly_payment
                current_balance -= principal

                self.payment_schedule.append({
                    'payment_number': month,
                    'payment_date': current_date,
                    'payment_amount': round(payment_amount, 2),
                    'interest_amount': round(interest, 2),
                    'principal_amount': round(principal, 2),
                    'remaining_debt': round(current_balance, 2) if current_balance > 0 else 0
                })

                current_date += relativedelta(months=1)
