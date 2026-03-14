from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.urls import reverse_lazy
from django.views.generic import CreateView, DetailView, ListView, UpdateView

from mortgage.utils import format_currency

from .forms import CustomerForm
from .models import Customer


class CustomerOwnedQuerysetMixin(LoginRequiredMixin):
    def get_queryset(self):
        return (
            Customer.objects.filter(user=self.request.user)
            .select_related('residence_city', 'desired_city', 'desired_district')
            .prefetch_related('desired_layouts', 'preferential_programs')
        )


class CustomerListView(CustomerOwnedQuerysetMixin, ListView):
    model = Customer
    template_name = 'customer/customer_list.html'
    context_object_name = 'customers'
    paginate_by = 20

    def get_queryset(self):
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
        context = super().get_context_data(**kwargs)
        context['search_query'] = (self.request.GET.get('q') or '').strip()
        return context


class CustomerCreateView(LoginRequiredMixin, CreateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customer/customer_form.html'

    def form_valid(self, form):
        form.instance.user = self.request.user
        return super().form_valid(form)

    def get_success_url(self):
        return reverse_lazy('customer:detail', kwargs={'pk': self.object.pk})


class CustomerDetailView(CustomerOwnedQuerysetMixin, DetailView):
    model = Customer
    template_name = 'customer/customer_detail.html'
    context_object_name = 'customer'

    def get_context_data(self, **kwargs):
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
            'max_property_cost': format_currency(max_property_cost) if max_property_cost is not None else '',
        }
        return context


class CustomerUpdateView(CustomerOwnedQuerysetMixin, UpdateView):
    model = Customer
    form_class = CustomerForm
    template_name = 'customer/customer_form.html'

    def get_success_url(self):
        return reverse_lazy('customer:detail', kwargs={'pk': self.object.pk})
