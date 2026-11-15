from urllib.parse import urlencode

from django import forms
from django.contrib import messages
from django.shortcuts import redirect
from django.urls import reverse
from django.views import View

from property.views import BaseCatalogView, CatalogModelConfig
from users.roles import ExternalDataSyncRequiredMixin, can_sync_external_data

from .import_forms import LocationImportForm
from .models import City, District, Metro, MetroLine, Region
from .osm_import import LocationImportError, import_locations


class LocationImportView(ExternalDataSyncRequiredMixin, View):
    """Provide the same administrator import on fallback Django pages."""

    def post(self, request):
        """Validate the selected hierarchy, import and report the result."""
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
            key='metro',
            model=Metro,
            form_fields=('station', 'metro_line', 'is_active'),
            table_fields=('station', 'metro_line', 'metro_line__city'),
            order_by=('metro_line__city__name', 'metro_line__line', 'station'),
            select_related=('metro_line__city',),
        ),
    )

    def get_current_model_key(self):
        """Route the removed metro-line tab to the metro catalog."""
        requested_key = self.request.POST.get('model') or self.request.GET.get(
            'model'
        )
        if requested_key == 'metro_line':
            return 'metro'
        return super().get_current_model_key()

    def get_sort_field_map(self, config):
        """Return sortable columns for location catalogs."""
        if config.key == 'metro':
            return {
                'station': 'station',
                'metro_line': 'metro_line__line',
                'metro_line__city': 'metro_line__city__name',
            }
        return super().get_sort_field_map(config)

    def filter_queryset(self, config, queryset):
        """Apply metro filters from the catalog page."""
        if config.key != 'metro':
            return queryset

        city_id = self.request.GET.get('filter_city')
        metro_line_id = self.request.GET.get('filter_metro_line')

        if city_id:
            queryset = queryset.filter(metro_line__city_id=city_id)
        if metro_line_id:
            queryset = queryset.filter(metro_line_id=metro_line_id)

        return queryset

    def build_context(self, config, form, edit_object=None, delete_error=None):
        """Add metro filter controls to the location catalog context."""
        context = super().build_context(
            config=config,
            form=form,
            edit_object=edit_object,
            delete_error=delete_error,
        )

        if can_sync_external_data(self.request.user):
            selected_region = self.request.GET.get('regionId', '')
            import_form = LocationImportForm(initial={
                'dictionary': self.request.GET.get('dictionary', 'regions'),
                'regionId': selected_region,
            })
            import_form.fields['regionId'].widget = forms.Select(choices=[
                ('', 'Выберите регион'),
                *Region.objects.filter(source_identifier__isnull=False)
                .order_by('name').values_list('pk', 'name')[:200],
            ])
            cities = City.objects.none()
            if selected_region.isdecimal():
                cities = City.objects.filter(
                    region_id=int(selected_region),
                    source_identifier__isnull=False,
                ).order_by('name')
            import_form.fields['cityId'].widget = forms.Select(choices=[
                ('', 'Выберите город'), *cities.values_list('pk', 'name')[:1000],
            ])
            context['location_import_form'] = import_form

        if config.key == 'metro':
            context['metro_filters'] = {
                'city': self.request.GET.get('filter_city', ''),
                'metro_line': self.request.GET.get('filter_metro_line', ''),
            }
            context['cities_for_filter'] = City.objects.order_by('name')
            context['metro_lines_for_filter'] = MetroLine.objects.select_related(
                'city'
            ).order_by('city__name', 'line')

        return context
