from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from property.views import BaseCatalogView, CatalogModelConfig
from users.roles import ExternalDataSyncRequiredMixin, can_sync_external_data

from .import_forms import LocationImportForm
from .legacy_catalog import legacy_choices
from .import_service import LocationImportError, import_locations
from .metro_import import import_legacy_metro, import_metro
from .metro_forms import MetroForm, MetroLineForm, MetroSystemForm
from .jobs import serialize_import_job, start_import_job
from .models import City, District, LocationImportJob, Metro, MetroLine, MetroSystem, Region
from .metro_geography import filter_metro_geography


class LocationImportView(ExternalDataSyncRequiredMixin, View):
    """Provide the same administrator import on fallback Django pages."""

    def post(self, request):
        """Validate the selected hierarchy, import and report the result."""
        if request.POST.get('action') == 'national':
            start_import_job()
            messages.success(request, 'Общий импорт поставлен в очередь. Прогресс сохранён.')
            return redirect('location:location_catalog')
        if request.POST.get('action') == 'choose-city':
            parameters = urlencode({
                key: request.POST.get(key, '')
                for key in ('dictionary', 'regionId')
            })
            catalog_url = reverse('location:location_catalog')
            return redirect(f'{catalog_url}?{parameters}')
        import_form = LocationImportForm(request.POST)
        if not import_form.is_valid():
            messages.error(request, ' '.join(
                str(error) for errors in import_form.errors.values()
                for error in errors
            ))
        else:
            try:
                if import_form.cleaned_data.get('system'):
                    result = import_metro(import_form.cleaned_data['system'])
                elif import_form.cleaned_data.get('legacy_metro_city'):
                    result = import_legacy_metro(import_form.cleaned_data['legacy_metro_city'])
                else:
                    result = import_locations(
                        import_form.cleaned_data['dictionary'],
                        import_form.cleaned_data.get('region'),
                        import_form.cleaned_data.get('city'),
                    )
            except LocationImportError as error:
                messages.error(request, str(error))
            else:
                messages.success(request, (
                    f'Импорт завершён: добавлено {result["created"]}, '
                    f'обновлено {result["updated"]}, '
                    f'без изменений {result["unchanged"]}, '
                    f'пропущено {result["skipped"]}.'
                ))
        return redirect('location:location_catalog')


class LocationCatalogView(BaseCatalogView):
    """Catalog view for location dictionaries."""

    template_name = 'location/catalog_form.html'

    def dispatch(self, request, *args, **kwargs):
        """Use canonical pages for geography and keep existing metro editors."""
        model_key = request.POST.get('model') or request.GET.get('model', 'region')
        if model_key in {'region', 'city', 'locality', 'district'}:
            from .catalog_views import CanonicalLocationCatalogView
            return CanonicalLocationCatalogView.as_view()(request, *args, **kwargs)
        return super().dispatch(request, *args, **kwargs)
    section_title = 'Локации'
    url_name = 'location:location_catalog'
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
        CatalogModelConfig(
            key='metro_system', model=MetroSystem,
            form_fields=('name', 'location', 'is_active'),
            table_fields=('name', 'location'), order_by=('name',), select_related=('location',),
        ),
        CatalogModelConfig(
            key='metro_line', model=MetroLine,
            form_fields=('line', 'line_color', 'system', 'is_active'),
            table_fields=('line', 'line_color', 'system'), order_by=('system__name', 'line'),
            select_related=('system',),
        ),
        CatalogModelConfig(
            key='metro',
            model=Metro,
            form_fields=('station', 'metro_line', 'lines', 'location', 'location_is_inferred', 'is_active'),
            table_fields=('station', 'metro_line', 'location', 'location_is_inferred'),
            order_by=('metro_line__system__name', 'metro_line__line', 'station'),
            select_related=('metro_line__system', 'location'),
        ),
    )

    def build_form(self, config, data=None, instance=None):
        """Use the same canonical metro validation as administrative editors."""
        form_class = {'metro': MetroForm, 'metro_line': MetroLineForm,
                      'metro_system': MetroSystemForm}.get(config.key)
        return form_class(data=data, instance=instance) if form_class else super().build_form(config, data, instance)

    def get_sort_field_map(self, config):
        """Return sortable columns for location catalogs."""
        if config.key == 'metro':
            return {
                'station': 'station',
                'metro_line': 'metro_line__line',
                'location': 'location__name',
                'location_is_inferred': 'location_is_inferred',
            }
        return super().get_sort_field_map(config)

    def filter_queryset(self, config, queryset):
        """Apply metro filters from the catalog page."""
        if config.key != 'metro':
            return queryset

        city_id = self.request.GET.get('filter_system')
        metro_line_id = self.request.GET.get('filter_metro_line')

        if city_id:
            queryset = queryset.filter(metro_line__system_id=city_id)
        elif self.request.GET.get('filter_city'):
            queryset = filter_metro_geography(queryset, {'cityId': self.request.GET['filter_city']})
        if metro_line_id:
            queryset = queryset.filter(
                Q(lines__pk=metro_line_id) | Q(metro_line_id=metro_line_id),
            ).distinct()

        return queryset

    def build_context(self, config, form, edit_object=None, delete_error=None):
        """Add metro filter controls to the location catalog context."""
        context = super().build_context(
            config=config,
            form=form,
            edit_object=edit_object,
            delete_error=delete_error,
        )
        for tab in context['model_tabs']:
            if tab['key'] == 'city':
                tab['title'] = 'Населённые пункты'
                tab['url'] = reverse('location:location_catalog') + '?model=locality'

        if can_sync_external_data(self.request.user):
            context['national_import'] = serialize_import_job(LocationImportJob.objects.first())
            selected_region = self.request.GET.get('regionId', '')
            import_form = LocationImportForm(initial={
                'dictionary': self.request.GET.get('dictionary', 'regions'),
                'regionId': selected_region,
            })
            import_form.fields['regionId'].widget = forms.Select(choices=[
                ('', 'Выберите регион'),
                *legacy_choices('region').values_list('legacy_id', 'legacy_name')[:200],
            ])
            cities = []
            if selected_region.isdecimal():
                cities = legacy_choices('city', region_id=int(selected_region)).values_list(
                    'legacy_id', 'legacy_name',
                )[:1000]
            import_form.fields['cityId'].widget = forms.Select(choices=[
                ('', 'Выберите город'), *cities,
            ])
            context['location_import_form'] = import_form

        if config.key == 'metro':
            context['metro_filters'] = {
                'city': self.request.GET.get('filter_system', ''),
                'metro_line': self.request.GET.get('filter_metro_line', ''),
            }
            context['cities_for_filter'] = MetroSystem.objects.order_by('name')
            context['metro_lines_for_filter'] = MetroLine.objects.select_related(
                'system'
            ).order_by('system__name', 'line')

        return context
