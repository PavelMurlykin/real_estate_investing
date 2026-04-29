from django.urls import path

from . import views

app_name = 'property'

urlpatterns = [
    path(
        'dictionaries/',
        views.DictionaryCatalogView.as_view(),
        name='dictionary_catalog',
    ),
    path(
        'developers/', views.DeveloperListView.as_view(), name='developer_list'
    ),
    path(
        'developers/create/',
        views.DeveloperCreateView.as_view(),
        name='developer_create',
    ),
    path(
        'developers/<int:pk>/update/',
        views.DeveloperUpdateView.as_view(),
        name='developer_update',
    ),
    path(
        'developers/<int:pk>/delete/',
        views.DeveloperDeleteView.as_view(),
        name='developer_delete',
    ),
    path(
        'complexes/',
        views.RealEstateComplexListView.as_view(),
        name='complex_list',
    ),
    path(
        'complexes/create/',
        views.RealEstateComplexCreateView.as_view(),
        name='complex_create',
    ),
    path(
        'complexes/<int:pk>/update/',
        views.RealEstateComplexUpdateView.as_view(),
        name='complex_update',
    ),
    path(
        'complexes/<int:pk>/delete/',
        views.RealEstateComplexDeleteView.as_view(),
        name='complex_delete',
    ),
    path('', views.PropertyListView.as_view(), name='list'),
    path('create/', views.PropertyCreateView.as_view(), name='create'),
    path('<int:pk>/', views.PropertyDetailView.as_view(), name='detail'),
    path(
        '<int:pk>/update/', views.PropertyUpdateView.as_view(), name='update'
    ),
    path(
        '<int:pk>/delete/', views.PropertyDeleteView.as_view(), name='delete'
    ),
]
