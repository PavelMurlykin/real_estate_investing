from django.urls import path

from .views import LocationCatalogView, LocationImportView

app_name = 'location'

urlpatterns = [
    path('import/', LocationImportView.as_view(), name='location_import'),
    path('', LocationCatalogView.as_view(), name='location_catalog'),
]
