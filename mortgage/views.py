import decimal
import openpyxl
from django.http import HttpResponse
from django.shortcuts import render, get_object_or_404
from openpyxl.styles import Font, Alignment, NamedStyle
from openpyxl.utils import get_column_letter

from .forms import MortgageForm
from .models import MortgageCalculation
from .mortgage_calculator import MortgageCalculator
from .utils import format_currency
from property.models import Property


def mortgage_calculator(request):
    # Инициализация формы
    mortgage_form = MortgageForm(request.POST or None)

    # Получаем список всех объектов
    properties = Property.objects.all()

    context = {
        'mortgage_form': mortgage_form,
        'properties': properties
    }

    if request.method == 'POST':
        if 'calculate' in request.POST:
            if mortgage_form.is_valid():
                # Получаем данные из формы
                data = mortgage_form.cleaned_data

                # Получаем выбранный объект недвижимости
                property_obj = data['PROPERTY']

                # Получаем стоимость из формы и преобразуем в float
                property_cost = float(data['PROPERTY_COST'])

                # Получаем значения первоначального взноса и преобразуем в float
                initial_payment_percent = float(data.get('INITIAL_PAYMENT_PERCENT', 0) or 0)
                initial_payment_rubles = float(data.get('INITIAL_PAYMENT_RUBLES', 0) or 0)

                # Рассчитываем итоговую стоимость объекта
                discount_markup_value = float(data.get('DISCOUNT_MARKUP_VALUE', 0) or 0)

                if data['DISCOUNT_MARKUP_TYPE'] == 'discount':
                    final_property_cost = property_cost * (1 - discount_markup_value / 100)
                else:
                    final_property_cost = property_cost * (1 + discount_markup_value / 100)

                # Если введены рубли, но не проценты, рассчитываем проценты
                if initial_payment_rubles and not initial_payment_percent and final_property_cost > 0:
                    initial_payment_percent = (initial_payment_rubles / final_property_cost) * 100

                # Если введены проценты, но не рубли, рассчитываем рубли
                if initial_payment_percent and not initial_payment_rubles and final_property_cost > 0:
                    initial_payment_rubles = final_property_cost * initial_payment_percent / 100

                # Если оба поля заполнены, используем проценты как основной источник
                if initial_payment_percent and initial_payment_rubles:
                    # Пересчитываем рубли на основе процентов для consistency
                    initial_payment_rubles = final_property_cost * initial_payment_percent / 100

                # Создаем экземпляр калькулятора (все значения преобразуем к float)
                calculator = MortgageCalculator(
                    property_cost=float(final_property_cost),
                    initial_payment_percent=float(initial_payment_percent),
                    initial_payment_date=data['INITIAL_PAYMENT_DATE'],
                    mortgage_term=int(data['MORTGAGE_TERM']),
                    annual_rate=float(data['ANNUAL_RATE']),
                    has_grace_period=data['HAS_GRACE_PERIOD'] == 'да',
                    grace_period_term=int(data['GRACE_PERIOD_TERM'] or 0),
                    grace_period_rate=float(data['GRACE_PERIOD_RATE'] or 0)
                )

                # Выполняем расчет
                result = calculator.calculate()

                # Форматируем числовые значения для отображения
                formatted_result = {}
                for key, value in result.items():
                    if key in ['grace_payments_count', 'main_payments_count']:
                        # Целые числа
                        formatted_result[key] = int(value) if value else 0
                    elif isinstance(value, (int, float, decimal.Decimal)):
                        # Денежные значения
                        formatted_result[key] = format_currency(value)
                    else:
                        formatted_result[key] = value

                # Получаем график платежей
                payment_schedule = calculator.get_payment_schedule()

                # Форматируем числовые значения в графике платежей
                for payment in payment_schedule:
                    for key in ['payment_amount', 'interest_amount', 'principal_amount', 'remaining_debt']:
                        if key in payment:
                            payment[key] = format_currency(payment[key])

                # Сохраняем расчет в базу данных (сохраняем как Decimal)
                calculation = MortgageCalculation(
                    property=property_obj,
                    initial_payment_percent=decimal.Decimal(str(initial_payment_percent)),
                    initial_payment_date=data['INITIAL_PAYMENT_DATE'],
                    mortgage_term=data['MORTGAGE_TERM'],
                    annual_rate=decimal.Decimal(str(data['ANNUAL_RATE'])),
                    has_grace_period=data['HAS_GRACE_PERIOD'] == 'да',
                    grace_period_term=data['GRACE_PERIOD_TERM'],
                    grace_period_rate=decimal.Decimal(str(data['GRACE_PERIOD_RATE'] or 0)),
                    discount_markup_type=data['DISCOUNT_MARKUP_TYPE'],
                    discount_markup_value=decimal.Decimal(str(discount_markup_value)),
                    final_property_cost=decimal.Decimal(str(final_property_cost)),
                    # Результаты
                    grace_payments_count=result['grace_payments_count'],
                    grace_period_end_date=result['grace_period_end_date'],
                    grace_monthly_payment=decimal.Decimal(str(result['grace_monthly_payment'])),
                    loan_after_grace=decimal.Decimal(str(result['loan_after_grace'])),
                    main_payments_count=result['main_payments_count'],
                    mortgage_end_date=result['mortgage_end_date'],
                    main_monthly_payment=decimal.Decimal(str(result['main_monthly_payment'])),
                    total_loan_amount=decimal.Decimal(str(result['total_loan_amount'])),
                    total_overpayment=decimal.Decimal(str(result['total_overpayment']))
                )
                calculation.save()

                # Сохраняем расчет в контекст
                context['result'] = formatted_result
                context['has_grace_period'] = data['HAS_GRACE_PERIOD'] == 'да'
                context['payment_schedule'] = payment_schedule
                context['final_property_cost'] = format_currency(final_property_cost)
                context['discount_markup_type'] = data['DISCOUNT_MARKUP_TYPE']
                context['discount_markup_value'] = discount_markup_value
                context['selected_property'] = property_obj

                # Передаем заполненную форму в контекст
                context['mortgage_form'] = mortgage_form

        elif 'export' in request.POST:
            # Аналогичные изменения для блока экспорта
            if mortgage_form.is_valid():
                # Получаем данные из формы
                mortgage_data = mortgage_form.cleaned_data

                # Получаем выбранный объект недвижимости
                property_obj = mortgage_data['PROPERTY']

                # Получаем стоимость из формы и преобразуем в float
                property_cost = float(mortgage_data['PROPERTY_COST'])

                # Получаем значения первоначального взноса и преобразуем в float
                initial_payment_percent = float(mortgage_data.get('INITIAL_PAYMENT_PERCENT', 0) or 0)
                initial_payment_rubles = float(mortgage_data.get('INITIAL_PAYMENT_RUBLES', 0) or 0)

                # Рассчитываем итоговую стоимость объекта
                discount_markup_value = float(mortgage_data.get('DISCOUNT_MARKUP_VALUE', 0) or 0)

                if mortgage_data['DISCOUNT_MARKUP_TYPE'] == 'discount':
                    final_property_cost = property_cost * (1 - discount_markup_value / 100)
                else:
                    final_property_cost = property_cost * (1 + discount_markup_value / 100)

                # Если введены рубли, но не проценты, рассчитываем проценты
                if initial_payment_rubles and not initial_payment_percent and final_property_cost > 0:
                    initial_payment_percent = (initial_payment_rubles / final_property_cost) * 100

                # Если введены проценты, но не рубли, рассчитываем рубли
                if initial_payment_percent and not initial_payment_rubles and final_property_cost > 0:
                    initial_payment_rubles = final_property_cost * initial_payment_percent / 100

                # Если оба поля заполнены, используем проценты как основной источник
                if initial_payment_percent and initial_payment_rubles:
                    # Пересчитываем рубли на основе процентов для consistency
                    initial_payment_rubles = final_property_cost * initial_payment_percent / 100

                # Создаем экземпляр калькулятора (все значения преобразуем к float)
                calculator = MortgageCalculator(
                    property_cost=float(final_property_cost),
                    initial_payment_percent=float(initial_payment_percent),
                    initial_payment_date=mortgage_data['INITIAL_PAYMENT_DATE'],
                    mortgage_term=int(mortgage_data['MORTGAGE_TERM']),
                    annual_rate=float(mortgage_data['ANNUAL_RATE']),
                    has_grace_period=mortgage_data['HAS_GRACE_PERIOD'] == 'да',
                    grace_period_term=int(mortgage_data['GRACE_PERIOD_TERM'] or 0),
                    grace_period_rate=float(mortgage_data['GRACE_PERIOD_RATE'] or 0)
                )

                # Выполняем расчет
                result = calculator.calculate()
                payment_schedule = calculator.get_payment_schedule()

                # Создаем Excel-файл
                response = HttpResponse(
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                response['Content-Disposition'] = 'attachment; filename="mortgage_calculation.xlsx"'

                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "Ипотечный расчет"

                # Создаем стиль для чисел с разделителями
                number_style = NamedStyle(name="number_style")
                number_style.number_format = '# ##0.00'
                wb.add_named_style(number_style)

                # Создаем стиль для целых чисел
                integer_style = NamedStyle(name="integer_style")
                integer_style.number_format = '# ##0'
                wb.add_named_style(integer_style)

                # Заголовок
                ws.merge_cells('A1:B1')
                ws['A1'] = 'Ипотечный калькулятор - результаты расчета'
                ws['A1'].font = Font(bold=True, size=14)
                ws['A1'].alignment = Alignment(horizontal='center')

                # Данные объекта
                ws['A3'] = 'Данные объекта:'
                ws['A3'].font = Font(bold=True)

                property_data_list = [
                    ['Застройщик', property_obj.building.real_estate_complex.developer.name],
                    ['Город', property_obj.building.real_estate_complex.district.city.name],
                    ['Название ЖК', property_obj.building.real_estate_complex.name],
                    ['Класс ЖК', property_obj.building.real_estate_complex.real_estate_class.name],
                    ['Корпус', property_obj.building.number],
                    ['№ квартиры', property_obj.apartment_number],
                    ['Планировка', property_obj.layout.name],
                    ['Площадь', float(property_obj.area)],
                    ['Этаж', property_obj.floor],
                    ['Стоимость объекта, руб.', property_cost],
                    ['Тип изменения цены',
                     'Скидка' if mortgage_data['DISCOUNT_MARKUP_TYPE'] == 'discount' else 'Удорожание'],
                    ['Значение, %', discount_markup_value],
                    ['Итоговая стоимость объекта, руб.', final_property_cost],
                ]

                for i, (param, value) in enumerate(property_data_list, start=4):
                    ws[f'A{i}'] = param
                    cell = ws[f'B{i}']

                    # Применяем форматирование к числам
                    if isinstance(value, (int, float)):
                        if param == 'Этаж':
                            cell.value = int(value)
                            cell.style = integer_style
                        elif param in ['Площадь', 'Значение, %']:
                            cell.value = value
                            cell.style = number_style
                        elif param in ['Стоимость объекта, руб.', 'Итоговая стоимость объекта, руб.']:
                            cell.value = value
                            cell.style = number_style
                        else:
                            cell.value = value
                    else:
                        cell.value = value

                    # Выравнивание по центру для столбца B
                    cell.alignment = Alignment(horizontal='center')

                # Входные параметры ипотеки
                start_row = len(property_data_list) + 5
                ws[f'A{start_row}'] = 'Параметры ипотеки:'
                ws[f'A{start_row}'].font = Font(bold=True)

                mortgage_data_list = [
                    ['Первоначальный взнос, %', initial_payment_percent],
                    ['Первоначальный взнос, руб.', final_property_cost * initial_payment_percent / 100],
                    ['Дата первоначального взноса', mortgage_data['INITIAL_PAYMENT_DATE'].strftime('%d.%m.%Y')],
                    ['Срок ипотеки, годы', int(mortgage_data['MORTGAGE_TERM'])],
                    ['Годовая ставка, %', float(mortgage_data['ANNUAL_RATE'])],
                    ['Наличие льготного периода', 'Да' if mortgage_data['HAS_GRACE_PERIOD'] == 'да' else 'Нет'],
                ]

                if mortgage_data['HAS_GRACE_PERIOD'] == 'да':
                    mortgage_data_list.extend([
                        ['Срок льготного периода, годы', int(mortgage_data['GRACE_PERIOD_TERM'])],
                        ['Годовая ставка в льготный период, %', float(mortgage_data['GRACE_PERIOD_RATE'])]
                    ])

                for i, (param, value) in enumerate(mortgage_data_list, start=start_row + 1):
                    ws[f'A{i}'] = param
                    cell = ws[f'B{i}']

                    # Применяем форматирование к числам
                    if isinstance(value, (int, float)):
                        if param in ['Срок ипотеки, годы', 'Срок льготного периода, годы']:
                            cell.value = int(value)
                            cell.style = integer_style
                        else:
                            cell.value = value
                            cell.style = number_style
                    else:
                        cell.value = value

                    # Выравнивание по центру для столбца B
                    cell.alignment = Alignment(horizontal='center')

                # Результаты расчета
                result_start = start_row + len(mortgage_data_list) + 2
                ws[f'A{result_start}'] = 'Результаты расчета:'
                ws[f'A{result_start}'].font = Font(bold=True)

                # Форматируем дату льготного периода с проверкой на None
                grace_period_end_date_str = ''
                if result['grace_period_end_date']:
                    grace_period_end_date_str = result['grace_period_end_date'].strftime('%d.%m.%Y')

                result_data = []

                if mortgage_data['HAS_GRACE_PERIOD'] == 'да':
                    result_data.extend([
                        ['Число платежей за льготный период', result['grace_payments_count']],
                        ['Дата последнего платежа по льготному периоду', grace_period_end_date_str],
                        ['Сумма ежемесячного платежа во время льготного периода, руб.',
                         float(result['grace_monthly_payment'])],
                        ['Сумма кредита после окончания льготного периода, руб.', float(result['loan_after_grace'])],
                    ])

                result_data.extend([
                    ['Число платежей за основной период', result['main_payments_count']],
                    ['Дата последнего платежа по ипотеке', result['mortgage_end_date'].strftime('%d.%m.%Y')],
                    ['Сумма ежемесячного платежа за основной период, руб.', float(result['main_monthly_payment'])],
                    ['Сумма кредита, руб.', float(result['total_loan_amount'])],
                    ['Сумма переплат по кредиту, руб.', float(result['total_overpayment'])],
                ])

                for i, (param, value) in enumerate(result_data, start=result_start + 1):
                    ws[f'A{i}'] = param
                    cell = ws[f'B{i}']

                    # Применяем форматирование к числам
                    if isinstance(value, (int, float)):
                        if param in ['Число платежей за льготный период', 'Число платежей за основной период']:
                            cell.value = int(value)
                            cell.style = integer_style
                        else:
                            cell.value = value
                            cell.style = number_style
                    else:
                        cell.value = value

                    # Выравнивание по центру для столбца B
                    cell.alignment = Alignment(horizontal='center')

                # График платежей
                schedule_start = result_start + len(result_data) + 2
                ws[f'A{schedule_start}'] = 'График платежей:'
                ws[f'A{schedule_start}'].font = Font(bold=True)

                headers = ['№', 'Дата платежа', 'Сумма платежа, руб.', 'В том числе проценты, руб.',
                           'В том числе основной долг, руб.', 'Остаток долга, руб.']

                for col, header in enumerate(headers, start=1):
                    cell = ws.cell(row=schedule_start + 1, column=col, value=header)
                    cell.font = Font(bold=True)
                    cell.alignment = Alignment(horizontal='center')

                for row, payment in enumerate(payment_schedule, start=schedule_start + 2):
                    ws.cell(row=row, column=1, value=payment['payment_number'])
                    ws.cell(row=row, column=2, value=payment['payment_date'].strftime('%d.%m.%Y'))

                    # Используем исходные числовые значения
                    for col_idx, key in enumerate(
                            ['payment_amount', 'interest_amount', 'principal_amount', 'remaining_debt'], start=3):
                        value = payment[key]
                        # Если значение - строка, преобразуем его в число
                        if isinstance(value, str):
                            numeric_value = float(value.replace(' ', '').replace(',', '.'))
                        else:
                            numeric_value = float(value)
                        cell = ws.cell(row=row, column=col_idx, value=numeric_value)
                        cell.style = number_style
                        cell.alignment = Alignment(horizontal='center')

                # Форматирование
                for column in ws.columns:
                    max_length = 0
                    column_letter = get_column_letter(column[0].column)
                    for cell in column:
                        if cell.value:
                            max_length = max(max_length, len(str(cell.value)))
                    adjusted_width = min(max_length + 2, 50)
                    ws.column_dimensions[column_letter].width = adjusted_width

                # Сохраняем файл
                wb.save(response)
                return response

    return render(request, 'mortgage/mortgage_calculator.html', context)


def calculation_list(request):
    """Список всех расчетов"""
    calculations = MortgageCalculation.objects.select_related('property').all().order_by('-timestamp')
    return render(request, 'mortgage/calculation_list.html', {
        'calculations': calculations
    })


def calculation_detail(request, pk):
    """Детальная информация о расчете"""
    calculation = get_object_or_404(MortgageCalculation.objects.select_related('property'), pk=pk)

    # Форматируем значения для отображения
    calculation.formatted_final_property_cost = format_currency(calculation.final_property_cost)
    calculation.formatted_grace_monthly_payment = format_currency(
        calculation.grace_monthly_payment) if calculation.grace_monthly_payment else None
    calculation.formatted_loan_after_grace = format_currency(
        calculation.loan_after_grace) if calculation.loan_after_grace else None
    calculation.formatted_main_monthly_payment = format_currency(
        calculation.main_monthly_payment) if calculation.main_monthly_payment else None
    calculation.formatted_total_loan_amount = format_currency(
        calculation.total_loan_amount) if calculation.total_loan_amount else None
    calculation.formatted_total_overpayment = format_currency(
        calculation.total_overpayment) if calculation.total_overpayment else None

    return render(request, 'mortgage/calculation_detail.html', {
        'calculation': calculation
    })
