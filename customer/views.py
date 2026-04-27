from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from mortgage.utils import (
    apply_calculation_filters,
    apply_calculation_sort,
    annotate_calculation_table_values,
    build_calculation_table_headers,
    format_currency,
    get_calculation_filters,
    get_calculation_sort,
)

from .forms import CustomerForm
from .models import Customer, CustomerCalculation


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
        return (
            Customer.objects.filter(user=self.request.user)
            .select_related(
                'residence_city', 'desired_city', 'desired_district'
            )
            .prefetch_related('desired_layouts', 'preferential_programs')
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

        context['calculated'] = {
            'max_term_years': max_term_years,
            'actual_key_rate': f'{key_rate:.2f}',
            'annual_rate': f'{annual_rate:.2f}',
            'max_property_cost': format_currency(max_property_cost)
            if max_property_cost is not None
            else '',
        }
        calculation_filters = get_calculation_filters(self.request)
        calculation_sort, calculation_order = get_calculation_sort(
            self.request
        )
        customer_calculations = (
            CustomerCalculation.objects.filter(customer=customer)
            .select_related(
                'calculation',
                'calculation__property',
                'calculation__property__building',
                'calculation__property__building__real_estate_complex',
            )
        )
        customer_calculations = apply_calculation_filters(
            annotate_calculation_table_values(
                customer_calculations,
                prefix='calculation__',
            ),
            calculation_filters,
            prefix='calculation__',
        )
        customer_calculations = apply_calculation_sort(
            customer_calculations,
            calculation_sort,
            calculation_order,
            prefix='calculation__',
        )

        context['customer_calculations'] = customer_calculations
        context['calculation_filters'] = calculation_filters
        context['calculation_sort'] = calculation_sort
        context['calculation_order'] = calculation_order
        context['calculation_table_headers'] = (
            build_calculation_table_headers(self.request)
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
