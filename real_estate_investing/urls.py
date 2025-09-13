from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('homepage.urls')),
    path('property/', include('property.urls', namespace='property')),
    path('mortgage/', include('mortgage.urls', namespace='mortgage')),
    path('trench-mortgage/', include('trench_mortgage.urls', namespace='trench_mortgage')),
]
