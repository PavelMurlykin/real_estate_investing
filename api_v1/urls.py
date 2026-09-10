from django.urls import path

from .views import (
    CustomerDetailAPIView,
    CustomerFormOptionsAPIView,
    CustomerListAPIView,
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
    SavedTrenchMortgageCalculationCreateAPIView,
    SessionAPIView,
    TrenchMortgageCalculationAPIView,
)

app_name = 'api_v1'

urlpatterns = [
    path('auth/session/', SessionAPIView.as_view(), name='session'),
    path('auth/login/', LoginAPIView.as_view(), name='login'),
    path('auth/logout/', LogoutAPIView.as_view(), name='logout'),
    path('overview/', OverviewAPIView.as_view(), name='overview'),
    path('customers/', CustomerListAPIView.as_view(), name='customer_list'),
    path(
        'customers/options/',
        CustomerFormOptionsAPIView.as_view(),
        name='customer_form_options',
    ),
    path(
        'customers/<int:pk>/',
        CustomerDetailAPIView.as_view(),
        name='customer_detail',
    ),
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
        'mortgage/trench/calculate/',
        TrenchMortgageCalculationAPIView.as_view(),
        name='trench_mortgage_calculate',
    ),
    path(
        'mortgage/trench/calculations/',
        SavedTrenchMortgageCalculationCreateAPIView.as_view(),
        name='saved_trench_mortgage_calculation_create',
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
