from django.urls import path

from property.views import LocationCatalogView

app_name = 'location'

urlpatterns = [
    path('', LocationCatalogView.as_view(), name='location_catalog'),
]
