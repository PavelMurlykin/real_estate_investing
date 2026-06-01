# mortgage/urls.py
from django.urls import path

from . import views

app_name = 'mortgage'

urlpatterns = [
    path('', views.mortgage_calculator, name='mortgage_calculator'),
    path(
        'property-cost/<int:pk>/',
        views.property_cost_api,
        name='property_cost_api',
    ),
    path('calculations/', views.calculation_list, name='calculation_list'),
    path(
        'calculations/<int:pk>/delete/',
        views.calculation_delete,
        name='calculation_delete',
    ),
    path(
        'calculations/<int:pk>/',
        views.calculation_detail,
        name='calculation_detail',
    ),
    path(
        'trench-calculations/',
        views.trench_calculation_list,
        name='trench_calculation_list',
    ),
    path(
        'trench-calculations/<int:pk>/delete/',
        views.trench_calculation_delete,
        name='trench_calculation_delete',
    ),
    path(
        'trench-calculations/<int:pk>/',
        views.trench_calculation_detail,
        name='trench_calculation_detail',
    ),
]
