from django.urls import path

from .views import (
    BankCatalogView,
    BankCreateView,
    BankDetailView,
    BankUpdateView,
    DeveloperMortgageProgramComplexOptionsView,
    DeveloperMortgageProgramCreateView,
    DeveloperMortgageProgramDeleteView,
    DeveloperMortgageProgramListView,
    DeveloperMortgageProgramUpdateView,
    KeyRateListView,
)

app_name = 'bank'

urlpatterns = [
    path('', BankCatalogView.as_view(), name='catalog'),
    path('banks/create/', BankCreateView.as_view(), name='bank_create'),
    path('banks/<int:pk>/', BankDetailView.as_view(), name='bank_detail'),
    path(
        'banks/<int:pk>/edit/',
        BankUpdateView.as_view(),
        name='bank_update',
    ),
    path(
        'developer-programs/',
        DeveloperMortgageProgramListView.as_view(),
        name='developer_mortgage_program_list',
    ),
    path(
        'developer-programs/create/',
        DeveloperMortgageProgramCreateView.as_view(),
        name='developer_mortgage_program_create',
    ),
    path(
        'developer-programs/<int:pk>/edit/',
        DeveloperMortgageProgramUpdateView.as_view(),
        name='developer_mortgage_program_update',
    ),
    path(
        'developer-programs/<int:pk>/delete/',
        DeveloperMortgageProgramDeleteView.as_view(),
        name='developer_mortgage_program_delete',
    ),
    path(
        'developer-programs/complex-options/',
        DeveloperMortgageProgramComplexOptionsView.as_view(),
        name='developer_mortgage_program_complex_options',
    ),
    path('key-rate/', KeyRateListView.as_view(), name='key_rate_list'),
]
