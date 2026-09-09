from django.urls import path

from .views import (
    LoginAPIView,
    LogoutAPIView,
    MortgageCalculationAPIView,
    MortgageOptionsAPIView,
    OverviewAPIView,
    PropertyListAPIView,
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
        'mortgage/options/',
        MortgageOptionsAPIView.as_view(),
        name='mortgage_options',
    ),
    path(
        'mortgage/calculate/',
        MortgageCalculationAPIView.as_view(),
        name='mortgage_calculate',
    ),
]
