from django.shortcuts import render

from location.models import City
from property.models import RealEstateComplex

CITY_PREPOSITIONAL_CASE = {
    'Санкт-Петербург': 'Санкт-Петербурге',
    'Москва': 'Москве',
    'Калининград': 'Калининграде',
}


def index(request):
    """Render the homepage with complexes for the selected city."""
    cities = list(City.objects.filter(is_active=True).order_by('name'))
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
                is_active=True,
                district__is_active=True,
                district__city=selected_city,
                district__city__is_active=True,
            )
            .select_related(
                'developer',
                'district__city__region',
                'real_estate_class',
                'real_estate_type',
            )
            .order_by('name')
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
