import sys

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.staticfiles.views import serve as serve_static_file
from django.urls import include, path, re_path

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
    path('customers/', include('customer.urls', namespace='customer')),
]

urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

if any(argument.endswith('runserver') for argument in sys.argv):
    urlpatterns += [
        re_path(
            r'^static/(?P<path>.*)$',
            serve_static_file,
            {'insecure': True},
        ),
    ]
