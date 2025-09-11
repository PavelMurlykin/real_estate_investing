from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('', include('homepage.urls')),
    path('admin/', admin.site.urls),
    path('property/', include('property.urls')),
    path('calculator/', include('calculator.urls')),
]
