from django.urls import path
from . import views

urlpatterns = [
    path('', views.mortgage_calculator, name='mortgage_calculator'),
]
