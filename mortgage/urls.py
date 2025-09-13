from django.urls import path

from . import views

app_name = 'mortgage'

urlpatterns = [
    path('', views.mortgage_calculator, name='mortgage_calculator'),
    path('calculations/', views.calculation_list, name='calculation_list'),
    path('calculations/<int:pk>/', views.calculation_detail, name='calculation_detail'),
]