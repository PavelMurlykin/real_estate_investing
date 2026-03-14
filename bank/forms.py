from decimal import Decimal

from django import forms

from .models import Bank


class BankForm(forms.ModelForm):
    """Описание класса BankForm.

    Инкапсулирует данные и поведение, необходимые для работы компонента
    в данном модуле.
    """

    salary_client_rate = forms.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0'),
        label='Процентная ставка для зарплатных клиентов, %',
    )

    class Meta:
        """Описание служебного класса Meta.

        Определяет метаданные и параметры конфигурации для родительского
        класса Django.
        """

        model = Bank
        fields = ('name', 'interest_rate')
        labels = {
            'name': 'Название',
            'interest_rate': 'Процентная ставка, %',
        }

    def __init__(self, *args, **kwargs):
        """Описание метода __init__.

        Инициализирует экземпляр класса и подготавливает его внутреннее
        состояние.

        Аргументы:
            *args: Входной параметр, влияющий на работу метода.
            **kwargs: Входной параметр, влияющий на работу метода.

        Возвращает:
            None: Заполняет атрибуты текущего экземпляра.
        """
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['salary_client_rate'].initial = (
                self.instance.interest_rate
                - self.instance.salary_client_discount
            )

    def clean(self):
        """Описание метода clean.

        Валидирует и нормализует входные данные перед сохранением.

        Возвращает:
            Any: Возвращает очищенные данные или значение поля в зависимости
        от контекста.
        """
        cleaned_data = super().clean()
        interest_rate = cleaned_data.get('interest_rate')
        salary_client_rate = cleaned_data.get('salary_client_rate')

        if (
            interest_rate is not None
            and salary_client_rate is not None
            and salary_client_rate > interest_rate
        ):
            self.add_error(
                'salary_client_rate',
                (
                    'Ставка для зарплатных клиентов не может быть выше '
                    'базовой ставки.'
                ),
            )

        return cleaned_data

    def save(self, commit=True):
        """Описание метода save.

        Сохраняет объект и связанные вычисленные значения.

        Аргументы:
            commit: Входной параметр, влияющий на работу метода.

        Возвращает:
            Any: Результат стандартного механизма сохранения.
        """
        bank = super().save(commit=False)
        salary_client_rate = self.cleaned_data['salary_client_rate']
        bank.salary_client_discount = bank.interest_rate - salary_client_rate
        bank.is_active = True

        if commit:
            bank.save()

        return bank
