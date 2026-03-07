from decimal import Decimal

from django import forms

from .models import Bank


class BankForm(forms.ModelForm):
    salary_client_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0'),
        label='Процентная ставка для зарплатных клиентов, %',
    )

    class Meta:
        model = Bank
        fields = ('name', 'interest_rate')
        labels = {
            'name': 'Название',
            'interest_rate': 'Процентная ставка, %',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['salary_client_rate'].initial = (
                self.instance.interest_rate - self.instance.salary_client_discount
            )

    def clean(self):
        cleaned_data = super().clean()
        interest_rate = cleaned_data.get('interest_rate')
        salary_client_rate = cleaned_data.get('salary_client_rate')

        if interest_rate is not None and salary_client_rate is not None and salary_client_rate > interest_rate:
            self.add_error(
                'salary_client_rate',
                'Ставка для зарплатных клиентов не может быть выше базовой ставки.',
            )

        return cleaned_data

    def save(self, commit=True):
        bank = super().save(commit=False)
        salary_client_rate = self.cleaned_data['salary_client_rate']
        bank.salary_client_discount = bank.interest_rate - salary_client_rate
        bank.is_active = True

        if commit:
            bank.save()

        return bank
