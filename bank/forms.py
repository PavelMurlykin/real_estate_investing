from django import forms
from django.forms import inlineformset_factory

from .models import Bank, BankProgram


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
