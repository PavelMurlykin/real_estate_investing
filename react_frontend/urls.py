from django.urls import path

from .views import ReactAppView

app_name = 'react_frontend'

urlpatterns = [
    path('', ReactAppView.as_view(), name='index'),
    path('<path:route>/', ReactAppView.as_view(), name='route'),
]
