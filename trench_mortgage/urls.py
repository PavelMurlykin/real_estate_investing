from django.urls import path

from . import views

app_name = 'trench_mortgage'

urlpatterns = [
    path(
        '', views.trench_mortgage_calculator, name='trench_mortgage_calculator'
    ),
    path(
        'calculate/',
        views.trench_mortgage_calculator,
        name='calculate_trench_mortgage',
    ),
]
