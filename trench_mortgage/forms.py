from datetime import date

from django import forms

from property.models import Property


class TrenchMortgageForm(forms.Form):
    PROPERTY = forms.ModelChoiceField(
        queryset=Property.objects.all(),
        label="Объект недвижимости",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    DISCOUNT_MARKUP_TYPE = forms.ChoiceField(
        choices=[("discount", "Скидка"), ("markup", "Удорожание")],
        label="Тип изменения цены",
        widget=forms.RadioSelect,
        initial="discount",
    )
    DISCOUNT_MARKUP_VALUE = forms.DecimalField(
        label="Значение, %",
        min_value=0,
        max_digits=5,
        decimal_places=2,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    INITIAL_PAYMENT_PERCENT = forms.DecimalField(
        label="Первоначальный взнос, %",
        min_value=0,
        max_value=100,
        max_digits=5,
        decimal_places=2,
        widget=forms.NumberInput(attrs={"class": "form-control", "step": "0.01"}),
    )
    INITIAL_PAYMENT_DATE = forms.DateField(
        label="Дата первоначального взноса",
        initial=date.today,
        widget=forms.DateInput(attrs={"class": "form-control", "type": "date"}),
    )
    MORTGAGE_TERM = forms.IntegerField(
        label="Срок кредита, лет",
        min_value=1,
        max_value=50,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    TRENCH_COUNT = forms.TypedChoiceField(
        label="Количество траншей",
        choices=[(i, str(i)) for i in range(1, 6)],
        coerce=int,
        empty_value=1,
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DISCOUNT_MARKUP_VALUE") is None:
            cleaned_data["DISCOUNT_MARKUP_VALUE"] = 0
        return cleaned_data
