from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from math import pow

import openpyxl
from dateutil.relativedelta import relativedelta
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from openpyxl.styles import Alignment, Font, NamedStyle
from openpyxl.utils import get_column_letter

from mortgage.utils import format_currency
from property.models import Property

from .forms import TrenchMortgageForm
from .models import Trench, TrenchMortgageCalculation

SESSION_KEY = "trench_mortgage_data"


def trench_mortgage_calculator(request):
    initial = {}
    property_id = request.GET.get("property_id")
    if property_id and str(property_id).isdigit():
        initial["PROPERTY"] = int(property_id)

    if request.method == "POST":
        form = TrenchMortgageForm(request.POST)
        if form.is_valid():
            cleaned_data = form.cleaned_data
            request.session[SESSION_KEY] = {
                "property_id": cleaned_data["PROPERTY"].id,
                "discount_markup_type": cleaned_data["DISCOUNT_MARKUP_TYPE"],
                "discount_markup_value": str(cleaned_data["DISCOUNT_MARKUP_VALUE"] or 0),
                "initial_payment_percent": str(cleaned_data["INITIAL_PAYMENT_PERCENT"]),
                "initial_payment_date": cleaned_data["INITIAL_PAYMENT_DATE"].isoformat(),
                "mortgage_term": int(cleaned_data["MORTGAGE_TERM"]),
                "trench_count": int(cleaned_data["TRENCH_COUNT"]),
            }
            return render(
                request,
                "trench_mortgage/trench_form.html",
                _build_trench_context(request.session[SESSION_KEY]),
            )
    else:
        form = TrenchMortgageForm(initial=initial)

    return render(request, "trench_mortgage/calculator.html", {"form": form})


def calculate_trench_mortgage(request):
    if request.method != "POST":
        return redirect("trench_mortgage:trench_mortgage_calculator")

    mortgage_data = _load_session_mortgage_data(request)
    if not mortgage_data:
        return redirect("trench_mortgage:trench_mortgage_calculator")

    trench_entries, input_rows, errors = _parse_trench_inputs(
        request.POST,
        mortgage_data["trench_count"],
    )

    context = _build_trench_context(mortgage_data)
    context["trench_input_rows"] = input_rows

    if errors:
        context["error_message"] = " ".join(errors)
        return render(request, "trench_mortgage/trench_form.html", context)

    calculation, calc_errors = _calculate_trench_mortgage(mortgage_data, trench_entries)
    if calc_errors:
        context["error_message"] = " ".join(calc_errors)
        return render(request, "trench_mortgage/trench_form.html", context)

    if "export" in request.POST:
        return _export_trench_excel(calculation)

    _save_trench_calculation(calculation)
    context["result"] = _format_result(calculation)

    return render(request, "trench_mortgage/trench_form.html", context)


def _build_trench_context(mortgage_data):
    property_obj = mortgage_data.get("property_obj")
    if not property_obj:
        property_obj = get_object_or_404(Property, pk=mortgage_data["property_id"])

    return {
        "trench_count": int(mortgage_data["trench_count"]),
        "property_obj": property_obj,
    }


def _load_session_mortgage_data(request):
    raw = request.session.get(SESSION_KEY)
    if not raw:
        return None

    property_ref = raw.get("property_id", raw.get("PROPERTY"))
    if hasattr(property_ref, "id"):
        property_id = property_ref.id
    else:
        try:
            property_id = int(property_ref)
        except (TypeError, ValueError):
            return None

    property_obj = Property.objects.filter(pk=property_id).first()
    if not property_obj:
        return None

    raw_initial_date = raw.get("initial_payment_date", raw.get("INITIAL_PAYMENT_DATE"))
    if isinstance(raw_initial_date, date):
        initial_payment_date = raw_initial_date
    else:
        try:
            initial_payment_date = datetime.strptime(str(raw_initial_date), "%Y-%m-%d").date()
        except (TypeError, ValueError):
            return None

    try:
        discount_markup_value = Decimal(str(raw.get("discount_markup_value", raw.get("DISCOUNT_MARKUP_VALUE", 0))))
        initial_payment_percent = Decimal(str(raw.get("initial_payment_percent", raw.get("INITIAL_PAYMENT_PERCENT", 0))))
        mortgage_term = int(raw.get("mortgage_term", raw.get("MORTGAGE_TERM", 0)))
        trench_count = int(raw.get("trench_count", raw.get("TRENCH_COUNT", 0)))
    except (TypeError, ValueError, InvalidOperation):
        return None

    if discount_markup_value < 0:
        return None
    if initial_payment_percent < 0 or initial_payment_percent > 100:
        return None
    if mortgage_term < 1 or mortgage_term > 50:
        return None
    if trench_count < 1 or trench_count > 5:
        return None

    return {
        "property_id": property_id,
        "property_obj": property_obj,
        "discount_markup_type": raw.get("discount_markup_type", raw.get("DISCOUNT_MARKUP_TYPE", "discount")),
        "discount_markup_value": discount_markup_value,
        "initial_payment_percent": initial_payment_percent,
        "initial_payment_date": initial_payment_date,
        "mortgage_term": mortgage_term,
        "trench_count": trench_count,
    }


def _parse_trench_inputs(post_data, trench_count):
    errors = []
    input_rows = []
    entries = []
    percent_sum = Decimal("0")

    for idx in range(1, trench_count + 1):
        trench_date_raw = str(post_data.get(f"trench_date_{idx}", "")).strip()
        trench_percent_raw = str(post_data.get(f"trench_percent_{idx}", "")).strip()
        annual_rate_raw = str(post_data.get(f"annual_rate_{idx}", "")).strip()

        input_rows.append(
            {
                "number": idx,
                "trench_date": trench_date_raw,
                "trench_percent": trench_percent_raw,
                "annual_rate": annual_rate_raw,
            }
        )

        if not trench_date_raw:
            errors.append(f"Не заполнена дата транша №{idx}.")
            continue
        if not annual_rate_raw:
            errors.append(f"Не заполнена ставка транша №{idx}.")
            continue

        try:
            trench_date = datetime.strptime(trench_date_raw, "%Y-%m-%d").date()
        except ValueError:
            errors.append(f"Неверный формат даты транша №{idx}.")
            continue

        try:
            annual_rate = Decimal(annual_rate_raw.replace(",", "."))
        except (InvalidOperation, AttributeError):
            errors.append(f"Неверная ставка транша №{idx}.")
            continue

        if annual_rate < 0:
            errors.append(f"Ставка транша №{idx} не может быть отрицательной.")
            continue

        if idx < trench_count:
            if not trench_percent_raw:
                errors.append(f"Не заполнен процент транша №{idx}.")
                continue
            try:
                trench_percent = Decimal(trench_percent_raw.replace(",", "."))
            except (InvalidOperation, AttributeError):
                errors.append(f"Неверный процент транша №{idx}.")
                continue

            if trench_percent <= 0:
                errors.append(f"Процент транша №{idx} должен быть больше 0.")
                continue

            percent_sum += trench_percent
        else:
            trench_percent = None

        entries.append(
            {
                "number": idx,
                "trench_date": trench_date,
                "trench_percent": trench_percent,
                "annual_rate": annual_rate,
            }
        )

    if errors:
        return [], input_rows, errors

    if len(entries) != trench_count:
        return [], input_rows, ["Некорректные данные траншей."]

    if trench_count == 1:
        last_percent = Decimal("100")
    else:
        last_percent = Decimal("100") - percent_sum

    if last_percent <= 0:
        return [], input_rows, ["Сумма процентов траншей превышает или равна 100%."]

    entries[-1]["trench_percent"] = last_percent.quantize(Decimal("0.01"))
    input_rows[-1]["trench_percent"] = f"{entries[-1]['trench_percent']:.2f}"

    for prev, current in zip(entries, entries[1:]):
        if current["trench_date"] < prev["trench_date"]:
            return [], input_rows, ["Даты траншей должны идти по возрастанию."]

    return entries, input_rows, []


def _calculate_trench_mortgage(mortgage_data, trench_entries):
    errors = []

    property_obj = mortgage_data["property_obj"]
    property_cost = float(property_obj.property_cost)
    discount_markup_value = float(mortgage_data["discount_markup_value"])

    if mortgage_data["discount_markup_type"] == "discount":
        final_property_cost = property_cost * (1 - discount_markup_value / 100)
    else:
        final_property_cost = property_cost * (1 + discount_markup_value / 100)

    initial_payment_percent = float(mortgage_data["initial_payment_percent"])
    initial_payment = final_property_cost * initial_payment_percent / 100
    loan_amount = final_property_cost - initial_payment

    initial_payment_date = mortgage_data["initial_payment_date"]
    mortgage_end_date = initial_payment_date + relativedelta(years=mortgage_data["mortgage_term"])

    trenches_result = []
    total_overpayment = 0.0
    cumulative_amount = 0.0

    for trench in trench_entries:
        trench_date = trench["trench_date"]
        if trench_date < initial_payment_date:
            errors.append(
                f"Дата транша №{trench['number']} не может быть раньше даты первоначального взноса."
            )
            continue

        months_remaining = _calculate_months_remaining(trench_date, mortgage_end_date)
        if months_remaining <= 0:
            errors.append(
                f"Для транша №{trench['number']} нет месяцев до конца срока ипотеки."
            )
            continue

        trench_percent = float(trench["trench_percent"])
        trench_amount = loan_amount * trench_percent / 100
        annual_rate = float(trench["annual_rate"])
        monthly_rate = annual_rate / 100 / 12

        if monthly_rate > 0:
            factor = pow(1 + monthly_rate, months_remaining)
            monthly_payment = trench_amount * monthly_rate * factor / (factor - 1)
        else:
            monthly_payment = trench_amount / months_remaining

        overpayment = (monthly_payment * months_remaining) - trench_amount

        cumulative_amount += trench_amount
        remaining_debt = max(loan_amount - cumulative_amount, 0)
        total_overpayment += overpayment

        trenches_result.append(
            {
                "number": trench["number"],
                "date": trench_date,
                "percent": trench_percent,
                "amount": trench_amount,
                "annual_rate": annual_rate,
                "monthly_payment": monthly_payment,
                "payments_count": months_remaining,
                "remaining_debt": remaining_debt,
                "overpayment": overpayment,
            }
        )

    if errors:
        return None, errors

    calculation = {
        "property_obj": property_obj,
        "property_cost": property_cost,
        "discount_markup_type": mortgage_data["discount_markup_type"],
        "discount_markup_value": discount_markup_value,
        "final_property_cost": final_property_cost,
        "initial_payment_percent": initial_payment_percent,
        "initial_payment": initial_payment,
        "initial_payment_date": initial_payment_date,
        "mortgage_term": mortgage_data["mortgage_term"],
        "mortgage_end_date": mortgage_end_date,
        "trench_count": mortgage_data["trench_count"],
        "total_loan_amount": loan_amount,
        "total_overpayment": total_overpayment,
        "trenches": trenches_result,
    }

    return calculation, []


def _calculate_months_remaining(start_date, end_date):
    months = (end_date.year - start_date.year) * 12 + (end_date.month - start_date.month)
    if end_date.day < start_date.day:
        months -= 1
    return months


def _format_result(calculation):
    formatted = {
        "final_property_cost": format_currency(calculation["final_property_cost"]),
        "initial_payment": format_currency(calculation["initial_payment"]),
        "initial_payment_date": calculation["initial_payment_date"].strftime("%d.%m.%Y"),
        "total_loan_amount": format_currency(calculation["total_loan_amount"]),
        "total_overpayment": format_currency(calculation["total_overpayment"]),
        "trenches": [],
    }

    for trench in calculation["trenches"]:
        formatted["trenches"].append(
            {
                "number": trench["number"],
                "date": trench["date"].strftime("%d.%m.%Y"),
                "percent": f"{trench['percent']:.2f}",
                "amount": format_currency(trench["amount"]),
                "annual_rate": f"{trench['annual_rate']:.2f}",
                "monthly_payment": format_currency(trench["monthly_payment"]),
                "payments_count": trench["payments_count"],
                "remaining_debt": format_currency(trench["remaining_debt"]),
                "overpayment": format_currency(trench["overpayment"]),
            }
        )

    return formatted


def _save_trench_calculation(calculation):
    calc_obj = TrenchMortgageCalculation.objects.create(
        property=calculation["property_obj"],
        final_property_cost=Decimal(str(calculation["final_property_cost"])),
        initial_payment_percent=Decimal(str(calculation["initial_payment_percent"])),
        initial_payment_date=calculation["initial_payment_date"],
        mortgage_term=calculation["mortgage_term"],
        trench_count=calculation["trench_count"],
        total_loan_amount=Decimal(str(calculation["total_loan_amount"])),
        total_overpayment=Decimal(str(calculation["total_overpayment"])),
    )

    trench_objects = []
    for trench in calculation["trenches"]:
        trench_objects.append(
            Trench(
                calculation=calc_obj,
                trench_number=trench["number"],
                trench_date=trench["date"],
                trench_percent=Decimal(str(trench["percent"])),
                trench_amount=Decimal(str(trench["amount"])),
                annual_rate=Decimal(str(trench["annual_rate"])),
                monthly_payment=Decimal(str(trench["monthly_payment"])),
                payments_count=trench["payments_count"],
                remaining_debt=Decimal(str(trench["remaining_debt"])),
            )
        )

    if trench_objects:
        Trench.objects.bulk_create(trench_objects)


def _export_trench_excel(calculation):
    response = HttpResponse(
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    response["Content-Disposition"] = 'attachment; filename="trench_mortgage_calculation.xlsx"'

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Траншевая ипотека"

    number_style = NamedStyle(name="number_style")
    number_style.number_format = "# ##0.00"
    wb.add_named_style(number_style)

    integer_style = NamedStyle(name="integer_style")
    integer_style.number_format = "# ##0"
    wb.add_named_style(integer_style)

    ws.merge_cells("A1:B1")
    ws["A1"] = "Траншевая ипотека - результаты расчета"
    ws["A1"].font = Font(bold=True, size=14)
    ws["A1"].alignment = Alignment(horizontal="center")

    property_obj = calculation["property_obj"]
    property_rows = [
        ["Застройщик", property_obj.building.real_estate_complex.developer.name],
        ["Город", property_obj.building.real_estate_complex.district.city.name],
        ["Название ЖК", property_obj.building.real_estate_complex.name],
        ["Корпус", property_obj.building.number],
        ["№ квартиры", property_obj.apartment_number],
        ["Площадь", float(property_obj.area)],
        ["Этаж", property_obj.floor],
        ["Стоимость объекта, руб.", calculation["property_cost"]],
        [
            "Тип изменения цены",
            "Скидка" if calculation["discount_markup_type"] == "discount" else "Удорожание",
        ],
        ["Значение, %", calculation["discount_markup_value"]],
        ["Итоговая стоимость объекта, руб.", calculation["final_property_cost"]],
    ]

    row = 3
    ws[f"A{row}"] = "Данные объекта"
    ws[f"A{row}"].font = Font(bold=True)
    row += 1

    for label, value in property_rows:
        ws[f"A{row}"] = label
        cell = ws[f"B{row}"]
        cell.value = value
        if isinstance(value, int):
            cell.style = integer_style
        elif isinstance(value, float):
            cell.style = number_style
        cell.alignment = Alignment(horizontal="center")
        row += 1

    row += 1
    ws[f"A{row}"] = "Параметры траншевой ипотеки"
    ws[f"A{row}"].font = Font(bold=True)
    row += 1

    mortgage_rows = [
        ["Первоначальный взнос, %", calculation["initial_payment_percent"]],
        ["Первоначальный взнос, руб.", calculation["initial_payment"]],
        ["Дата первоначального взноса", calculation["initial_payment_date"].strftime("%d.%m.%Y")],
        ["Срок кредита, лет", calculation["mortgage_term"]],
        ["Количество траншей", calculation["trench_count"]],
    ]

    for label, value in mortgage_rows:
        ws[f"A{row}"] = label
        cell = ws[f"B{row}"]
        cell.value = value
        if isinstance(value, int):
            cell.style = integer_style
        elif isinstance(value, float):
            cell.style = number_style
        cell.alignment = Alignment(horizontal="center")
        row += 1

    row += 1
    ws[f"A{row}"] = "Транши"
    ws[f"A{row}"].font = Font(bold=True)
    row += 1

    headers = [
        "№",
        "Дата",
        "Сумма, %",
        "Сумма, руб.",
        "Ставка, %",
        "Ежемесячный платеж, руб.",
        "Число платежей",
        "Остаток долга, руб.",
        "Переплата, руб.",
    ]

    for col, header in enumerate(headers, start=1):
        cell = ws.cell(row=row, column=col, value=header)
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")

    row += 1
    for trench in calculation["trenches"]:
        ws.cell(row=row, column=1, value=trench["number"]).style = integer_style
        ws.cell(row=row, column=2, value=trench["date"].strftime("%d.%m.%Y"))

        values = [
            trench["percent"],
            trench["amount"],
            trench["annual_rate"],
            trench["monthly_payment"],
            trench["payments_count"],
            trench["remaining_debt"],
            trench["overpayment"],
        ]

        for col_offset, value in enumerate(values, start=3):
            cell = ws.cell(row=row, column=col_offset, value=float(value))
            cell.style = integer_style if col_offset == 7 else number_style
            cell.alignment = Alignment(horizontal="center")

        row += 1

    row += 1
    ws[f"A{row}"] = "Итоги"
    ws[f"A{row}"].font = Font(bold=True)
    row += 1

    totals = [
        ["Сумма кредита, руб.", calculation["total_loan_amount"]],
        ["Сумма переплаты, руб.", calculation["total_overpayment"]],
    ]

    for label, value in totals:
        ws[f"A{row}"] = label
        cell = ws[f"B{row}"]
        cell.value = float(value)
        cell.style = number_style
        cell.alignment = Alignment(horizontal="center")
        row += 1

    for column in ws.columns:
        max_length = 0
        column_letter = get_column_letter(column[0].column)
        for cell in column:
            if cell.value is not None:
                max_length = max(max_length, len(str(cell.value)))
        ws.column_dimensions[column_letter].width = min(max_length + 2, 60)

    wb.save(response)
    return response
