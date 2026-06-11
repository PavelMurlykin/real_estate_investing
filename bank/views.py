from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import DecimalField, ExpressionWrapper, F, Window
from django.db.models.functions import Lead
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.views.generic import TemplateView

from property.views import BaseCatalogView, CatalogModelConfig

from .forms import BankForm, BankProgramFormSet
from .key_rate_sync import KeyRateSyncError, sync_key_rates
from .mortgage_offer_sync import (
    BankMortgageSyncError,
    sync_bank_mortgage_offers,
)
from .models import (
    Bank,
    BankProgram,
    KeyRate,
    MortgageProgram,
    MortgageProgramAlias,
    MortgageProgramRegionalCreditLimit,
)


class BankCatalogView(BaseCatalogView):
    """Catalog view for bank dictionaries and mortgage settings."""

    template_name = 'bank/catalog_form.html'
    section_title = 'Банки'
    url_name = 'bank:catalog'
    default_model_key = 'bank'
    bank_page_size = 10
    model_configs = (
        CatalogModelConfig(
            key='bank',
            model=Bank,
            form_fields=('name', 'logo_url'),
            table_fields=('name',),
            order_by=('name',),
        ),
        CatalogModelConfig(
            key='mortgage_program',
            model=MortgageProgram,
            form_fields=(
                'name',
                'condition',
                'is_preferential',
                'credit_limit',
            ),
            table_fields=(
                'name',
                'condition',
                'is_preferential',
                'credit_limit',
            ),
            order_by=('name',),
        ),
        CatalogModelConfig(
            key='mortgage_program_regional_credit_limit',
            model=MortgageProgramRegionalCreditLimit,
            form_fields=('mortgage_program', 'region', 'credit_limit'),
            table_fields=('mortgage_program', 'region', 'credit_limit'),
            order_by=('mortgage_program__name', 'region__name'),
            select_related=('mortgage_program', 'region'),
        ),
        CatalogModelConfig(
            key='mortgage_program_alias',
            model=MortgageProgramAlias,
            form_fields=('mortgage_program', 'source_name', 'source'),
            table_fields=(
                'mortgage_program',
                'source_name',
                'normalized_name',
                'source',
            ),
            order_by=('mortgage_program__name', 'source_name'),
            select_related=('mortgage_program',),
        ),
        CatalogModelConfig(
            key='bank_program',
            model=BankProgram,
            form_fields=(
                'bank',
                'mortgage_program',
                'interest_rate',
                'minimum_initial_payment_percent',
                'maximum_loan_term_years',
            ),
            table_fields=(
                'bank',
                'mortgage_program',
                'interest_rate',
                'minimum_initial_payment_percent',
                'maximum_loan_term_years',
            ),
            order_by=('bank__name', 'mortgage_program__name'),
            select_related=('bank', 'mortgage_program'),
        ),
    )

    def post(self, request, *args, **kwargs):
        """Handle bank catalog updates and regular catalog actions."""
        config = self.get_config()
        action = request.POST.get('action', 'save')
        if config.key == 'bank' and action == 'sync_bank_mortgage_offers':
            return self.handle_bank_mortgage_sync()
        if (
            config.key == 'bank'
            and action == 'sync_existing_bank_mortgage_offers'
        ):
            return self.handle_bank_mortgage_sync(update_bank_registry=False)
        if config.key == 'bank' and action == 'save':
            return redirect('bank:bank_create')

        return super().post(request, *args, **kwargs)

    def handle_bank_mortgage_sync(self, update_bank_registry=True):
        """Synchronize bank mortgage offer data from the external source."""
        sync_label = (
            'данные банков'
            if update_bank_registry
            else 'ипотечные программы банков'
        )
        try:
            result = sync_bank_mortgage_offers(
                update_bank_registry=update_bank_registry
            )
        except BankMortgageSyncError as error:
            messages.error(
                self.request,
                f'Не удалось обновить {sync_label}: {error}',
            )
        else:
            success_label = (
                'Обновление данных банков'
                if update_bank_registry
                else 'Обновление ипотечных программ банков'
            )
            messages.success(
                self.request,
                (
                    f'{success_label} завершено: '
                    f'создано={result["created"]}, '
                    f'обновлено={result["updated"]}, '
                    f'обработано={result["processed"]}, '
                    'эталонных программ='
                    f'{result.get("reference_programs_processed", 0)}, '
                    'алиасов программ='
                    f'{result.get("reference_program_aliases_created", 0)}.'
                ),
            )
            for warning in result.get('warnings', []):
                messages.warning(self.request, warning)

        return redirect(self.get_model_url('bank'))

    def _safe_decimal(self, value):
        """Parse decimal filter values without raising validation errors."""
        if value in (None, ''):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def build_form(self, config, data=None, instance=None):
        """Build a catalog form, using a dedicated form for banks."""
        if config.key == 'bank':
            form = BankForm(data=data, instance=instance)
            self._apply_form_control_classes(form)
            return form

        return super().build_form(config, data=data, instance=instance)

    def _apply_form_control_classes(self, form):
        """Apply Bootstrap classes to a Django form."""
        for field in form.fields.values():
            widget = field.widget
            if not hasattr(widget, 'attrs'):
                continue

            existing_class = widget.attrs.get('class', '')
            widget.attrs['class'] = f'{existing_class} form-control'.strip()

    def get_sort_field_map(self, config):
        """Return sortable fields for bank catalog tables."""
        if config.key == 'bank':
            return {'name': 'name'}
        if config.key == 'bank_program':
            return {
                'bank': 'bank__name',
                'mortgage_program': 'mortgage_program__name',
                'interest_rate': 'interest_rate',
                'minimum_initial_payment_percent': (
                    'minimum_initial_payment_percent'
                ),
                'maximum_loan_term_years': 'maximum_loan_term_years',
            }
        if config.key == 'mortgage_program_regional_credit_limit':
            return {
                'mortgage_program': 'mortgage_program__name',
                'region': 'region__name',
                'credit_limit': 'credit_limit',
            }
        return {}

    def get_queryset(self, config):
        """Return filtered and sorted catalog queryset."""
        queryset = config.model.objects.all()
        if config.select_related:
            queryset = queryset.select_related(*config.select_related)

        sort_by = self.request.GET.get('sort_by')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        sort_prefix = '-' if sort_dir == 'desc' else ''

        if config.key == 'bank':
            name = (self.request.GET.get('filter_name') or '').strip()
            if name:
                queryset = queryset.filter(name__icontains=name)

            bank_scope = self.request.GET.get('filter_bank_scope', 'all')
            if bank_scope == 'with_programs':
                queryset = queryset.filter(
                    mortgage_programs__isnull=False,
                ).distinct()

            sort_field = self.get_sort_field_map(config).get(sort_by)
            if sort_field:
                return queryset.order_by(f'{sort_prefix}{sort_field}')
            return queryset.order_by(*config.order_by)

        if config.key == 'bank_program':
            bank_id = self.request.GET.get('filter_bank')
            program_id = self.request.GET.get('filter_program')

            if bank_id and bank_id.isdecimal():
                queryset = queryset.filter(bank_id=bank_id)
            if program_id:
                queryset = queryset.filter(mortgage_program_id=program_id)

            sort_field = self.get_sort_field_map(config).get(sort_by)
            if sort_field:
                return queryset.order_by(f'{sort_prefix}{sort_field}')
            return queryset.order_by(*config.order_by)

        if config.key == 'mortgage_program_regional_credit_limit':
            sort_field = self.get_sort_field_map(config).get(sort_by)
            if sort_field:
                return queryset.order_by(f'{sort_prefix}{sort_field}')
            return queryset.order_by(*config.order_by)

        return queryset.order_by(*config.order_by)

    def get_bank_page(self, config):
        """Return the current page of banks."""
        paginator = Paginator(self.get_queryset(config), self.bank_page_size)
        return paginator.get_page(self.request.GET.get('page'))

    def get_bank_selected_url(self, bank):
        """Build a URL that selects a bank in the catalog."""
        params = self.request.GET.copy()
        params['model'] = 'bank'
        params['selected_bank'] = str(bank.pk)
        params.pop('edit', None)
        return f'?{params.urlencode()}'

    def build_rows(self, config, columns):
        """Build table rows with bank-specific actions when needed."""
        if config.key != 'bank':
            return super().build_rows(config, columns)

        rows = []
        for bank in self.get_bank_page(config).object_list:
            rows.append(
                {
                    'pk': bank.pk,
                    'bank_id': bank.pk,
                    'name': bank.name,
                    'logo_url': bank.logo_url,
                    'selected_url': self.get_bank_selected_url(bank),
                    'detail_url': reverse(
                        'bank:bank_detail',
                        kwargs={'pk': bank.pk},
                    ),
                    'edit_url': reverse(
                        'bank:bank_update',
                        kwargs={'pk': bank.pk},
                    ),
                }
            )
        return rows

    def get_selected_bank(self, bank_page):
        """Return the selected bank for the side program table."""
        selected_bank_id = self.request.GET.get('selected_bank')
        if selected_bank_id and selected_bank_id.isdecimal():
            selected_bank = bank_page.paginator.object_list.filter(
                pk=selected_bank_id,
            ).first()
            if selected_bank is not None:
                return selected_bank

        first_bank = next(iter(bank_page.object_list), None)
        return first_bank

    def build_bank_program_rows(self, selected_bank):
        """Build bank program rows for the selected bank."""
        if selected_bank is None:
            return []

        return list(
            BankProgram.objects.select_related('mortgage_program')
            .filter(bank=selected_bank)
            .order_by('mortgage_program__name')
        )

    def build_bank_pagination_querystring(self):
        """Build query string for bank pagination links."""
        params = self.request.GET.copy()
        params['model'] = 'bank'
        params.pop('page', None)
        params.pop('edit', None)
        return params.urlencode()

    def build_context(self, config, form, edit_object=None, delete_error=None):
        """Build template context for bank and generic catalog pages."""
        context = super().build_context(
            config=config,
            form=form,
            edit_object=edit_object,
            delete_error=delete_error,
        )

        context['sort_by'] = self.request.GET.get('sort_by', '')
        context['sort_dir'] = self.request.GET.get('sort_dir', 'asc')

        if config.key == 'bank':
            bank_page = self.get_bank_page(config)
            selected_bank = self.get_selected_bank(bank_page)
            context['rows'] = self.build_rows(config, context['columns'])
            context['bank_filters'] = {
                'name': self.request.GET.get('filter_name', ''),
                'scope': self.request.GET.get('filter_bank_scope', 'all'),
            }
            context['page_obj'] = bank_page
            context['pagination_querystring'] = (
                self.build_bank_pagination_querystring()
            )
            context['selected_bank'] = selected_bank
            context['selected_bank_programs'] = self.build_bank_program_rows(
                selected_bank
            )
            context['bank_create_url'] = reverse('bank:bank_create')
            context['last_synced_at'] = (
                Bank.objects.order_by('-updated_at')
                .values_list('updated_at', flat=True)
                .first()
            )

        if config.key == 'bank_program':
            context['bank_program_filters'] = {
                'bank': self.request.GET.get('filter_bank', ''),
                'program': self.request.GET.get('filter_program', ''),
            }
            context['banks_for_filter'] = Bank.objects.order_by('name')
            context['programs_for_filter'] = MortgageProgram.objects.order_by(
                'name'
            )

        sortable_fields = set(self.get_sort_field_map(config).keys())
        for column in context['columns']:
            column_name = column['name']
            column['is_sortable'] = column_name in sortable_fields
            column['is_sorted'] = False
            column['sort_direction'] = ''
            column['sort_url'] = ''

            if not column['is_sortable']:
                continue

            next_sort_dir = 'asc'
            if context['sort_by'] == column_name:
                column['is_sorted'] = True
                column['sort_direction'] = context['sort_dir']
                if context['sort_dir'] != 'desc':
                    next_sort_dir = 'desc'

            params = self.request.GET.copy()
            params['model'] = config.key
            params['sort_by'] = column_name
            params['sort_dir'] = next_sort_dir
            params.pop('edit', None)
            column['sort_url'] = f'?{params.urlencode()}'

        return context


class BankProgramFormMixin:
    """Shared behavior for bank create and update pages."""

    template_name = 'bank/bank_form.html'
    bank = None

    def get_bank(self):
        """Return bank instance for the current request."""
        return self.bank

    def get_form_title(self):
        """Return page title for the form."""
        return 'Создание банка' if self.get_bank() is None else 'Банк'

    def apply_form_control_classes(self, form):
        """Apply Bootstrap classes to form fields."""
        for field in form.fields.values():
            widget = field.widget
            if not hasattr(widget, 'attrs'):
                continue

            existing_class = widget.attrs.get('class', '')
            widget.attrs['class'] = f'{existing_class} form-control'.strip()

    def build_formset(self, data=None, instance=None):
        """Build a bank program formset."""
        formset = BankProgramFormSet(data=data, instance=instance)
        for form in formset.forms:
            self.apply_form_control_classes(form)
        return formset

    def get_context_data(self, **kwargs):
        """Build bank form page context."""
        context = super().get_context_data(**kwargs)
        bank = self.get_bank()
        bank_form = kwargs.get('form') or BankForm(instance=bank)
        program_formset = kwargs.get('formset') or self.build_formset(
            instance=bank
        )
        self.apply_form_control_classes(bank_form)

        context.update(
            {
                'section_title': self.get_form_title(),
                'bank': bank,
                'form': bank_form,
                'formset': program_formset,
                'catalog_url': f'{reverse("bank:catalog")}?model=bank',
            }
        )
        return context

    def post(self, request, *args, **kwargs):
        """Save bank and related mortgage programs."""
        bank = self.get_bank() or Bank()
        bank_form = BankForm(data=request.POST, instance=bank)
        program_formset = self.build_formset(data=request.POST, instance=bank)
        self.apply_form_control_classes(bank_form)

        if bank_form.is_valid():
            with transaction.atomic():
                saved_bank = bank_form.save()
                program_formset = self.build_formset(
                    data=request.POST,
                    instance=saved_bank,
                )
                if program_formset.is_valid():
                    program_formset.save()
                    return redirect('bank:bank_detail', pk=saved_bank.pk)
                transaction.set_rollback(True)

        context = self.get_context_data(
            form=bank_form,
            formset=program_formset,
        )
        return self.render_to_response(context, status=400)


class BankCreateView(BankProgramFormMixin, TemplateView):
    """Create a bank with mortgage programs."""


class BankUpdateView(BankProgramFormMixin, TemplateView):
    """Update a bank with mortgage programs."""

    def dispatch(self, request, *args, **kwargs):
        """Load bank before handling the request."""
        self.bank = get_object_or_404(Bank, pk=kwargs['pk'])
        return super().dispatch(request, *args, **kwargs)


class BankDetailView(TemplateView):
    """Show a bank card with its mortgage programs."""

    template_name = 'bank/bank_detail.html'

    def get_context_data(self, **kwargs):
        """Build bank detail context."""
        context = super().get_context_data(**kwargs)
        bank = get_object_or_404(Bank, pk=self.kwargs['pk'])
        context.update(
            {
                'section_title': bank.name,
                'bank': bank,
                'programs': (
                    BankProgram.objects.select_related('mortgage_program')
                    .filter(bank=bank)
                    .order_by('mortgage_program__name')
                ),
                'catalog_url': f'{reverse("bank:catalog")}?model=bank',
                'edit_url': reverse(
                    'bank:bank_update',
                    kwargs={'pk': bank.pk},
                ),
            }
        )
        return context


class KeyRateListView(TemplateView):
    """List and manually synchronize Central Bank key rates."""

    template_name = 'bank/key_rate_list.html'

    def post(self, request, *args, **kwargs):
        """Run manual key rate synchronization."""
        try:
            result = sync_key_rates()
        except KeyRateSyncError as error:
            messages.error(
                request,
                f'Не удалось обновить данные ключевой ставки: {error}',
            )
        else:
            messages.success(
                request,
                (
                    'Обновление данных ключевой ставки завершено: '
                    f'создано={result["created"]}, '
                    f'обновлено={result["updated"]}, '
                    f'обработано={result["processed"]}.'
                ),
            )

        return redirect('bank:key_rate_list')

    def get_queryset(self):
        """Return key rates with previous-rate deltas."""
        return (
            KeyRate.objects.annotate(
                previous_rate=Window(
                    expression=Lead('key_rate'),
                    order_by=F('meeting_date').desc(),
                ),
            )
            .annotate(
                rate_change=ExpressionWrapper(
                    F('key_rate') - F('previous_rate'),
                    output_field=DecimalField(max_digits=5, decimal_places=2),
                ),
            )
            .order_by('-meeting_date')
        )

    def get_context_data(self, **kwargs):
        """Build key rate page context."""
        context = super().get_context_data(**kwargs)
        rows = list(self.get_queryset())

        context['section_title'] = 'Ключевая ставка'
        context['rows'] = rows
        context['last_synced_at'] = (
            KeyRate.objects.order_by('-updated_at')
            .values_list('updated_at', flat=True)
            .first()
        )
        return context
