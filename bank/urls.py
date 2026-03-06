from django.urls import path

from .views import BankCatalogView

app_name = 'bank'

urlpatterns = [
    path('', BankCatalogView.as_view(), name='catalog'),
]
