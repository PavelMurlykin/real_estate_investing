from django import forms
from django.forms import inlineformset_factory

from property.models import RealEstateComplex

from .models import Bank, BankProgram, DeveloperMortgageProgram


class RealEstateComplexChoiceField(forms.ModelChoiceField):
    """Показывает в селекте ЖК вместе с названием застройщика."""

    def label_from_instance(self, real_estate_complex):
        """Возвращает однозначную подпись ЖК для выбранной группы."""
        return (
            f'{real_estate_complex.name} '
            f'({real_estate_complex.developer.name})'
        )


class BankForm(forms.ModelForm):
    """Form for creating and editing banks."""

    class Meta:
        """Configure bank form fields."""

        model = Bank
        fields = ('name', 'logo_url')
        labels = {
            'name': 'Название',
            'logo_url': 'Логотип',
        }

    def save(self, commit=True):
        """Save bank and keep catalog-created banks active."""
        bank = super().save(commit=False)
        bank.is_active = True

        if commit:
            bank.save()

        return bank


class BankProgramForm(forms.ModelForm):
    """Form for a bank mortgage program row."""

    class Meta:
        """Configure bank program row fields."""

        model = BankProgram
        fields = (
            'mortgage_program',
            'interest_rate',
            'minimum_initial_payment_percent',
            'maximum_loan_term_years',
        )

    def has_changed(self):
        """Treat fully empty extra rows as unchanged."""
        if self.instance.pk or not self.is_bound:
            return super().has_changed()

        field_values = [
            self.data.get(f'{self.prefix}-{field_name}')
            for field_name in self.Meta.fields
        ]
        if all(value in (None, '') for value in field_values):
            return False

        return super().has_changed()


class DeveloperMortgageProgramForm(forms.ModelForm):
    """Форма создания и редактирования программы застройщика."""

    real_estate_complex = RealEstateComplexChoiceField(
        queryset=RealEstateComplex.objects.none(),
        required=False,
        empty_label='Все ЖК группы',
        label='ЖК',
    )

    class Meta:
        """Настраивает поля ипотечной программы застройщика."""

        model = DeveloperMortgageProgram
        fields = (
            'company_group',
            'real_estate_complex',
            'bank',
            'mortgage_program',
            'price_increase_percent',
            'grace_period_months',
            'grace_period_interest_rate',
            'minimum_initial_payment_percent',
            'interest_rate',
            'maximum_loan_term_years',
            'maximum_loan_amount',
            'rate_discount_percent',
        )
        widgets = {
            'price_increase_percent': forms.NumberInput(
                attrs={'step': '0.01'}
            ),
            'grace_period_months': forms.NumberInput(
                attrs={'min': '1', 'step': '1'}
            ),
            'grace_period_interest_rate': forms.NumberInput(
                attrs={'min': '0', 'max': '100', 'step': '0.01'}
            ),
            'minimum_initial_payment_percent': forms.NumberInput(
                attrs={'min': '0', 'max': '100', 'step': '0.01'}
            ),
            'interest_rate': forms.NumberInput(
                attrs={'min': '0', 'max': '100', 'step': '0.01'}
            ),
            'maximum_loan_term_years': forms.NumberInput(
                attrs={'min': '1', 'step': '1'}
            ),
            'maximum_loan_amount': forms.NumberInput(
                attrs={'min': '0', 'step': '0.01'}
            ),
            'rate_discount_percent': forms.NumberInput(
                attrs={'min': '0', 'max': '100', 'step': '0.01'}
            ),
        }

    def __init__(self, *args, **kwargs):
        """Ограничивает список ЖК выбранной группой компаний."""
        super().__init__(*args, **kwargs)
        company_group_id = self.get_selected_company_group_id()
        real_estate_complexes = RealEstateComplex.objects.none()
        if company_group_id is not None:
            real_estate_complexes = (
                RealEstateComplex.objects.select_related('developer')
                .filter(developer__company_group_id=company_group_id)
                .order_by('name', 'developer__name')
            )
        self.fields['real_estate_complex'].queryset = (
            real_estate_complexes
        )

        for field in self.fields.values():
            if isinstance(field.widget, forms.Select):
                field.widget.attrs['class'] = 'form-select'
            else:
                field.widget.attrs['class'] = 'form-control'

    def get_selected_company_group_id(self):
        """Возвращает группу из POST, initial или редактируемой записи."""
        field_name = self.add_prefix('company_group')
        raw_company_group_id = (
            self.data.get(field_name) if self.is_bound else ''
        )
        if str(raw_company_group_id).isdigit():
            return int(raw_company_group_id)

        initial_company_group = self.initial.get('company_group')
        initial_company_group_id = getattr(
            initial_company_group, 'pk', initial_company_group
        )
        if str(initial_company_group_id).isdigit():
            return int(initial_company_group_id)

        if self.instance and self.instance.company_group_id:
            return self.instance.company_group_id
        return None


BankProgramFormSet = inlineformset_factory(
    Bank,
    BankProgram,
    form=BankProgramForm,
    fields=(
        'mortgage_program',
        'interest_rate',
        'minimum_initial_payment_percent',
        'maximum_loan_term_years',
    ),
    extra=3,
    can_delete=True,
)
