from django.urls import path

from .views import BankCatalogView, KeyRateListView

app_name = 'bank'

urlpatterns = [
    path('', BankCatalogView.as_view(), name='catalog'),
    path('key-rate/', KeyRateListView.as_view(), name='key_rate_list'),
]
