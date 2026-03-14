from decimal import Decimal, InvalidOperation

from django.db.models import DecimalField, ExpressionWrapper, F, Window
from django.db.models.functions import Lead
from django.views.generic import TemplateView

from property.views import BaseCatalogView, CatalogModelConfig

from .forms import BankForm
from .models import Bank, BankProgram, KeyRate, MortgageProgram


class BankCatalogView(BaseCatalogView):
    template_name = 'bank/catalog_form.html'
    section_title = 'Банки'
    url_name = 'bank:catalog'
    default_model_key = 'bank'
    model_configs = (
        CatalogModelConfig(
            key='bank',
            model=Bank,
            form_fields=('name', 'interest_rate', 'salary_client_discount'),
            table_fields=('name', 'interest_rate', 'salary_client_discount'),
            order_by=('name',),
        ),
        CatalogModelConfig(
            key='mortgage_program',
            model=MortgageProgram,
            form_fields=('name', 'condition', 'is_preferential'),
            table_fields=('name', 'condition', 'is_preferential'),
            order_by=('name',),
        ),
        CatalogModelConfig(
            key='bank_program',
            model=BankProgram,
            form_fields=('bank', 'mortgage_program'),
            table_fields=('bank', 'mortgage_program'),
            order_by=('bank__name', 'mortgage_program__name'),
            select_related=('bank', 'mortgage_program'),
        ),
    )

    def _safe_decimal(self, value):
        if value in (None, ''):
            return None
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return None

    def build_form(self, config, data=None, instance=None):
        if config.key == 'bank':
            form = BankForm(data=data, instance=instance)

            for field in form.fields.values():
                widget = field.widget
                if hasattr(widget, 'attrs'):
                    existing_class = widget.attrs.get('class', '')
                    widget.attrs['class'] = f'{existing_class} form-control'.strip()

            return form

        return super().build_form(config, data=data, instance=instance)

    def get_sort_field_map(self, config):
        if config.key == 'bank':
            return {
                'name': 'name',
                'interest_rate': 'interest_rate',
                'salary_client_discount': 'salary_client_rate',
            }
        if config.key == 'bank_program':
            return {
                'bank': 'bank__name',
                'mortgage_program': 'mortgage_program__name',
            }
        return {}

    def get_queryset(self, config):
        queryset = config.model.objects.all()
        if config.select_related:
            queryset = queryset.select_related(*config.select_related)

        sort_by = self.request.GET.get('sort_by')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        sort_prefix = '-' if sort_dir == 'desc' else ''

        if config.key == 'bank':
            queryset = queryset.annotate(
                salary_client_rate=ExpressionWrapper(
                    F('interest_rate') - F('salary_client_discount'),
                    output_field=DecimalField(max_digits=5, decimal_places=2),
                ),
            )

            name = (self.request.GET.get('filter_name') or '').strip()
            interest_rate_from = self._safe_decimal(self.request.GET.get('filter_interest_rate_from'))
            interest_rate_to = self._safe_decimal(self.request.GET.get('filter_interest_rate_to'))
            salary_rate_from = self._safe_decimal(self.request.GET.get('filter_salary_rate_from'))
            salary_rate_to = self._safe_decimal(self.request.GET.get('filter_salary_rate_to'))

            if name:
                queryset = queryset.filter(name__icontains=name)
            if interest_rate_from is not None:
                queryset = queryset.filter(interest_rate__gte=interest_rate_from)
            if interest_rate_to is not None:
                queryset = queryset.filter(interest_rate__lte=interest_rate_to)
            if salary_rate_from is not None:
                queryset = queryset.filter(salary_client_rate__gte=salary_rate_from)
            if salary_rate_to is not None:
                queryset = queryset.filter(salary_client_rate__lte=salary_rate_to)

            sort_field = self.get_sort_field_map(config).get(sort_by)
            if sort_field:
                return queryset.order_by(f'{sort_prefix}{sort_field}')
            return queryset.order_by(*config.order_by)

        if config.key == 'bank_program':
            bank_name = (self.request.GET.get('filter_bank') or '').strip()
            program_id = self.request.GET.get('filter_program')

            if bank_name:
                queryset = queryset.filter(bank__name__icontains=bank_name)
            if program_id:
                queryset = queryset.filter(mortgage_program_id=program_id)

            sort_field = self.get_sort_field_map(config).get(sort_by)
            if sort_field:
                return queryset.order_by(f'{sort_prefix}{sort_field}')
            return queryset.order_by(*config.order_by)

        return queryset.order_by(*config.order_by)

    def build_columns(self, config):
        columns = super().build_columns(config)

        if config.key == 'bank':
            for column in columns:
                if column['name'] == 'salary_client_discount':
                    column['label'] = 'Процентная ставка для зарплатных клиентов, %'

        return columns

    def build_rows(self, config, columns):
        if config.key != 'bank':
            return super().build_rows(config, columns)

        rows = []
        queryset = self.get_queryset(config)
        for obj in queryset:
            cells = []
            for column in columns:
                if column['name'] == 'salary_client_discount':
                    raw_value = getattr(obj, 'salary_client_rate')
                else:
                    raw_value = getattr(obj, column['name'])

                cells.append(
                    {
                        'value': self.format_cell_value(raw_value),
                        'is_long_text': column['is_long_text'],
                    }
                )

            rows.append(
                {
                    'pk': obj.pk,
                    'bank_id': obj.pk,
                    'cells': cells,
                    'edit_url': self.get_model_url(config.key, edit_id=obj.pk),
                }
            )

        return rows

    def build_context(self, config, form, edit_object=None, delete_error=None):
        context = super().build_context(
            config=config,
            form=form,
            edit_object=edit_object,
            delete_error=delete_error,
        )

        context['sort_by'] = self.request.GET.get('sort_by', '')
        context['sort_dir'] = self.request.GET.get('sort_dir', 'asc')

        if config.key == 'bank':
            context['bank_filters'] = {
                'name': self.request.GET.get('filter_name', ''),
                'interest_rate_from': self.request.GET.get('filter_interest_rate_from', ''),
                'interest_rate_to': self.request.GET.get('filter_interest_rate_to', ''),
                'salary_rate_from': self.request.GET.get('filter_salary_rate_from', ''),
                'salary_rate_to': self.request.GET.get('filter_salary_rate_to', ''),
            }

            bank_program_map = {}
            for relation in BankProgram.objects.select_related('mortgage_program').order_by('mortgage_program__name'):
                bank_program_map.setdefault(str(relation.bank_id), []).append(relation.mortgage_program.name)
            context['bank_program_map'] = bank_program_map

        if config.key == 'bank_program':
            context['bank_program_filters'] = {
                'bank': self.request.GET.get('filter_bank', ''),
                'program': self.request.GET.get('filter_program', ''),
            }
            context['programs_for_filter'] = MortgageProgram.objects.order_by('name')

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


class KeyRateListView(TemplateView):
    template_name = 'bank/key_rate_list.html'

    def get_queryset(self):
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
        context = super().get_context_data(**kwargs)
        rows = list(self.get_queryset())

        context['section_title'] = 'Ключевая ставка'
        context['rows'] = rows
        context['last_synced_at'] = (
            KeyRate.objects.order_by('-updated_at').values_list('updated_at', flat=True).first()
        )
        return context
