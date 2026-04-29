from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django import forms
from django.db import models as django_models
from django.db import transaction
from django.db.models import Count
from django.db.models.deletion import ProtectedError
from django.forms import modelform_factory
from django.http import HttpResponseRedirect
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    TemplateView,
    UpdateView,
)

from location.models import City, District, Metro, MetroLine, Region

from .forms import (
    DeveloperForm,
    PropertyForm,
    RealEstateComplexBuildingFormSet,
    RealEstateComplexForm,
    RealEstateComplexMetroAvailabilityFormSet,
)
from .models import (
    ApartmentDecoration,
    ApartmentLayout,
    Developer,
    Property,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateType,
)


@dataclass(frozen=True)
class CatalogModelConfig:
    """Описание класса CatalogModelConfig.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    key: str
    model: type[django_models.Model]
    form_fields: tuple[str, ...]
    table_fields: tuple[str, ...]
    order_by: tuple[str, ...]
    select_related: tuple[str, ...] = ()

    @property
    def title(self):
        """Описание метода title.

        Выполняет прикладную операцию текущего модуля.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        return str(self.model._meta.verbose_name_plural)


class BaseCatalogView(TemplateView):
    """Описание класса BaseCatalogView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    template_name = 'property/catalog_form.html'
    section_title = ''
    url_name = ''
    default_model_key = ''
    model_configs: tuple[CatalogModelConfig, ...] = ()

    def get_sort_field_map(self, config):
        """Return table columns that can be used for queryset sorting."""
        return {field_name: field_name for field_name in config.table_fields}

    def get_config_map(self):
        """Описание метода get_config_map.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return {config.key: config for config in self.model_configs}

    def get_current_model_key(self):
        """Описание метода get_current_model_key.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        key = (
            self.request.POST.get('model')
            or self.request.GET.get('model')
            or self.default_model_key
        )
        config_map = self.get_config_map()
        if key in config_map:
            return key
        return self.default_model_key

    def get_config(self):
        """Описание метода get_config.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return self.get_config_map()[self.get_current_model_key()]

    def get_model_url(self, model_key, edit_id=None):
        """Описание метода get_model_url.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            model_key: Входной параметр, влияющий на работу метода.
            edit_id: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        url = f'{reverse(self.url_name)}?model={model_key}'
        if edit_id:
            url = f'{url}&edit={edit_id}'
        return url

    def filter_queryset(self, config, queryset):
        """Apply request filters to the catalog queryset."""
        return queryset

    def get_queryset(self, config):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            config: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        queryset = config.model.objects.all()
        if config.select_related:
            queryset = queryset.select_related(*config.select_related)
        queryset = self.filter_queryset(config, queryset)

        sort_by = self.request.GET.get('sort_by')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        sort_prefix = '-' if sort_dir == 'desc' else ''
        sort_field = self.get_sort_field_map(config).get(sort_by)

        if sort_field:
            return queryset.order_by(f'{sort_prefix}{sort_field}')
        return queryset.order_by(*config.order_by)

    def build_form(self, config, data=None, instance=None):
        """Описание метода build_form.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            config: Входной параметр, влияющий на работу метода.
            data: Входной параметр, влияющий на работу метода.
            instance: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        form_class = modelform_factory(config.model, fields=config.form_fields)
        form = form_class(data=data, instance=instance)

        for field in form.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs['class'] = 'form-check-input'
                continue

            existing_class = widget.attrs.get('class', '')
            combined_class = f'{existing_class} form-control'.strip()
            widget.attrs['class'] = ' '.join(combined_class.split())

        return form

    def get_metro_line_option_data(self, form):
        """Build color data for metro line selects."""
        if 'metro_line' not in form.fields:
            return []

        return [
            {
                'id': metro_line.pk,
                'color': metro_line.line_color,
            }
            for metro_line in form.fields['metro_line'].queryset
        ]

    def format_cell_value(self, value):
        """Описание метода format_cell_value.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            value: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        if isinstance(value, bool):
            return 'Да' if value else 'Нет'
        if value in (None, ''):
            return '-'
        return str(value)

    def build_cell(self, value):
        """Prepare a table cell for the catalog template."""
        cell = {
            'value': self.format_cell_value(value),
            'is_long_text': False,
            'color': '',
        }

        if isinstance(value, MetroLine):
            cell['value'] = value.line
            cell['color'] = value.line_color

        return cell

    def get_field_by_path(self, model, field_path):
        """Resolve a Django model field by a direct or related field path."""
        current_model = model
        model_field = None
        for field_name in field_path.split('__'):
            model_field = current_model._meta.get_field(field_name)
            if getattr(model_field, 'remote_field', None):
                current_model = model_field.remote_field.model
        return model_field

    def get_value_by_path(self, obj, field_path):
        """Read an object value by a direct or related field path."""
        value = obj
        for field_name in field_path.split('__'):
            value = getattr(value, field_name, None)
            if value is None:
                break
        return value

    def build_columns(self, config):
        """Описание метода build_columns.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            config: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        columns = []
        for field_name in config.table_fields:
            model_field = self.get_field_by_path(config.model, field_name)
            columns.append(
                {
                    'name': field_name,
                    'label': model_field.verbose_name,
                    'is_long_text': model_field.get_internal_type()
                    == 'TextField',
                }
            )
        return columns

    def build_rows(self, config, columns):
        """Описание метода build_rows.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            config: Входной параметр, влияющий на работу метода.
            columns: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        rows = []
        queryset = self.get_queryset(config)
        for obj in queryset:
            cells = []
            for column in columns:
                raw_value = self.get_value_by_path(obj, column['name'])
                cell = self.build_cell(raw_value)
                cell['is_long_text'] = column['is_long_text']
                cells.append(cell)
            rows.append(
                {
                    'pk': obj.pk,
                    'cells': cells,
                    'edit_url': self.get_model_url(config.key, edit_id=obj.pk),
                }
            )
        return rows

    def build_nav_models(self, current_key):
        """Описание метода build_nav_models.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            current_key: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        items = []
        for config in self.model_configs:
            items.append(
                {
                    'key': config.key,
                    'title': config.title,
                    'url': self.get_model_url(config.key),
                    'is_active': config.key == current_key,
                }
            )
        return items

    def build_context(self, config, form, edit_object=None, delete_error=None):
        """Описание метода build_context.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            config: Входной параметр, влияющий на работу метода.
            form: Входной параметр, влияющий на работу метода.
            edit_object: Входной параметр, влияющий на работу метода.
            delete_error: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        columns = self.build_columns(config)
        current_model_key = config.key
        context = {
            'section_title': self.section_title,
            'model_tabs': self.build_nav_models(current_model_key),
            'current_model_title': config.title,
            'model_key': current_model_key,
            'columns': columns,
            'rows': self.build_rows(config, columns),
            'form': form,
            'is_editing': edit_object is not None,
            'edit_object': edit_object,
            'form_action_url': reverse(self.url_name),
            'cancel_url': self.get_model_url(current_model_key),
            'delete_error': delete_error,
            'metro_line_options': self.get_metro_line_option_data(form),
        }

        context['sort_by'] = self.request.GET.get('sort_by', '')
        context['sort_dir'] = self.request.GET.get('sort_dir', 'asc')

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

    def get_edit_object(self, config):
        """Описание метода get_edit_object.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            config: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        edit_id = self.request.GET.get('edit')
        if not edit_id:
            return None
        return get_object_or_404(config.model, pk=edit_id)

    def get(self, request, *args, **kwargs):
        """Описание метода get.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            request: Входной параметр, влияющий на работу метода.
            *args: Входной параметр, влияющий на работу метода.
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        config = self.get_config()
        edit_object = self.get_edit_object(config)
        form = self.build_form(config, instance=edit_object)
        context = self.get_context_data(
            **self.build_context(config, form=form, edit_object=edit_object)
        )
        return self.render_to_response(context)

    def post(self, request, *args, **kwargs):
        """Описание метода post.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            request: Входной параметр, влияющий на работу метода.
            *args: Входной параметр, влияющий на работу метода.
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        config = self.get_config()
        action = request.POST.get('action', 'save')

        if action == 'delete':
            return self.handle_delete(config)
        return self.handle_save(config)

    def handle_save(self, config):
        """Описание метода handle_save.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            config: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        object_id = self.request.POST.get('object_id')
        instance = (
            get_object_or_404(config.model, pk=object_id)
            if object_id
            else None
        )
        form = self.build_form(
            config, data=self.request.POST, instance=instance
        )

        if form.is_valid():
            form.save()
            return redirect(self.get_model_url(config.key))

        context = self.get_context_data(
            **self.build_context(config, form=form, edit_object=instance)
        )
        return self.render_to_response(context, status=400)

    def handle_delete(self, config):
        """Описание метода handle_delete.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            config: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        object_id = self.request.POST.get('object_id')
        if not object_id:
            return redirect(self.get_model_url(config.key))

        object_to_delete = get_object_or_404(config.model, pk=object_id)

        try:
            object_to_delete.delete()
            return redirect(self.get_model_url(config.key))
        except ProtectedError:
            form = self.build_form(config)
            delete_error = (
                f'Нельзя удалить "{object_to_delete}": есть связанные записи.'
            )
            context = self.get_context_data(
                **self.build_context(
                    config, form=form, delete_error=delete_error
                )
            )
            return self.render_to_response(context, status=400)


class DictionaryCatalogView(BaseCatalogView):
    """Описание класса DictionaryCatalogView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    section_title = 'Справочники'
    url_name = 'property:dictionary_catalog'
    default_model_key = 'real_estate_type'
    model_configs = (
        CatalogModelConfig(
            key='real_estate_type',
            model=RealEstateType,
            form_fields=('name', 'description', 'is_active'),
            table_fields=('name', 'description', 'is_active'),
            order_by=('name',),
        ),
        CatalogModelConfig(
            key='real_estate_class',
            model=RealEstateClass,
            form_fields=('name', 'weight', 'description', 'is_active'),
            table_fields=('name', 'weight', 'description', 'is_active'),
            order_by=('weight', 'name'),
        ),
        CatalogModelConfig(
            key='apartment_layout',
            model=ApartmentLayout,
            form_fields=('name', 'description', 'is_active'),
            table_fields=('name', 'description', 'is_active'),
            order_by=('name',),
        ),
        CatalogModelConfig(
            key='apartment_decoration',
            model=ApartmentDecoration,
            form_fields=('name', 'description', 'is_active'),
            table_fields=('name', 'description', 'is_active'),
            order_by=('name',),
        ),
    )


class ProtectedDeleteMixin:
    """Описание класса ProtectedDeleteMixin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    protected_error_message = 'Нельзя удалить запись из-за связанных данных.'

    def post(self, request, *args, **kwargs):
        """Описание метода post.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            request: Входной параметр, влияющий на работу метода.
            *args: Входной параметр, влияющий на работу метода.
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        self.object = self.get_object()
        try:
            return super().post(request, *args, **kwargs)
        except ProtectedError:
            context = self.get_context_data(object=self.object)
            context['protected_error'] = self.protected_error_message
            return self.render_to_response(context, status=400)


class DeveloperListView(ListView):
    """Описание класса DeveloperListView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Developer
    template_name = 'property/developer_list.html'
    context_object_name = 'developers'
    paginate_by = 20

    def get_queryset(self):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return Developer.objects.order_by('name')


class DeveloperCreateView(CreateView):
    """Описание класса DeveloperCreateView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Developer
    form_class = DeveloperForm
    template_name = 'property/developer_form.html'
    success_url = reverse_lazy('property:developer_list')


class DeveloperUpdateView(UpdateView):
    """Описание класса DeveloperUpdateView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Developer
    form_class = DeveloperForm
    template_name = 'property/developer_form.html'
    success_url = reverse_lazy('property:developer_list')


class DeveloperDeleteView(ProtectedDeleteMixin, DeleteView):
    """Описание класса DeveloperDeleteView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Developer
    template_name = 'property/developer_confirm_delete.html'
    success_url = reverse_lazy('property:developer_list')
    protected_error_message = (
        'Нельзя удалить застройщика: с ним связаны записи ЖК.'
    )


class RealEstateComplexListView(ListView):
    """Описание класса RealEstateComplexListView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = RealEstateComplex
    template_name = 'property/real_estate_complex_list.html'
    context_object_name = 'complexes'
    paginate_by = 20
    sort_fields = {
        'name': 'name',
        'developer': 'developer__name',
        'city': 'district__city__name',
        'real_estate_class': 'real_estate_class__name',
        'real_estate_type': 'real_estate_type__name',
        'buildings_count': 'buildings_count',
    }
    table_columns = (
        {'key': 'name', 'label': 'ЖК'},
        {'key': 'developer', 'label': 'Застройщик'},
        {'key': 'city', 'label': 'Город'},
        {'key': 'real_estate_class', 'label': 'Класс'},
        {'key': 'real_estate_type', 'label': 'Тип'},
        {'key': 'buildings_count', 'label': 'Корпусов'},
    )

    def get_queryset(self):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        queryset = (
            RealEstateComplex.objects.annotate(
                buildings_count=Count('realestatecomplexbuilding')
            )
            .select_related(
                'developer',
                'district__city',
                'real_estate_class',
                'real_estate_type',
            )
        )

        filters = self.get_filters()
        if filters['name']:
            queryset = queryset.filter(name__icontains=filters['name'])
        if filters['developer']:
            queryset = queryset.filter(developer_id=filters['developer'])
        if filters['city']:
            queryset = queryset.filter(district__city_id=filters['city'])
        if filters['real_estate_class']:
            queryset = queryset.filter(
                real_estate_class_id=filters['real_estate_class']
            )
        if filters['real_estate_type']:
            queryset = queryset.filter(
                real_estate_type_id=filters['real_estate_type']
            )
        if filters['buildings_count'].isdigit():
            queryset = queryset.filter(
                buildings_count=filters['buildings_count']
            )

        sort_by = self.request.GET.get('sort_by', '')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        sort_field = self.sort_fields.get(sort_by)
        if sort_field:
            sort_prefix = '-' if sort_dir == 'desc' else ''
            return queryset.order_by(f'{sort_prefix}{sort_field}', 'name')

        return queryset.order_by('developer__name', 'name')

    def get_filters(self):
        return {
            'name': self.request.GET.get('filter_name', '').strip(),
            'developer': self.request.GET.get('filter_developer', ''),
            'city': self.request.GET.get('filter_city', ''),
            'real_estate_class': self.request.GET.get(
                'filter_real_estate_class', ''
            ),
            'real_estate_type': self.request.GET.get(
                'filter_real_estate_type', ''
            ),
            'buildings_count': self.request.GET.get(
                'filter_buildings_count', ''
            ),
        }

    def build_querystring(self, **overrides):
        params = self.request.GET.copy()
        params.pop('page', None)
        for key, value in overrides.items():
            if value in (None, ''):
                params.pop(key, None)
                continue
            params[key] = value
        return params.urlencode()

    def build_table_columns(self):
        sort_by = self.request.GET.get('sort_by', '')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        columns = []

        for column in self.table_columns:
            key = column['key']
            next_sort_dir = 'asc'
            is_sorted = sort_by == key
            if is_sorted and sort_dir != 'desc':
                next_sort_dir = 'desc'

            columns.append(
                {
                    **column,
                    'is_sorted': is_sorted,
                    'sort_direction': sort_dir if is_sorted else '',
                    'sort_url': (
                        '?'
                        + self.build_querystring(
                            sort_by=key, sort_dir=next_sort_dir
                        )
                    ),
                }
            )

        return columns

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['filters'] = self.get_filters()
        context['sort_by'] = self.request.GET.get('sort_by', '')
        context['sort_dir'] = self.request.GET.get('sort_dir', 'asc')
        context['columns'] = self.build_table_columns()
        context['developers_for_filter'] = Developer.objects.order_by('name')
        context['cities_for_filter'] = City.objects.order_by('name')
        context['classes_for_filter'] = RealEstateClass.objects.order_by(
            'weight', 'name'
        )
        context['types_for_filter'] = RealEstateType.objects.order_by('name')
        context['pagination_querystring'] = self.build_querystring()
        return context


class RealEstateComplexFormsetMixin:
    """Описание класса RealEstateComplexFormsetMixin.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = RealEstateComplex
    form_class = RealEstateComplexForm
    template_name = 'property/real_estate_complex_form.html'
    success_url = reverse_lazy('property:complex_list')

    def get_formset(self):
        """Описание метода get_formset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        instance = (
            self.object
            if getattr(self, 'object', None)
            else RealEstateComplex()
        )
        if self.request.method == 'POST':
            return RealEstateComplexBuildingFormSet(
                self.request.POST, instance=instance, prefix='buildings'
            )
        return RealEstateComplexBuildingFormSet(
            instance=instance, prefix='buildings'
        )

    def get_metro_availability_formset(self):
        instance = (
            self.object
            if getattr(self, 'object', None)
            else RealEstateComplex()
        )
        if self.request.method == 'POST':
            return RealEstateComplexMetroAvailabilityFormSet(
                self.request.POST, instance=instance, prefix='metro'
            )
        return RealEstateComplexMetroAvailabilityFormSet(
            instance=instance, prefix='metro'
        )

    def validate_metro_availability_city(self, form, metro_formset):
        selected_city = form.cleaned_data.get('city')
        if not selected_city:
            district = form.cleaned_data.get('district')
            selected_city = district.city if district else None

        if not selected_city:
            return True

        is_valid = True
        for metro_form in metro_formset.forms:
            if not hasattr(metro_form, 'cleaned_data'):
                continue
            if metro_form.cleaned_data.get('DELETE'):
                continue

            metro = metro_form.cleaned_data.get('metro')
            if not metro:
                continue

            if metro.metro_line.city_id != selected_city.pk:
                metro_form.add_error(
                    'metro',
                    'Станция метро не относится к выбранному городу.',
                )
                is_valid = False

        return is_valid

    def get_context_data(self, **kwargs):
        """Описание метода get_context_data.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        context = super().get_context_data(**kwargs)
        context.setdefault('building_formset', self.get_formset())
        context.setdefault(
            'metro_availability_formset',
            self.get_metro_availability_formset(),
        )
        context['location_cities'] = list(
            City.objects.order_by('name').values('id', 'name', 'region_id')
        )
        context['location_districts'] = list(
            District.objects.select_related('city__region')
            .order_by('name')
            .values('id', 'name', 'city_id', 'city__region_id')
        )
        context['location_metro_stations'] = list(
            Metro.objects.select_related('metro_line__city')
            .order_by(
                'metro_line__city__name',
                'metro_line__line',
                'station',
            )
            .values(
                'id',
                'station',
                'metro_line__line',
                'metro_line__line_color',
                'metro_line__city_id',
            )
        )
        existing_complexes = RealEstateComplex.objects.all()
        current_object = getattr(self, 'object', None)
        if current_object and current_object.pk:
            existing_complexes = existing_complexes.exclude(
                pk=current_object.pk
            )
        context['existing_complexes'] = list(
            existing_complexes.order_by('developer_id', 'name').values(
                'id',
                'name',
                'developer_id',
            )
        )
        return context

    def form_valid(self, form):
        """Описание метода form_valid.

        Выполняет прикладную операцию текущего модуля.

        Аргументы:
            form: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата определяется вызывающим кодом.
        """
        context = self.get_context_data(form=form)
        building_formset = context['building_formset']
        metro_formset = context['metro_availability_formset']

        if not building_formset.is_valid() or not metro_formset.is_valid():
            return self.render_to_response(context, status=400)

        if not self.validate_metro_availability_city(form, metro_formset):
            return self.render_to_response(context, status=400)

        with transaction.atomic():
            self.object = form.save()
            building_formset.instance = self.object
            building_formset.save()
            metro_formset.instance = self.object
            metro_formset.save()

        return HttpResponseRedirect(self.get_success_url())


class RealEstateComplexCreateView(RealEstateComplexFormsetMixin, CreateView):
    """Описание класса RealEstateComplexCreateView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    pass


class RealEstateComplexUpdateView(RealEstateComplexFormsetMixin, UpdateView):
    """Описание класса RealEstateComplexUpdateView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    pass


class RealEstateComplexDeleteView(ProtectedDeleteMixin, DeleteView):
    """Описание класса RealEstateComplexDeleteView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = RealEstateComplex
    template_name = 'property/real_estate_complex_confirm_delete.html'
    success_url = reverse_lazy('property:complex_list')
    protected_error_message = (
        'Нельзя удалить ЖК: есть связанные объекты недвижимости.'
    )


class PropertyListView(ListView):
    """Описание класса PropertyListView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Property
    template_name = 'property/property_list.html'
    context_object_name = 'properties'
    paginate_by = 20
    sort_fields = {
        'city': 'building__real_estate_complex__district__city__name',
        'developer': 'building__real_estate_complex__developer__name',
        'complex': 'building__real_estate_complex__name',
        'building': 'building__number',
        'apartment_number': 'apartment_number',
        'layout': 'layout__name',
        'area': 'area',
        'property_cost': 'property_cost',
    }
    table_columns = (
        {'key': 'city', 'label': 'Город'},
        {'key': 'developer', 'label': 'Застройщик'},
        {'key': 'complex', 'label': 'ЖК'},
        {'key': 'building', 'label': 'Корпус'},
        {'key': 'apartment_number', 'label': 'Квартира'},
        {'key': 'layout', 'label': 'Планировка'},
        {'key': 'area', 'label': 'Площадь, м2'},
        {'key': 'property_cost', 'label': 'Цена, руб.'},
    )

    def get_queryset(self):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        queryset = Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex__district__city',
            'building__real_estate_complex',
            'building',
            'layout',
            'decoration',
        )

        filters = self.get_filters()

        if filters['city']:
            queryset = queryset.filter(
                building__real_estate_complex__district__city_id=filters[
                    'city'
                ]
            )
        if filters['developer']:
            queryset = queryset.filter(
                building__real_estate_complex__developer_id=filters[
                    'developer'
                ]
            )
        if filters['complex']:
            queryset = queryset.filter(
                building__real_estate_complex_id=filters['complex']
            )
        if filters['building']:
            queryset = queryset.filter(building_id=filters['building'])
        if filters['apartment_number']:
            queryset = queryset.filter(
                apartment_number__icontains=filters['apartment_number']
            )
        if filters['layout']:
            queryset = queryset.filter(layout_id=filters['layout'])
        if filters['area']:
            area = self.parse_decimal(filters['area'])
            if area is not None:
                queryset = queryset.filter(area=area)
        if filters['property_cost']:
            property_cost = self.parse_decimal(filters['property_cost'])
            if property_cost is not None:
                queryset = queryset.filter(property_cost=property_cost)

        sort_by = self.request.GET.get('sort_by', '')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        sort_field = self.sort_fields.get(sort_by)
        if sort_field:
            sort_prefix = '-' if sort_dir == 'desc' else ''
            return queryset.order_by(
                f'{sort_prefix}{sort_field}', 'apartment_number'
            )

        return queryset.order_by(
            'building__real_estate_complex__district__city__name',
            'building__real_estate_complex__developer__name',
            'building__real_estate_complex__name',
            'building__number',
            'apartment_number',
        )

    def get_filters(self):
        return {
            'city': self.request.GET.get('filter_city', ''),
            'developer': self.request.GET.get('filter_developer', ''),
            'complex': self.request.GET.get('filter_complex', ''),
            'building': self.request.GET.get('filter_building', ''),
            'apartment_number': self.request.GET.get(
                'filter_apartment_number', ''
            ).strip(),
            'layout': self.request.GET.get('filter_layout', ''),
            'area': self.request.GET.get('filter_area', '').strip(),
            'property_cost': self.request.GET.get(
                'filter_property_cost', ''
            ).strip(),
        }

    def parse_decimal(self, value):
        try:
            return Decimal(value.replace(',', '.'))
        except (InvalidOperation, ValueError):
            return None

    def build_querystring(self, **overrides):
        params = self.request.GET.copy()
        params.pop('page', None)
        for key, value in overrides.items():
            if value in (None, ''):
                params.pop(key, None)
                continue
            params[key] = value
        return params.urlencode()

    def build_table_columns(self):
        sort_by = self.request.GET.get('sort_by', '')
        sort_dir = self.request.GET.get('sort_dir', 'asc')
        columns = []

        for column in self.table_columns:
            key = column['key']
            next_sort_dir = 'asc'
            is_sorted = sort_by == key
            if is_sorted and sort_dir != 'desc':
                next_sort_dir = 'desc'

            columns.append(
                {
                    **column,
                    'is_sorted': is_sorted,
                    'sort_direction': sort_dir if is_sorted else '',
                    'sort_url': (
                        '?'
                        + self.build_querystring(
                            sort_by=key, sort_dir=next_sort_dir
                        )
                    ),
                }
            )

        return columns

    def get_context_data(self, **kwargs):
        """Описание метода get_context_data.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        context = super().get_context_data(**kwargs)
        context['filters'] = self.get_filters()
        context['sort_by'] = self.request.GET.get('sort_by', '')
        context['sort_dir'] = self.request.GET.get('sort_dir', 'asc')
        context['columns'] = self.build_table_columns()
        context['cities_for_filter'] = City.objects.order_by('name')
        context['developers_for_filter'] = Developer.objects.order_by('name')
        context['complexes_for_filter'] = RealEstateComplex.objects.select_related(
            'developer', 'district__city'
        ).order_by('name')
        context['buildings_for_filter'] = (
            RealEstateComplexBuilding.objects.select_related(
                'real_estate_complex'
            ).order_by('real_estate_complex__name', 'number')
        )
        context['layouts_for_filter'] = ApartmentLayout.objects.order_by('name')
        context['pagination_querystring'] = self.build_querystring()
        return context


class PropertyDetailView(DetailView):
    """Описание класса PropertyDetailView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Property
    template_name = 'property/property_detail.html'
    context_object_name = 'property'

    def get_queryset(self):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return Property.objects.select_related(
            'building__real_estate_complex__developer',
            'building__real_estate_complex__district__city__region',
            'building__real_estate_complex__real_estate_class',
            'building__real_estate_complex__real_estate_type',
            'building',
            'layout',
            'decoration',
        )


class PropertyCreateView(CreateView):
    """Описание класса PropertyCreateView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Property
    form_class = PropertyForm
    template_name = 'property/property_form.html'
    success_url = reverse_lazy('property:list')

    def get_context_data(self, **kwargs):
        """Описание метода get_context_data.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        context = super().get_context_data(**kwargs)
        context['regions'] = Region.objects.all()
        context['cities'] = City.objects.all()
        context['districts'] = District.objects.all()
        context['developers'] = Developer.objects.all()
        context['complexes'] = RealEstateComplex.objects.all()
        context['buildings'] = RealEstateComplexBuilding.objects.all()
        context['layouts'] = ApartmentLayout.objects.all()
        context['decorations'] = ApartmentDecoration.objects.all()
        return context


class PropertyUpdateView(UpdateView):
    """Описание класса PropertyUpdateView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Property
    form_class = PropertyForm
    template_name = 'property/property_form.html'

    def get_success_url(self):
        """Описание метода get_success_url.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return reverse_lazy('property:detail', kwargs={'pk': self.object.pk})

    def get_context_data(self, **kwargs):
        """Описание метода get_context_data.

        Возвращает подготовленные данные для дальнейшей обработки.

        Аргументы:
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        context = super().get_context_data(**kwargs)
        context['regions'] = Region.objects.all()
        context['cities'] = City.objects.all()
        context['districts'] = District.objects.all()
        context['developers'] = Developer.objects.all()
        context['complexes'] = RealEstateComplex.objects.all()
        context['buildings'] = RealEstateComplexBuilding.objects.all()
        context['layouts'] = ApartmentLayout.objects.all()
        context['decorations'] = ApartmentDecoration.objects.all()

        property_obj = self.get_object()

        if property_obj.building:
            building = property_obj.building
            real_estate_complex = building.real_estate_complex
            district = real_estate_complex.district
            city = district.city
            region = city.region
            developer = real_estate_complex.developer

            context['current_region'] = region.id
            context['current_city'] = city.id
            context['current_district'] = district.id
            context['current_developer'] = developer.id
            context['current_complex'] = real_estate_complex.id
            context['current_building'] = building.id

            context['filtered_cities'] = City.objects.filter(region=region)
            context['filtered_districts'] = District.objects.filter(city=city)
            context['filtered_complexes'] = RealEstateComplex.objects.filter(
                district=district
            )
            context['filtered_buildings'] = (
                RealEstateComplexBuilding.objects.filter(
                    real_estate_complex=real_estate_complex,
                )
            )

        return context


class PropertyDeleteView(DeleteView):
    """Описание класса PropertyDeleteView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    model = Property
    template_name = 'property/property_confirm_delete.html'
    success_url = reverse_lazy('property:list')
