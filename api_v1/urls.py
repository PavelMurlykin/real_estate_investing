from django.urls import path

from .views import (
    LoginAPIView,
    LogoutAPIView,
    MortgageCalculationAPIView,
    MortgageOptionsAPIView,
    OverviewAPIView,
    PropertyDetailAPIView,
    PropertyListAPIView,
    SavedMortgageCalculationDetailAPIView,
    SavedMortgageCalculationExportAPIView,
    SavedMortgageCalculationListCreateAPIView,
    SessionAPIView,
)

app_name = 'api_v1'

urlpatterns = [
    path('auth/session/', SessionAPIView.as_view(), name='session'),
    path('auth/login/', LoginAPIView.as_view(), name='login'),
    path('auth/logout/', LogoutAPIView.as_view(), name='logout'),
    path('overview/', OverviewAPIView.as_view(), name='overview'),
    path('properties/', PropertyListAPIView.as_view(), name='property_list'),
    path(
        'properties/<int:pk>/',
        PropertyDetailAPIView.as_view(),
        name='property_detail',
    ),
    path(
        'mortgage/options/',
        MortgageOptionsAPIView.as_view(),
        name='mortgage_options',
    ),
    path(
        'mortgage/calculate/',
        MortgageCalculationAPIView.as_view(),
        name='mortgage_calculate',
    ),
    path(
        'mortgage/calculations/',
        SavedMortgageCalculationListCreateAPIView.as_view(),
        name='saved_mortgage_calculation_list',
    ),
    path(
        'mortgage/calculations/<int:pk>/',
        SavedMortgageCalculationDetailAPIView.as_view(),
        name='saved_mortgage_calculation_detail',
    ),
    path(
        'mortgage/calculations/<int:pk>/export/excel/',
        SavedMortgageCalculationExportAPIView.as_view(),
        {'export_format': 'excel'},
        name='saved_mortgage_calculation_export_excel',
    ),
    path(
        'mortgage/calculations/<int:pk>/export/word/',
        SavedMortgageCalculationExportAPIView.as_view(),
        {'export_format': 'word'},
        name='saved_mortgage_calculation_export_word',
    ),
]
