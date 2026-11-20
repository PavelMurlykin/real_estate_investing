from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.forms import inlineformset_factory

from core.forms import GroupedDecimalField
from location.legacy_catalog import legacy_catalog, unique_legacy_region
from property.models import RealEstateComplex

from .models import Bank, BankProgram, DeveloperMortgageProgram, MortgageProgramRegionalCreditLimit


class RegionalCreditLimitForm(forms.ModelForm):
    """Edit the canonical subject or preserve a historical-only limit."""

    region = forms.IntegerField(min_value=1, required=False, widget=forms.HiddenInput)

    class Meta:
        """Use the same amount and subject validation in both Django editors."""

        model = MortgageProgramRegionalCreditLimit
        fields = ('mortgage_program', 'region_location', 'region', 'credit_limit', 'is_active')
        field_classes = {'credit_limit': GroupedDecimalField}

    def clean(self):
        """Resolve either ID domain and retain the old contract on unchanged edits."""
        cleaned = super().clean()
        location = cleaned.get('region_location')
        legacy_id = cleaned.get('region')
        if legacy_id is not None:
            alias = legacy_catalog('region').select_related('location__location_type').filter(legacy_id=legacy_id).first()
            if alias is None or (location and location.pk != alias.location_id):
                self.add_error('region_location', 'Выберите соответствующий регион.')
                return cleaned
            location = alias.location if alias.location.location_type.category == 'region' else None
            cleaned['region_location'] = location
            self.instance.region_id, self.instance.legacy_region_name = legacy_id, alias.legacy_name
        elif location and location.pk != self.instance.region_location_id:
            self.instance.region_id, self.instance.legacy_region_name = unique_legacy_region(location.pk)
        if location is None and self.instance.region_id is None:
            self.add_error('region_location', 'Выберите регион.')
        if cleaned.get('mortgage_program') and (location or self.instance.region_id is not None):
            same_region = Q()
            if location:
                same_region |= Q(region_location=location)
            if self.instance.region_id is not None:
                same_region |= Q(region_id=self.instance.region_id)
            if MortgageProgramRegionalCreditLimit.objects.filter(
                same_region, mortgage_program=cleaned['mortgage_program'],
            ).exclude(pk=self.instance.pk).exists():
                self.add_error('region_location', 'Для этой программы лимит региона уже существует.')
        return cleaned


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


class DeveloperMortgageProgramImportForm(forms.Form):
    """Validates an uploaded normalized developer program workbook."""

    maximum_file_size = 15 * 1024 * 1024
    workbook_file = forms.FileField(
        label='Файл XLSX',
        widget=forms.ClearableFileInput(
            attrs={
                'accept': '.xlsx',
                'class': 'form-control',
            }
        ),
    )

    def clean_workbook_file(self):
        """Reject unsupported extensions and unexpectedly large files."""
        workbook_file = self.cleaned_data['workbook_file']
        if not workbook_file.name.casefold().endswith('.xlsx'):
            raise ValidationError('Поддерживаются только файлы XLSX.')
        if workbook_file.size > self.maximum_file_size:
            raise ValidationError(
                'Размер файла не должен превышать 15 МБ.'
            )
        return workbook_file


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
