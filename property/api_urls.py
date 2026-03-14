from django.http import JsonResponse
from django.urls import path

from location.models import City, District

from .models import RealEstateComplex, RealEstateComplexBuilding


def cities_api(request):
    """Описание метода cities_api.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        request: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    region_id = request.GET.get('region_id')
    cities = City.objects.filter(region_id=region_id).values('id', 'name')
    return JsonResponse(list(cities), safe=False)


def districts_api(request):
    """Описание метода districts_api.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        request: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    city_id = request.GET.get('city_id')
    districts = District.objects.filter(city_id=city_id).values('id', 'name')
    return JsonResponse(list(districts), safe=False)


def complexes_api(request):
    """Описание метода complexes_api.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        request: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    district_id = request.GET.get('district_id')
    complexes = RealEstateComplex.objects.filter(
        district_id=district_id
    ).values('id', 'name')
    return JsonResponse(list(complexes), safe=False)


def buildings_api(request):
    """Описание метода buildings_api.

    Выполняет прикладную операцию текущего модуля.

    Аргументы:
        request: Входной параметр, влияющий на работу метода.

    Возвращает:
        Any: Тип результата определяется вызывающим кодом.
    """
    complex_id = request.GET.get('complex_id')
    buildings = RealEstateComplexBuilding.objects.filter(
        real_estate_complex_id=complex_id
    ).values('id', 'number')
    return JsonResponse(list(buildings), safe=False)


urlpatterns = [
    path('cities/', cities_api, name='cities_api'),
    path('districts/', districts_api, name='districts_api'),
    path('complexes/', complexes_api, name='complexes_api'),
    path('buildings/', buildings_api, name='buildings_api'),
]
