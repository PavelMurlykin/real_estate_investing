# calculation/urls.py
from django.urls import path

from . import views

app_name = 'calculation'

urlpatterns = [
    path('', views.CalculationView.as_view(), name='calculation_form'),
    path('get-property-cost/<int:property_id>/', views.get_property_cost, name='get_property_cost'),
    path('clear-session/', views.clear_calculation_session, name='clear_session'),
]
