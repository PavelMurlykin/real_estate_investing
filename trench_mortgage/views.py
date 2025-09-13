from django.shortcuts import render, redirect
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from decimal import Decimal
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json

from .forms import TrenchMortgageForm, TrenchForm
from .models import TrenchMortgageCalculation, Trench
from mortgage.utils import format_currency


def trench_mortgage_calculator(request):
    if request.method == 'POST':
        form = TrenchMortgageForm(request.POST)
        if form.is_valid():
            # Сохраняем данные формы в сессии
            request.session['trench_mortgage_data'] = form.cleaned_data
            return render(request, 'trench_mortgage/trench_form.html', {
                'trench_count': form.cleaned_data['TRENCH_COUNT'],
                'form': TrenchForm()
            })
    else:
        form = TrenchMortgageForm()

    return render(request, 'trench_mortgage/calculator.html', {'form': form})


@csrf_exempt
def calculate_trench_mortgage(request):
    if request.method == 'POST':
        try:
            # Получаем данные из сессии и POST-запроса
            trench_data = json.loads(request.POST.get('trench_data', '[]'))
            mortgage_data = request.session.get('trench_mortgage_data', {})

            # Расчет итоговой стоимости объекта
            property_cost = float(mortgage_data['PROPERTY'].property_cost)
            discount_markup_value = float(mortgage_data.get('DISCOUNT_MARKUP_VALUE', 0) or 0)

            if mortgage_data['DISCOUNT_MARKUP_TYPE'] == 'discount':
                final_property_cost = property_cost * (1 - discount_markup_value / 100)
            else:
                final_property_cost = property_cost * (1 + discount_markup_value / 100)

            # Расчет первоначального взноса
            initial_payment_percent = float(mortgage_data['INITIAL_PAYMENT_PERCENT'])
            initial_payment = final_property_cost * initial_payment_percent / 100
            loan_amount = final_property_cost - initial_payment

            # Расчет траншей
            trenches = []
            remaining_percent = 100.0
            total_loan_amount = 0
            total_overpayment = 0

            for i, trench in enumerate(trench_data):
                if i < len(trench_data) - 1:
                    trench_percent = float(trench['trench_percent'])
                    remaining_percent -= trench_percent
                else:
                    trench_percent = remaining_percent  # Последний транш получает остаток

                trench_amount = loan_amount * trench_percent / 100
                annual_rate = float(trench['annual_rate'])
                trench_date = datetime.strptime(trench['trench_date'], '%Y-%m-%d').date()

                # Расчет ежемесячного платежа для этого транша
                monthly_rate = annual_rate / 100 / 12
                months_remaining = (mortgage_data['MORTGAGE_TERM'] * 12) - (i * 12)  # Упрощенный расчет

                if monthly_rate > 0:
                    monthly_payment = (trench_amount * monthly_rate) / (1 - (1 + monthly_rate) ** -months_remaining)
                else:
                    monthly_payment = trench_amount / months_remaining

                # Расчет переплаты по траншу
                overpayment = (monthly_payment * months_remaining) - trench_amount

                trenches.append({
                    'number': i + 1,
                    'date': trench_date,
                    'percent': trench_percent,
                    'amount': trench_amount,
                    'annual_rate': annual_rate,
                    'monthly_payment': monthly_payment,
                    'payments_count': months_remaining,
                    'remaining_debt': loan_amount - sum(t['amount'] for t in trenches),
                    'overpayment': overpayment
                })

                total_loan_amount += trench_amount
                total_overpayment += overpayment

            # Форматирование результатов
            formatted_result = {
                'final_property_cost': format_currency(final_property_cost),
                'initial_payment': format_currency(initial_payment),
                'initial_payment_date': mortgage_data['INITIAL_PAYMENT_DATE'].strftime('%d.%m.%Y'),
                'total_loan_amount': format_currency(total_loan_amount),
                'total_overpayment': format_currency(total_overpayment),
                'trenches': []
            }

            for trench in trenches:
                formatted_result['trenches'].append({
                    'number': trench['number'],
                    'date': trench['date'].strftime('%d.%m.%Y'),
                    'percent': f"{trench['percent']:.2f}",
                    'amount': format_currency(trench['amount']),
                    'annual_rate': f"{trench['annual_rate']:.2f}",
                    'monthly_payment': format_currency(trench['monthly_payment']),
                    'payments_count': trench['payments_count'],
                    'remaining_debt': format_currency(trench['remaining_debt'])
                })

            return JsonResponse({'success': True, 'result': formatted_result})

        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})

    return JsonResponse({'success': False, 'error': 'Invalid request method'})