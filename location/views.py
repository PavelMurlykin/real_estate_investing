from property.views import BaseCatalogView, CatalogModelConfig

from .models import City, District, Metro, MetroLine, Region


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
