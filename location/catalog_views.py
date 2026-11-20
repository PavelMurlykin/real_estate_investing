"""Keep fallback location pages on the same canonical dictionary service."""

from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views import View

from users.roles import can_manage_catalogs, can_sync_external_data
from .catalog_forms import LocationCatalogFilterForm, LocationCatalogForm
from .catalog_service import (
    CATALOG_CATEGORIES, catalog_locations, delete_catalog_location,
    filter_catalog_locations, save_catalog_location,
)
from .jobs import serialize_import_job
from .models import LocationCompatibilityEntry, Location, LocationImportJob, LocationType


class CanonicalLocationCatalogView(View):
    """Read Location and preserve legacy IDs only at the URL compatibility boundary."""

    def dictionary_key(self):
        """Resolve old tab names without reusing their primary keys."""
        model_key = self.request.POST.get('model') or self.request.GET.get('model', 'region')
        return {
            'region': 'regions', 'city': 'localities',
            'locality': 'localities', 'district': 'districts',
        }.get(model_key, 'regions')

    def edited_location(self, key):
        """Resolve explicit canonical edits or translate an original catalog link."""
        from property.location_form_fields import selected_identifier

        supplied = self.request.POST.get('locationId') or self.request.GET.get('locationId')
        identifier = selected_identifier(supplied)
        if supplied and not identifier:
            raise Http404
        if identifier:
            return get_object_or_404(catalog_locations(key), pk=identifier)
        old_identifier = selected_identifier(self.request.GET.get('edit'))
        if old_identifier:
            mapping = get_object_or_404(
                LocationCompatibilityEntry, legacy_id=old_identifier, model_name={
                'regions': 'region', 'localities': 'city', 'districts': 'district',
            }[key])
            return get_object_or_404(catalog_locations(key), pk=mapping.location_id)
        return None

    def get(self, request):
        """Render a bounded dictionary, filters and an authorized editor."""
        key = self.dictionary_key()
        instance = self.edited_location(key)
        form = LocationCatalogForm(CATALOG_CATEGORIES[key], instance=instance)
        return self.page(key, form, instance)

    def post(self, request):
        """Apply authorized canonical writes without touching old dictionaries."""
        if not can_manage_catalogs(request.user):
            raise PermissionDenied
        key = self.dictionary_key()
        instance = self.edited_location(key)
        form = LocationCatalogForm(CATALOG_CATEGORIES[key], request.POST, instance)
        if request.POST.get('action') == 'delete' and instance:
            try:
                delete_catalog_location(instance)
            except (ValidationError, ProtectedError):
                form.add_error(None, (
                    'Удаление невозможно: запись используется или связана '
                    'с источником. Снимите флаг «Активно».'
                ))
                return self.page(key, form, instance, 409)
        elif form.is_valid():
            try:
                save_catalog_location(CATALOG_CATEGORIES[key], form.service_values(), instance)
            except ValidationError as error:
                errors_by_field = (
                    error.message_dict if hasattr(error, 'message_dict')
                    else {'__all__': error.messages}
                )
                for field, errors in errors_by_field.items():
                    form.add_error(field if field in form.fields else None, errors)
            else:
                messages.success(request, 'Территория сохранена. Существующие связи сохранены.')
                return self.success_url(key)
        else:
            return self.page(key, form, instance, 400)
        if form.errors:
            return self.page(key, form, instance, 400)
        return self.success_url(key)

    def success_url(self, key):
        """Keep an explicit fallback navigation after a successful POST."""
        return redirect(reverse('location:location_catalog') + '?' + urlencode({
            'model': {'regions': 'region', 'localities': 'locality', 'districts': 'district'}[key],
            'legacy': '1',
        }))

    def page(self, key, form, instance=None, status=200):
        """Avoid serializing full parent dictionaries or loading unbounded rows."""
        filters = LocationCatalogFilterForm(self.request.GET)
        valid = filters.is_valid()
        parameters = filters.cleaned_data if valid else {}
        queryset = (
            filter_catalog_locations(catalog_locations(key), parameters)
            if valid else Location.objects.none()
        )
        page = Paginator(queryset, 20).get_page(self.request.GET.get('page'))
        selected = list(Location.objects.select_related('parent', 'region', 'location_type').filter(
            pk__in=[parameters.get('regionId'), parameters.get('ancestorId')],
        ))
        can_import = can_sync_external_data(self.request.user)
        model_keys = {
            'regions': 'region', 'localities': 'locality', 'districts': 'district',
        }
        titles = {
            'regions': 'Регионы', 'localities': 'Населённые пункты',
            'districts': 'Административные районы',
        }
        return render(self.request, 'location/canonical_catalog.html', {
            'title': titles[key], 'dictionary_key': key, 'model_key': model_keys[key],
            'form': form, 'edited_location': instance, 'filter_form': filters,
            'filters': parameters,
            'region_selected': next((
                row for row in selected if row.pk == parameters.get('regionId')
            ), None),
            'district_selected': next((
                row for row in selected if row.pk == parameters.get('ancestorId')
            ), None),
            'page_obj': page, 'can_manage_catalogs': can_manage_catalogs(self.request.user),
            'types': LocationType.objects.filter(
                category=CATALOG_CATEGORIES[key],
            ).order_by('name', 'pk'),
            'can_sync_external_data': can_import,
            'national_import': serialize_import_job(
                LocationImportJob.objects.first(),
            ) if can_import else None,
        }, status=status if valid else 400)
