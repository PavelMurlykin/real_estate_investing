from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from core.views import health_check

urlpatterns = [
    path('health/', health_check, name='health_check'),
    path('admin/', admin.site.urls),
    path('users/', include('users.urls', namespace='users')),
    path('', include('homepage.urls')),
    path('locations/', include('location.urls', namespace='location')),
    path('property/', include('property.urls', namespace='property')),
    path('bank/', include('bank.urls', namespace='bank')),
    path('api/', include('property.api_urls')),
    path('mortgage/', include('mortgage.urls', namespace='mortgage')),
    path(
        'trench-mortgage/',
        include('trench_mortgage.urls', namespace='trench_mortgage'),
    ),
    path('customers/', include('customer.urls', namespace='customer')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
