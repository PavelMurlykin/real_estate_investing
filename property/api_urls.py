from django.urls import path
from django.http import JsonResponse
from .models import City, District, RealEstateComplex, RealEstateComplexBuilding


def cities_api(request):
    region_id = request.GET.get('region_id')
    cities = City.objects.filter(region_id=region_id).values('id', 'name')
    return JsonResponse(list(cities), safe=False)

def districts_api(request):
    city_id = request.GET.get('city_id')
    districts = District.objects.filter(city_id=city_id).values('id', 'name')
    return JsonResponse(list(districts), safe=False)

def complexes_api(request):
    district_id = request.GET.get('district_id')
    complexes = RealEstateComplex.objects.filter(district_id=district_id).values('id', 'name')
    return JsonResponse(list(complexes), safe=False)

def buildings_api(request):
    complex_id = request.GET.get('complex_id')
    buildings = RealEstateComplexBuilding.objects.filter(real_estate_complex_id=complex_id).values('id', 'number')
    return JsonResponse(list(buildings), safe=False)

urlpatterns = [
    path('cities/', cities_api, name='cities_api'),
    path('districts/', districts_api, name='districts_api'),
    path('complexes/', complexes_api, name='complexes_api'),
    path('buildings/', buildings_api, name='buildings_api'),
]
