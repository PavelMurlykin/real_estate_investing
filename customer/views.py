from decimal import Decimal, InvalidOperation

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Prefetch, Q
from django.urls import reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)

from bank.models import MortgageProgram
from mortgage.utils import (
    build_calculation_table_headers,
    format_currency,
    get_calculation_filters,
    get_calculation_sort,
)
from users.roles import can_view_all_private_records

from .forms import CustomerForm
from .models import Customer, CustomerCalculation, CustomerTrenchCalculation


CUSTOMER_CALCULATION_SORT_FIELDS = {
    'city': 'city_name',
    'timestamp': 'timestamp',
    'object': 'object_name',
    'cost': 'final_property_cost',
    'initial_payment': 'table_initial_payment_amount',
    'monthly_payment': 'main_monthly_payment',
    'term': 'mortgage_term',
    'rate': 'annual_rate',
}


def _parse_customer_calculation_decimal(value):
    """Return a decimal filter value or None."""
    if not value:
        return None
    try:
        return Decimal(str(value).replace(',', '.'))
    except (InvalidOperation, ValueError):
        return None


def _get_customer_calculation_property(calculation):
    """Return the property object used by a saved calculation."""
    return calculation.property


def _get_customer_calculation_city(calculation):
    """Return the city object used by a saved calculation."""
    return (
        _get_customer_calculation_property(calculation)
        .building.real_estate_complex.district.city
    )


def _get_customer_calculation_object_name(calculation):
    """Return the object name used for customer calculation sorting."""
    property_obj = _get_customer_calculation_property(calculation)
    return property_obj.building.real_estate_complex.name


def _get_last_trench_monthly_payment(calculation):
    """Return the cumulative monthly payment of the last trench."""
    trenches = list(calculation.trenches.all())
    if not trenches:
        return Decimal('0')
    return trenches[-1].monthly_payment


def _prepare_customer_calculation_link(
    link,
    program_type,
    program_label,
    monthly_payment,
):
    """Attach shared table attributes to a customer calculation link."""
    calculation = link.calculation
    link.program_type = program_type
    link.program_label = program_label
    link.table_initial_payment_amount = (
        calculation.final_property_cost
        * calculation.initial_payment_percent
        / Decimal('100')
    )
    link.main_monthly_payment = monthly_payment
    link.timestamp = calculation.timestamp
    link.city = _get_customer_calculation_city(calculation)
    link.city_name = link.city.name
    link.object_name = _get_customer_calculation_object_name(calculation)
    link.final_property_cost = calculation.final_property_cost
    link.mortgage_term = calculation.mortgage_term
    link.annual_rate = calculation.annual_rate
    return link


def _build_customer_calculation_links(
    market_customer_calculations,
    trench_customer_calculations,
):
    """Return normalized calculation links for the customer detail table."""
    rows = [
        _prepare_customer_calculation_link(
            customer_calculation,
            'market',
            'Рыночная ипотека',
            customer_calculation.calculation.main_monthly_payment,
        )
        for customer_calculation in market_customer_calculations
    ]
    rows.extend(
        _prepare_customer_calculation_link(
            customer_calculation,
            'trench',
            'Траншевая ипотека',
            _get_last_trench_monthly_payment(
                customer_calculation.calculation
            ),
        )
        for customer_calculation in trench_customer_calculations
    )
    return rows


def _apply_customer_calculation_decimal_range(
    rows,
    filters,
    row_attribute,
    filter_name,
):
    """Filter normalized customer calculation rows by decimal range."""
    from_value = _parse_customer_calculation_decimal(
        filters.get(f'{filter_name}_from')
    )
    if from_value is not None:
        rows = [
            row
            for row in rows
            if getattr(row, row_attribute) >= from_value
        ]

    to_value = _parse_customer_calculation_decimal(
        filters.get(f'{filter_name}_to')
    )
    if to_value is not None:
        rows = [
            row
            for row in rows
            if getattr(row, row_attribute) <= to_value
        ]

    return rows


def _apply_customer_calculation_filters(rows, filters):
    """Filter normalized customer calculation rows."""
    city = filters.get('city')
    if city:
        rows = [row for row in rows if str(row.city.pk) == city]

    search = (filters.get('q') or '').casefold()
    if search:
        rows = [
            row
            for row in rows
            if search in row.calculation.property.apartment_number.casefold()
            or search in row.object_name.casefold()
        ]

    rows = _apply_customer_calculation_decimal_range(
        rows, filters, 'final_property_cost', 'cost'
    )
    rows = _apply_customer_calculation_decimal_range(
        rows, filters, 'table_initial_payment_amount', 'initial_payment'
    )
    rows = _apply_customer_calculation_decimal_range(
        rows, filters, 'main_monthly_payment', 'monthly_payment'
    )
    rows = _apply_customer_calculation_decimal_range(
        rows, filters, 'annual_rate', 'rate'
    )

    term_from = _parse_customer_calculation_decimal(
        filters.get('term_from')
    )
    if term_from is not None:
        rows = [
            row for row in rows if row.mortgage_term >= term_from * 12
        ]

    term_to = _parse_customer_calculation_decimal(filters.get('term_to'))
    if term_to is not None:
        rows = [row for row in rows if row.mortgage_term <= term_to * 12]

    return rows


def _get_customer_calculation_sort_value(row, sort):
    """Return a normalized sort value for a customer calculation row."""
    value = getattr(row, CUSTOMER_CALCULATION_SORT_FIELDS[sort])
    if isinstance(value, str):
        return value.casefold()
    return value


def _sort_customer_calculation_rows(rows, sort, order):
    """Sort normalized customer calculation rows."""
    return sorted(
        rows,
        key=lambda row: _get_customer_calculation_sort_value(row, sort),
        reverse=order == 'desc',
    )


def _build_customer_calculation_city_choices(rows):
    """Return city choices available in normalized customer calculations."""
    cities = {
        str(row.city.pk): row.city.name
        for row in rows
    }
    return [
        {'id': city_id, 'name': city_name}
        for city_id, city_name in sorted(
            cities.items(), key=lambda item: item[1].casefold()
        )
    ]


class CustomerOwnedQuerysetMixin(LoginRequiredMixin):
    """Описание класса CustomerOwnedQuerysetMixin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    def get_queryset(self):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        queryset = Customer.objects.all()
        if not can_view_all_private_records(self.request.user):
            queryset = queryset.filter(user=self.request.user)

        return (
            queryset
            .select_related(
                'residence_city',
                'desired_city',
                'desired_city__region',
                'desired_district',
            )
            .prefetch_related(
                'desired_layouts',
                Prefetch(
                    'preferential_programs',
                    queryset=MortgageProgram.objects.prefetch_related(
                        'regional_credit_limits'
                    ),
                ),
            )
        )


class CustomerListView(CustomerOwnedQuerysetMixin, ListView):
    """Описание класса CustomerListView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Customer
    template_name = 'customer/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20

    def get_queryset(self):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        queryset = super().get_queryset().order_by('-created_at')
        search = (self.request.GET.get('q') or '').strip()
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        """Описание метода get_context_data.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        context = super().get_context_data(**kwargs)
        context['search_query'] = (self.request.GET.get('q') or '').strip()
        return context


class CustomerCreateView(LoginRequiredMixin, CreateView):
    """Описание класса CustomerCreateView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Customer
    form_class = CustomerForm
    template_name = 'customer/customer_form.html'

    def form_valid(self, form):
        """Описание метода form_valid.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            form: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        """Описание метода get_success_url.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return reverse_lazy('customer:detail', kwargs={'pk': self.object.pk})


class CustomerDetailView(CustomerOwnedQuerysetMixin, DetailView):
    """Описание класса CustomerDetailView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Customer
    template_name = 'customer/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
        """Описание метода get_context_data.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        context = super().get_context_data(**kwargs)

        customer = self.object
        max_term_years = customer.get_max_mortgage_term_years()
        key_rate = customer.get_actual_cbr_key_rate()
        annual_rate = customer.get_effective_annual_rate()
        max_property_cost = customer.calculate_max_property_cost(
            annual_rate=annual_rate,
            max_term_years=max_term_years,
        )
        has_preferential_program = (
            customer.has_selected_preferential_program()
        )
        preferential_max_property_cost = None
        preferential_credit_limit = None
        if has_preferential_program:
            preferential_credit_limit = (
                customer.get_preferential_credit_limit()
            )
            preferential_max_property_cost = (
                customer.calculate_max_property_cost(
                    annual_rate=Customer.DEFAULT_PREFERENTIAL_ANNUAL_RATE,
                    max_term_years=max_term_years,
                    credit_limit=preferential_credit_limit,
                )
            )

        context['calculated'] = {
            'max_term_years': max_term_years,
            'actual_key_rate': f'{key_rate:.2f}',
            'annual_rate': f'{annual_rate:.2f}',
            'max_property_cost': format_currency(max_property_cost)
            if max_property_cost is not None
            else '',
            'has_preferential_program': has_preferential_program,
            'preferential_annual_rate': (
                f'{Customer.DEFAULT_PREFERENTIAL_ANNUAL_RATE:g}'
            ),
            'preferential_max_property_cost': format_currency(
                preferential_max_property_cost
            )
            if preferential_max_property_cost is not None
            else '',
            'preferential_credit_limit': format_currency(
                preferential_credit_limit
            )
            if preferential_credit_limit is not None
            else '',
        }
        calculation_filters = get_calculation_filters(self.request)
        calculation_sort, calculation_order = get_calculation_sort(
            self.request
        )
        market_customer_calculations = CustomerCalculation.objects.filter(
            customer=customer
        )
        trench_customer_calculations = (
            CustomerTrenchCalculation.objects.filter(customer=customer)
        )
        if not can_view_all_private_records(self.request.user):
            market_customer_calculations = market_customer_calculations.filter(
                calculation__user=self.request.user
            )
            trench_customer_calculations = (
                trench_customer_calculations.filter(
                    calculation__user=self.request.user
                )
            )
        market_customer_calculations = (
            market_customer_calculations
            .select_related(
                'calculation',
                'calculation__property',
                'calculation__property__layout',
                'calculation__property__building',
                'calculation__property__building__real_estate_complex',
                (
                    'calculation__property__building'
                    '__real_estate_complex__district'
                ),
                (
                    'calculation__property__building'
                    '__real_estate_complex__district__city'
                ),
            )
        )
        trench_customer_calculations = (
            trench_customer_calculations
            .select_related(
                'calculation',
                'calculation__property',
                'calculation__property__layout',
                'calculation__property__building',
                'calculation__property__building__real_estate_complex',
                (
                    'calculation__property__building'
                    '__real_estate_complex__district'
                ),
                (
                    'calculation__property__building'
                    '__real_estate_complex__district__city'
                ),
            )
            .prefetch_related('calculation__trenches')
        )
        customer_calculation_rows = _build_customer_calculation_links(
            market_customer_calculations,
            trench_customer_calculations,
        )
        calculation_cities = _build_customer_calculation_city_choices(
            customer_calculation_rows
        )
        customer_calculations = _apply_customer_calculation_filters(
            customer_calculation_rows,
            calculation_filters,
        )
        customer_calculations = _sort_customer_calculation_rows(
            customer_calculations,
            calculation_sort,
            calculation_order,
        )

        context['customer_calculations'] = customer_calculations
        context['calculation_cities'] = calculation_cities
        context['calculation_filters'] = calculation_filters
        context['calculation_sort'] = calculation_sort
        context['calculation_order'] = calculation_order
        context['calculation_filter_reset_url'] = self.request.path
        context['calculation_table_headers'] = (
            build_calculation_table_headers(
                self.request,
                excluded_fields=('timestamp',),
            )
        )
        return context


class CustomerUpdateView(CustomerOwnedQuerysetMixin, UpdateView):
    """Описание класса CustomerUpdateView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Customer
    form_class = CustomerForm
    template_name = 'customer/customer_form.html'

    def get_success_url(self):
        """Описание метода get_success_url.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return reverse_lazy('customer:detail', kwargs={'pk': self.object.pk})


class CustomerDeleteView(CustomerOwnedQuerysetMixin, DeleteView):
    """Удаляет клиента текущего пользователя."""

    model = Customer
    success_url = reverse_lazy('customer:list')


class CustomerCalculationDeleteView(LoginRequiredMixin, DeleteView):
    """Удаляет связь клиента с сохраненным ипотечным расчетом."""

    model = CustomerCalculation

    def get_queryset(self):
        """Возвращает связи расчетов для клиентов текущего пользователя."""
        queryset = CustomerCalculation.objects.all()
        if not can_view_all_private_records(self.request.user):
            queryset = queryset.filter(
                customer__user=self.request.user,
                calculation__user=self.request.user,
            )
        return queryset

    def get_success_url(self):
        """Возвращает пользователя в карточку клиента после удаления связи."""
        return reverse_lazy(
            'customer:detail', kwargs={'pk': self.object.customer_id}
        )


class CustomerTrenchCalculationDeleteView(LoginRequiredMixin, DeleteView):
    """Delete a customer link to a saved trench mortgage calculation."""

    model = CustomerTrenchCalculation

    def get_queryset(self):
        """Return trench calculation links available to the current user."""
        queryset = CustomerTrenchCalculation.objects.all()
        if not can_view_all_private_records(self.request.user):
            queryset = queryset.filter(
                customer__user=self.request.user,
                calculation__user=self.request.user,
            )
        return queryset

    def get_success_url(self):
        """Return the user to the customer detail after link deletion."""
        return reverse_lazy(
            'customer:detail', kwargs={'pk': self.object.customer_id}
        )
