from dataclasses import dataclass

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

from location.models import City, District, Region

from .forms import (
    DeveloperForm,
    PropertyFilterForm,
    PropertyForm,
    RealEstateComplexBuildingFormSet,
    RealEstateComplexForm,
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
            model_field = config.model._meta.get_field(field_name)
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
        return {
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
        }

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


class LocationCatalogView(BaseCatalogView):
    """Описание класса LocationCatalogView.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    section_title = 'Локации'
    url_name = 'property:location_catalog'
    default_model_key = 'region'
    model_configs = (
        CatalogModelConfig(
            key='region',
            model=Region,
            form_fields=('name', 'code', 'is_active'),
            table_fields=('name', 'code', 'is_active'),
            order_by=('name',),
        ),
        CatalogModelConfig(
            key='city',
            model=City,
            form_fields=('name', 'region', 'is_active'),
            table_fields=('name', 'region', 'is_active'),
            order_by=('name',),
            select_related=('region',),
        ),
        CatalogModelConfig(
            key='district',
            model=District,
            form_fields=('name', 'city', 'is_active'),
            table_fields=('name', 'city', 'is_active'),
            order_by=('name',),
            select_related=('city',),
        ),
    )


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

    def get_queryset(self):
        """Описание метода get_queryset.

        Возвращает подготовленные данные для дальнейшей обработки.

        Возвращает:
            Any: Тип результата зависит от контекста использования.
        """
        return (
            RealEstateComplex.objects.annotate(
                buildings_count=Count('realestatecomplexbuilding')
            )
            .select_related(
                'developer',
                'district__city',
                'real_estate_class',
                'real_estate_type',
            )
            .order_by('developer__name', 'name')
        )


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

        if not building_formset.is_valid():
            return self.form_invalid(form)

        with transaction.atomic():
            self.object = form.save()
            building_formset.instance = self.object
            building_formset.save()

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
        ).order_by(
            'building__real_estate_complex__developer__name',
            'building__real_estate_complex__name',
            'building__number',
            'apartment_number',
        )

        city = self.request.GET.get('city')
        developer = self.request.GET.get('developer')
        complex_id = self.request.GET.get('complex')

        if city:
            queryset = queryset.filter(
                building__real_estate_complex__district__city_id=city
            )
        if developer:
            queryset = queryset.filter(
                building__real_estate_complex__developer_id=developer
            )
        if complex_id:
            queryset = queryset.filter(
                building__real_estate_complex_id=complex_id
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
        context['filter_form'] = PropertyFilterForm(self.request.GET)
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
