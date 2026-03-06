from django.shortcuts import render

from property.models import City, RealEstateComplex


CITY_PREPOSITIONAL_CASE = {
    'Санкт-Петербург': 'Санкт-Петербурге',
    'Москва': 'Москве',
    'Калининград': 'Калининграде',
}


def index(request):
    cities = City.objects.filter(is_active=True).order_by('name')
    selected_city = None

    city_id = request.GET.get('city')
    if city_id and city_id.isdigit():
        selected_city = cities.filter(pk=int(city_id)).first()

    if selected_city is None:
        selected_city = cities.filter(name='Санкт-Петербург').first() or cities.first()

    complexes = RealEstateComplex.objects.none()
    if selected_city:
        complexes = (
            RealEstateComplex.objects
            .filter(
                is_active=True,
                district__is_active=True,
                district__city=selected_city,
                district__city__is_active=True,
            )
            .select_related('district__city')
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
        'complexes': complexes,
        'complexes_map_data': complexes_map_data,
        'headline_city': (
            CITY_PREPOSITIONAL_CASE.get(selected_city.name, selected_city.name)
            if selected_city else 'выбранном городе'
        ),
    }
    return render(request, template, context)
