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
        'company-groups/',
        views.CompanyGroupListView.as_view(),
        name='company_group_list',
    ),
    path(
        'company-groups/create/',
        views.CompanyGroupCreateView.as_view(),
        name='company_group_create',
    ),
    path(
        'company-groups/<int:pk>/update/',
        views.CompanyGroupUpdateView.as_view(),
        name='company_group_update',
    ),
    path(
        'company-groups/<int:pk>/delete/',
        views.CompanyGroupDeleteView.as_view(),
        name='company_group_delete',
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
        'developers/import-registry/',
        views.DeveloperRegistryImportView.as_view(),
        name='developer_registry_import',
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
        'complexes/<int:pk>/',
        views.RealEstateComplexDetailView.as_view(),
        name='complex_detail',
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
