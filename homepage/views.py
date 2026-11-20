from django.shortcuts import render
from django.db.models import Q

from location.legacy_catalog import LegacyImportScope, legacy_choices
from property.models import RealEstateComplex
from property.location_context import geography_prefetch

CITY_PREPOSITIONAL_CASE = {
    'Санкт-Петербург': 'Санкт-Петербурге',
    'Москва': 'Москве',
    'Калининград': 'Калининграде',
}


def index(request):
    """Render the homepage with complexes for the selected city."""
    cities = [LegacyImportScope.from_mapping(alias) for alias in legacy_choices('city', active_only=True)]
    selected_city = None

    city_id = request.GET.get('city')
    selected_view = request.GET.get('view')
    if selected_view not in ('list', 'map'):
        selected_view = 'list'

    if city_id and city_id.isdigit():
        selected_city_id = int(city_id)
        selected_city = next(
            (city for city in cities if city.pk == selected_city_id),
            None,
        )

    if selected_city is None:
        selected_city = next(
            (city for city in cities if city.name == 'Санкт-Петербург'),
            cities[0] if cities else None,
        )

    complexes = []
    if selected_city:
        complexes = list(
            RealEstateComplex.objects.filter(
                Q(district_id__in=legacy_choices('district', city_id=selected_city.pk, active_only=True)
                  .values('legacy_id'))
                | Q(district_id__isnull=True, location_links__is_primary=True,
                    location_links__location__ancestor_links__ancestor__legacy_mappings__model_name='city',
                    location_links__location__ancestor_links__ancestor__legacy_mappings__legacy_id=selected_city.pk),
                is_active=True,
            )
            .select_related(
                'developer',
                'real_estate_class',
                'real_estate_type',
            )
            .prefetch_related(geography_prefetch())
            .distinct().order_by('name')
        )

    complexes_map_data = [
        {
            'name': complex_obj.name,
            'map_link': complex_obj.map_link or '',
        }
        for complex_obj in complexes
    ]

    template = 'homepage/index.html'
    context = {
        'cities': cities,
        'selected_city': selected_city,
        'selected_view': selected_view,
        'complexes': complexes,
        'complexes_map_data': complexes_map_data,
        'headline_city': (
            CITY_PREPOSITIONAL_CASE.get(selected_city.name, selected_city.name)
            if selected_city
            else 'выбранном городе'
        ),
    }
    return render(request, template, context)
