# mortgage/views.py
import decimal

import openpyxl
from django.contrib import messages
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST
from openpyxl.styles import Alignment, Font, NamedStyle
from openpyxl.utils import get_column_letter

from property.models import Property

from .forms import MortgageForm
from .models import MortgageCalculation
from .mortgage_calculator import MortgageCalculator
from .utils import format_currency


def _get_target_customer(request):
    customer_id = request.POST.get('customer') or request.GET.get('customer')
    if not customer_id or not request.user.is_authenticated:
        return None

    from customer.models import Customer

    return get_object_or_404(Customer, pk=customer_id, user=request.user)


def _attach_calculation_to_customer(customer, calculation):
    if customer is None:
        return

    from customer.models import CustomerCalculation

    CustomerCalculation.objects.get_or_create(
        customer=customer,
        calculation=calculation,
    )


def _normalize_discount_markup_values(cleaned_data):
    """Возвращает процент, рубли и итоговую стоимость после корректировки."""
    property_cost = float(cleaned_data['PROPERTY_COST'])
    discount_markup_percent = float(
        cleaned_data.get('DISCOUNT_MARKUP_VALUE', 0) or 0
    )
    discount_markup_rubles = float(
        cleaned_data.get('DISCOUNT_MARKUP_RUBLES', 0) or 0
    )
    discount_markup_source = cleaned_data.get('DISCOUNT_MARKUP_SOURCE')

    if discount_markup_source == 'rubles':
        if property_cost > 0:
            discount_markup_percent = (
                discount_markup_rubles / property_cost
            ) * 100
        else:
            discount_markup_percent = 0
    else:
        discount_markup_rubles = (
            property_cost * discount_markup_percent / 100
        )

    if cleaned_data['DISCOUNT_MARKUP_TYPE'] == 'discount':
        final_property_cost = property_cost - discount_markup_rubles
    else:
        final_property_cost = property_cost + discount_markup_rubles

    return (
        discount_markup_percent,
        discount_markup_rubles,
        final_property_cost,
    )


def _normalize_initial_payment_values(cleaned_data, final_property_cost):
    """Возвращает согласованные значения первоначального взноса."""
    initial_payment_percent = float(
        cleaned_data.get('INITIAL_PAYMENT_PERCENT', 0) or 0
    )
    initial_payment_rubles = float(
        cleaned_data.get('INITIAL_PAYMENT_RUBLES', 0) or 0
    )
    initial_payment_source = cleaned_data.get('INITIAL_PAYMENT_SOURCE')

    if initial_payment_source == 'rubles':
        initial_payment_percent = (
            initial_payment_rubles / final_property_cost * 100
            if final_property_cost > 0
            else 0
        )
    else:
        initial_payment_rubles = (
            final_property_cost * initial_payment_percent / 100
        )

    return initial_payment_percent, initial_payment_rubles


def _get_discount_markup_labels(discount_markup_type):
    """Возвращает подписи для корректировки цены в процентах и рублях."""
    if discount_markup_type == 'discount':
        return 'Скидка, %', 'Скидка, руб.'

    return 'Удорожание, %', 'Удорожание, руб.'


def mortgage_calculator(request):
    # Инициализация формы
    """Описание метода mortgage_calculator.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        request: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    target_customer = _get_target_customer(request)

    if request.method == 'POST':
        form_data = request.POST.copy()
        selected_id = form_data.get('PROPERTY')
        if selected_id:
            selected_property = Property.objects.filter(id=selected_id).first()
            if selected_property:
                if not form_data.get('PROPERTY_COST'):
                    form_data['PROPERTY_COST'] = str(
                        selected_property.property_cost
                    )
        mortgage_form = MortgageForm(form_data)
    else:
        mortgage_form = MortgageForm()

    context = {
        'mortgage_form': mortgage_form,
        'target_customer': target_customer,
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

                # Получаем базовую стоимость из скрытого поля
                base_property_cost = float(data['PROPERTY_COST'])

                (
                    discount_markup_value,
                    discount_markup_rubles,
                    final_property_cost,
                ) = _normalize_discount_markup_values(data)
                (
                    initial_payment_percent,
                    initial_payment_rubles,
                ) = _normalize_initial_payment_values(
                    data, final_property_cost
                )

                # Создаем экземпляр калькулятора.
                # Все значения преобразуем к float.
                calculator = MortgageCalculator(
                    property_cost=float(final_property_cost),
                    initial_payment_percent=float(initial_payment_percent),
                    initial_payment_date=data['INITIAL_PAYMENT_DATE'],
                    mortgage_term=int(data['MORTGAGE_TERM']),
                    annual_rate=float(data['ANNUAL_RATE']),
                    has_grace_period=data['HAS_GRACE_PERIOD'] == 'yes',
                    grace_period_term=int(data['GRACE_PERIOD_TERM'] or 0),
                    grace_period_rate=float(data['GRACE_PERIOD_RATE'] or 0),
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
                    for key in [
                        'payment_amount',
                        'interest_amount',
                        'principal_amount',
                        'remaining_debt',
                    ]:
                        if key in payment:
                            payment[key] = format_currency(payment[key])

                # Сохраняем расчет в базу данных (сохраняем как Decimal)
                calculation = MortgageCalculation(
                    property=property_obj,
                    base_property_cost=decimal.Decimal(
                        str(base_property_cost)
                    ),
                    initial_payment_percent=decimal.Decimal(
                        str(initial_payment_percent)
                    ),
                    initial_payment_date=data['INITIAL_PAYMENT_DATE'],
                    mortgage_term=data['MORTGAGE_TERM'],
                    annual_rate=decimal.Decimal(str(data['ANNUAL_RATE'])),
                    has_grace_period=data['HAS_GRACE_PERIOD'] == 'yes',
                    grace_period_term=data['GRACE_PERIOD_TERM'],
                    grace_period_rate=decimal.Decimal(
                        str(data['GRACE_PERIOD_RATE'] or 0)
                    ),
                    discount_markup_type=data['DISCOUNT_MARKUP_TYPE'],
                    discount_markup_value=decimal.Decimal(
                        str(discount_markup_value)
                    ),
                    final_property_cost=decimal.Decimal(
                        str(final_property_cost)
                    ),
                    # Результаты
                    grace_payments_count=result['grace_payments_count'],
                    grace_period_end_date=result['grace_period_end_date'],
                    grace_monthly_payment=decimal.Decimal(
                        str(result['grace_monthly_payment'])
                    ),
                    loan_after_grace=decimal.Decimal(
                        str(result['loan_after_grace'])
                    ),
                    main_payments_count=result['main_payments_count'],
                    mortgage_end_date=result['mortgage_end_date'],
                    main_monthly_payment=decimal.Decimal(
                        str(result['main_monthly_payment'])
                    ),
                    total_loan_amount=decimal.Decimal(
                        str(result['total_loan_amount'])
                    ),
                    total_overpayment=decimal.Decimal(
                        str(result['total_overpayment'])
                    ),
                )
                calculation.save()
                _attach_calculation_to_customer(target_customer, calculation)
                if target_customer is not None:
                    messages.success(
                        request,
                        'Расчет сохранен и привязан к клиенту.',
                    )

                # Сохраняем расчет в контекст
                context['result'] = formatted_result
                context['has_grace_period'] = data['HAS_GRACE_PERIOD'] == 'yes'
                context['payment_schedule'] = payment_schedule
                context['final_property_cost'] = format_currency(
                    final_property_cost
                )
                context['discount_markup_type'] = data['DISCOUNT_MARKUP_TYPE']
                context['discount_markup_value'] = discount_markup_value
                context['discount_markup_rubles'] = discount_markup_rubles
                context['selected_property'] = property_obj
                context['initial_payment_percent'] = initial_payment_percent
                context['initial_payment_rubles'] = initial_payment_rubles

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

                (
                    discount_markup_value,
                    discount_markup_rubles,
                    final_property_cost,
                ) = _normalize_discount_markup_values(mortgage_data)
                (
                    initial_payment_percent,
                    initial_payment_rubles,
                ) = _normalize_initial_payment_values(
                    mortgage_data, final_property_cost
                )

                # Создаем экземпляр калькулятора.
                # Все значения преобразуем к float.
                calculator = MortgageCalculator(
                    property_cost=float(final_property_cost),
                    initial_payment_percent=float(initial_payment_percent),
                    initial_payment_date=mortgage_data['INITIAL_PAYMENT_DATE'],
                    mortgage_term=int(mortgage_data['MORTGAGE_TERM']),
                    annual_rate=float(mortgage_data['ANNUAL_RATE']),
                    has_grace_period=mortgage_data['HAS_GRACE_PERIOD']
                    == 'yes',
                    grace_period_term=int(
                        mortgage_data['GRACE_PERIOD_TERM'] or 0
                    ),
                    grace_period_rate=float(
                        mortgage_data['GRACE_PERIOD_RATE'] or 0
                    ),
                )

                # Выполняем расчет
                result = calculator.calculate()
                payment_schedule = calculator.get_payment_schedule()

                # Создаем Excel-файл
                response = HttpResponse(
                    content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
                )
                response['Content-Disposition'] = (
                    'attachment; filename="mortgage_calculation.xlsx"'
                )

                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = 'Ипотечный расчет'

                # Создаем стиль для чисел с разделителями
                number_style = NamedStyle(name='number_style')
                number_style.number_format = '# ##0.00'
                wb.add_named_style(number_style)

                # Создаем стиль для целых чисел
                integer_style = NamedStyle(name='integer_style')
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

                (
                    discount_markup_percent_label,
                    discount_markup_rubles_label,
                ) = _get_discount_markup_labels(
                    mortgage_data['DISCOUNT_MARKUP_TYPE']
                )

                property_data_list = [
                    [
                        'Застройщик',
                        property_obj.building.real_estate_complex.developer.name,
                    ],
                    [
                        'Город',
                        property_obj.building.real_estate_complex.district.city.name,
                    ],
                    [
                        'Название ЖК',
                        property_obj.building.real_estate_complex.name,
                    ],
                    [
                        'Класс ЖК',
                        property_obj.building.real_estate_complex.real_estate_class.name,
                    ],
                    ['Корпус', property_obj.building.number],
                    ['№ квартиры', property_obj.apartment_number],
                    ['Планировка', property_obj.layout.name],
                    ['Площадь', float(property_obj.area)],
                    ['Этаж', property_obj.floor],
                    ['Стоимость объекта, руб.', property_cost],
                    [
                        'Корректировка цены',
                        'Скидка'
                        if mortgage_data['DISCOUNT_MARKUP_TYPE'] == 'discount'
                        else 'Удорожание',
                    ],
                    [discount_markup_percent_label, discount_markup_value],
                    [discount_markup_rubles_label, discount_markup_rubles],
                    ['Итоговая стоимость объекта, руб.', final_property_cost],
                ]

                for i, (param, value) in enumerate(
                    property_data_list, start=4
                ):
                    ws[f'A{i}'] = param
                    cell = ws[f'B{i}']

                    # Применяем форматирование к числам
                    if isinstance(value, (int, float)):
                        if param == 'Этаж':
                            cell.value = int(value)
                            cell.style = integer_style
                        elif param in [
                            'Площадь',
                            discount_markup_percent_label,
                            discount_markup_rubles_label,
                        ]:
                            cell.value = value
                            cell.style = number_style
                        elif param in [
                            'Стоимость объекта, руб.',
                            'Итоговая стоимость объекта, руб.',
                        ]:
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
                    [
                        'Первоначальный взнос, руб.',
                        final_property_cost * initial_payment_percent / 100,
                    ],
                    [
                        'Дата первоначального взноса',
                        mortgage_data['INITIAL_PAYMENT_DATE'].strftime(
                            '%d.%m.%Y'
                        ),
                    ],
                    [
                        'Срок ипотеки, годы',
                        int(mortgage_data['MORTGAGE_TERM_YEARS']),
                    ],
                    [
                        'Срок ипотеки, мес.',
                        int(mortgage_data['MORTGAGE_TERM']),
                    ],
                    ['Годовая ставка, %', float(mortgage_data['ANNUAL_RATE'])],
                    [
                        'Наличие льготного периода',
                        'Да'
                        if mortgage_data['HAS_GRACE_PERIOD'] == 'yes'
                        else 'Нет',
                    ],
                ]

                if mortgage_data['HAS_GRACE_PERIOD'] == 'yes':
                    mortgage_data_list.extend(
                        [
                            [
                                'Срок льготного периода, годы',
                                int(
                                    mortgage_data['GRACE_PERIOD_TERM_YEARS']
                                    or 0
                                ),
                            ],
                            [
                                'Срок льготного периода, мес.',
                                int(mortgage_data['GRACE_PERIOD_TERM'] or 0),
                            ],
                            [
                                'Годовая ставка в льготный период, %',
                                float(mortgage_data['GRACE_PERIOD_RATE']),
                            ],
                        ]
                    )

                for i, (param, value) in enumerate(
                    mortgage_data_list, start=start_row + 1
                ):
                    ws[f'A{i}'] = param
                    cell = ws[f'B{i}']

                    # Применяем форматирование к числам
                    if isinstance(value, (int, float)):
                        if param in [
                            'Срок ипотеки, годы',
                            'Срок ипотеки, мес.',
                            'Срок льготного периода, годы',
                            'Срок льготного периода, мес.',
                        ]:
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
                    grace_period_end_date_str = result[
                        'grace_period_end_date'
                    ].strftime('%d.%m.%Y')

                result_data = []

                if mortgage_data['HAS_GRACE_PERIOD'] == 'yes':
                    result_data.extend(
                        [
                            [
                                'Число платежей за льготный период',
                                result['grace_payments_count'],
                            ],
                            [
                                'Дата последнего платежа по льготному периоду',
                                grace_period_end_date_str,
                            ],
                            [
                                (
                                    'Сумма ежемесячного платежа '
                                    'во время льготного периода, '
                                    'руб.'
                                ),
                                float(result['grace_monthly_payment']),
                            ],
                            [
                                (
                                    'Сумма кредита после окончания '
                                    'льготного периода, руб.'
                                ),
                                float(result['loan_after_grace']),
                            ],
                        ]
                    )

                result_data.extend(
                    [
                        [
                            'Число платежей за основной период',
                            result['main_payments_count'],
                        ],
                        [
                            'Дата последнего платежа по ипотеке',
                            result['mortgage_end_date'].strftime('%d.%m.%Y'),
                        ],
                        [
                            (
                                'Сумма ежемесячного платежа '
                                'за основной период, руб.'
                            ),
                            float(result['main_monthly_payment']),
                        ],
                        [
                            'Сумма кредита, руб.',
                            float(result['total_loan_amount']),
                        ],
                        [
                            'Сумма переплат по кредиту, руб.',
                            float(result['total_overpayment']),
                        ],
                    ]
                )

                for i, (param, value) in enumerate(
                    result_data, start=result_start + 1
                ):
                    ws[f'A{i}'] = param
                    cell = ws[f'B{i}']

                    # Применяем форматирование к числам
                    if isinstance(value, (int, float)):
                        if param in [
                            'Число платежей за льготный период',
                            'Число платежей за основной период',
                        ]:
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

                headers = [
                    '№',
                    'Дата платежа',
                    'Сумма платежа, руб.',
                    'В том числе проценты, руб.',
                    'В том числе основной долг, руб.',
                    'Остаток долга, руб.',
                ]

                for col, header in enumerate(headers, start=1):
                    cell = ws.cell(
                        row=schedule_start + 1, column=col, value=header
                    )
                    cell.font = Font(bold=True)
                    cell.alignment = Alignment(horizontal='center')

                for row, payment in enumerate(
                    payment_schedule, start=schedule_start + 2
                ):
                    ws.cell(row=row, column=1, value=payment['payment_number'])
                    ws.cell(
                        row=row,
                        column=2,
                        value=payment['payment_date'].strftime('%d.%m.%Y'),
                    )

                    # Используем исходные числовые значения
                    for col_idx, key in enumerate(
                        [
                            'payment_amount',
                            'interest_amount',
                            'principal_amount',
                            'remaining_debt',
                        ],
                        start=3,
                    ):
                        value = payment[key]
                        # Если значение - строка, преобразуем его в число
                        if isinstance(value, str):
                            numeric_value = float(
                                value.replace(' ', '').replace(',', '.')
                            )
                        else:
                            numeric_value = float(value)
                        cell = ws.cell(
                            row=row, column=col_idx, value=numeric_value
                        )
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

    return render(request, 'mortgage/mortgage_form.html', context)


def property_cost_api(request, pk):
    """Описание метода property_cost_api.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        request: Входной параметр, влияющий на работу метода.
        pk: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    property_obj = get_object_or_404(Property, pk=pk)
    return JsonResponse(
        {
            'property_cost': str(property_obj.property_cost),
        }
    )


def calculation_list(request):
    """Список всех расчетов"""
    target_customer = _get_target_customer(request)

    if request.method == 'POST' and target_customer is not None:
        selected_ids = request.POST.getlist('calculations')
        calculations = MortgageCalculation.objects.filter(pk__in=selected_ids)

        for calculation in calculations:
            _attach_calculation_to_customer(target_customer, calculation)

        if selected_ids:
            messages.success(
                request,
                'Выбранные расчеты добавлены в карточку клиента.',
            )
        else:
            messages.info(request, 'Расчеты для добавления не выбраны.')
        return redirect('customer:detail', pk=target_customer.pk)

    calculations = (
        MortgageCalculation.objects.select_related(
            'property',
            'property__building',
            'property__building__real_estate_complex',
        )
        .all()
        .order_by('-timestamp')
    )
    linked_calculation_ids = []
    if target_customer is not None:
        linked_calculation_ids = list(
            target_customer.saved_calculations.values_list('pk', flat=True)
        )

    return render(
        request,
        'mortgage/mortgage_list.html',
        {
            'calculations': calculations,
            'target_customer': target_customer,
            'linked_calculation_ids': linked_calculation_ids,
        },
    )


@require_POST
def calculation_delete(request, pk):
    """Удаление сохраненного ипотечного расчета."""
    calculation = get_object_or_404(MortgageCalculation, pk=pk)
    calculation.delete()
    return redirect('mortgage:calculation_list')


def calculation_detail(request, pk):
    """Детальная информация о расчете"""
    calculation = get_object_or_404(
        MortgageCalculation.objects.select_related('property'), pk=pk
    )

    # Форматируем значения для отображения
    calculation.formatted_final_property_cost = format_currency(
        calculation.final_property_cost
    )
    calculation.formatted_grace_monthly_payment = (
        format_currency(calculation.grace_monthly_payment)
        if calculation.grace_monthly_payment
        else None
    )
    calculation.formatted_loan_after_grace = (
        format_currency(calculation.loan_after_grace)
        if calculation.loan_after_grace
        else None
    )
    calculation.formatted_main_monthly_payment = (
        format_currency(calculation.main_monthly_payment)
        if calculation.main_monthly_payment
        else None
    )
    calculation.formatted_total_loan_amount = (
        format_currency(calculation.total_loan_amount)
        if calculation.total_loan_amount
        else None
    )
    calculation.formatted_total_overpayment = (
        format_currency(calculation.total_overpayment)
        if calculation.total_overpayment
        else None
    )

    return render(
        request, 'mortgage/mortgage_detail.html', {'calculation': calculation}
    )
