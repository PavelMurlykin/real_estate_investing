from django.urls import path

from .views import (
    BankCatalogView,
    BankCreateView,
    BankDetailView,
    BankUpdateView,
    KeyRateListView,
)

app_name = 'bank'

urlpatterns = [
    path('', BankCatalogView.as_view(), name='catalog'),
    path('banks/create/', BankCreateView.as_view(), name='bank_create'),
    path('banks/<int:pk>/', BankDetailView.as_view(), name='bank_detail'),
    path(
        'banks/<int:pk>/edit/',
        BankUpdateView.as_view(),
        name='bank_update',
    ),
    path('key-rate/', KeyRateListView.as_view(), name='key_rate_list'),
]
