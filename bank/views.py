from property.views import BaseCatalogView, CatalogModelConfig

from .models import Bank, BankProgram, MortgageProgram


class BankCatalogView(BaseCatalogView):
    section_title = 'Банки'
    url_name = 'bank:catalog'
    default_model_key = 'bank'
    model_configs = (
        CatalogModelConfig(
            key='bank',
            model=Bank,
            form_fields=('name', 'interest_rate', 'salary_client_discount', 'is_active'),
            table_fields=('name', 'interest_rate', 'salary_client_discount', 'is_active'),
            order_by=('name',),
        ),
        CatalogModelConfig(
            key='mortgage_program',
            model=MortgageProgram,
            form_fields=('name', 'condition', 'is_preferential', 'is_active'),
            table_fields=('name', 'condition', 'is_preferential', 'is_active'),
            order_by=('name',),
        ),
        CatalogModelConfig(
            key='bank_program',
            model=BankProgram,
            form_fields=('bank', 'mortgage_program', 'is_active'),
            table_fields=('bank', 'mortgage_program', 'is_active'),
            order_by=('bank__name', 'mortgage_program__name'),
            select_related=('bank', 'mortgage_program'),
        ),
    )
