from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from core.models import BaseModel
from location.models import Region

from .program_matching import normalize_mortgage_program_match_name


class Bank(BaseModel):
    """Банк, выдающий ипотечные программы."""

    name = models.CharField(
        max_length=255, unique=True, verbose_name='Название'
    )
    logo_url = models.URLField(
        max_length=1000,
        blank=True,
        default='',
        verbose_name='Логотип',
    )
    mortgage_programs = models.ManyToManyField(
        'MortgageProgram',
        through='BankProgram',
        related_name='banks',
        verbose_name='Ипотечные программы',
    )

    class Meta(BaseModel.Meta):
        """Метаданные таблицы банков."""

        db_table = 'bank'
        verbose_name = 'Банк'
        verbose_name_plural = 'Банки'
        ordering = ['name']

    def __str__(self):
        """Возвращает название банка."""
        return self.name


class MortgageProgram(BaseModel):
    """Ипотечная программа банка."""

    name = models.CharField(
        max_length=255, unique=True, verbose_name='Название'
    )
    condition = models.TextField(verbose_name='Условие')
    is_preferential = models.BooleanField(
        default=False, verbose_name='Льготная программа'
    )
    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Кредитный лимит',
    )

    class Meta(BaseModel.Meta):
        """Метаданные таблицы ипотечных программ."""

        db_table = 'mortgage_program'
        verbose_name = 'Ипотечная программа'
        verbose_name_plural = 'Ипотечные программы'
        ordering = ['name']

    def __str__(self):
        """Возвращает название ипотечной программы."""
        return self.name

    def get_credit_limit(self, region=None):
        """Возвращает лимит суммы кредита для льготной программы."""
        if not self.is_preferential:
            return None

        if region is None:
            return self.credit_limit

        region_id = getattr(region, 'pk', region)
        prefetched_credit_limits = getattr(
            self, '_prefetched_objects_cache', {}
        ).get('regional_credit_limits')
        if prefetched_credit_limits is not None:
            for regional_credit_limit in prefetched_credit_limits:
                if (
                    regional_credit_limit.is_active
                    and regional_credit_limit.region_id == region_id
                ):
                    return regional_credit_limit.credit_limit
            return self.credit_limit

        regional_credit_limit = (
            self.regional_credit_limits.filter(
                region_id=region_id,
                is_active=True,
            )
            .values_list('credit_limit', flat=True)
            .first()
        )
        if regional_credit_limit is not None:
            return regional_credit_limit

        return self.credit_limit


class MortgageProgramRegionalCreditLimit(BaseModel):
    """Региональное исключение кредитного лимита ипотечной программы."""

    mortgage_program = models.ForeignKey(
        MortgageProgram,
        on_delete=models.CASCADE,
        related_name='regional_credit_limits',
        verbose_name='Ипотечная программа',
    )
    region = models.ForeignKey(
        Region,
        on_delete=models.PROTECT,
        related_name='mortgage_program_credit_limits',
        verbose_name='Регион',
    )
    credit_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Кредитный лимит',
    )

    class Meta(BaseModel.Meta):
        """Метаданные региональных исключений кредитного лимита."""

        db_table = 'mortgage_program_regional_credit_limit'
        verbose_name = 'Региональный лимит ипотечной программы'
        verbose_name_plural = 'Региональные лимиты ипотечных программ'
        ordering = ['mortgage_program__name', 'region__name']
        constraints = [
            models.UniqueConstraint(
                fields=['mortgage_program', 'region'],
                name='unique_mortgage_program_region_credit_limit',
            )
        ]

    def __str__(self):
        """Возвращает строковое представление регионального лимита."""
        return (
            f'{self.mortgage_program} - {self.region}: '
            f'{self.credit_limit}'
        )


class MortgageProgramAlias(BaseModel):
    """Alias that maps imported program names to a canonical program."""

    mortgage_program = models.ForeignKey(
        MortgageProgram,
        on_delete=models.CASCADE,
        related_name='aliases',
        verbose_name='Эталонная ипотечная программа',
    )
    source_name = models.CharField(
        max_length=255,
        verbose_name='Написание из источника',
    )
    normalized_name = models.CharField(
        max_length=255,
        unique=True,
        editable=False,
        verbose_name='Ключ сопоставления',
    )
    source = models.CharField(
        max_length=255,
        blank=True,
        default='',
        verbose_name='Источник',
    )

    class Meta(BaseModel.Meta):
        """Метаданные алиасов ипотечных программ."""

        db_table = 'mortgage_program_alias'
        verbose_name = 'Алиас ипотечной программы'
        verbose_name_plural = 'Алиасы ипотечных программ'
        ordering = ['mortgage_program__name', 'source_name']

    def save(self, *args, **kwargs):
        """Populate the normalized matching key before saving."""
        self.normalized_name = normalize_mortgage_program_match_name(
            self.source_name
        )
        super().save(*args, **kwargs)

    def __str__(self):
        """Return a readable alias mapping."""
        return f'{self.source_name} -> {self.mortgage_program}'


class BankProgram(BaseModel):
    """Связь банка с доступной ипотечной программой."""

    bank = models.ForeignKey(
        Bank, on_delete=models.CASCADE, verbose_name='Банк'
    )
    mortgage_program = models.ForeignKey(
        MortgageProgram,
        on_delete=models.PROTECT,
        verbose_name='Ипотечная программа',
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Процентная ставка, %',
    )
    minimum_initial_payment_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Минимальный первый взнос, %',
    )
    maximum_loan_term_years = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name='Максимальный срок кредита, лет',
    )

    class Meta(BaseModel.Meta):
        """Метаданные таблицы программ банков."""

        db_table = 'bank_program'
        verbose_name = 'Программа банка'
        verbose_name_plural = 'Программы банков'
        ordering = ['bank__name', 'mortgage_program__name']
        constraints = [
            models.UniqueConstraint(
                fields=['bank', 'mortgage_program'],
                name='unique_bank_program_pair',
            ),
        ]

    def __str__(self):
        """Возвращает связку банка и ипотечной программы."""
        return f'{self.bank} - {self.mortgage_program}'


class DeveloperMortgageProgram(BaseModel):
    """Условия ипотечной программы для группы компаний или отдельного ЖК."""

    company_group = models.ForeignKey(
        'property.CompanyGroup',
        on_delete=models.PROTECT,
        related_name='developer_mortgage_programs',
        verbose_name='Группа компаний',
    )
    real_estate_complex = models.ForeignKey(
        'property.RealEstateComplex',
        on_delete=models.PROTECT,
        related_name='developer_mortgage_programs',
        null=True,
        blank=True,
        verbose_name='ЖК',
    )
    bank = models.ForeignKey(
        Bank,
        on_delete=models.PROTECT,
        related_name='developer_mortgage_programs',
        verbose_name='Банк',
    )
    mortgage_program = models.ForeignKey(
        MortgageProgram,
        on_delete=models.PROTECT,
        related_name='developer_mortgage_programs',
        verbose_name='Ипотечная программа',
    )
    price_increase_percent = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal('0'),
        null=True,
        blank=True,
        verbose_name='Удорожание, %',
    )
    grace_period_months = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name='Срок льготного периода, мес.',
    )
    grace_period_interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('100')),
        ],
        verbose_name='Ставка на льготный период, % годовых',
    )
    minimum_initial_payment_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('100')),
        ],
        verbose_name='Первоначальный взнос, %',
    )
    interest_rate = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('100')),
        ],
        verbose_name='Годовая ставка, %',
    )
    maximum_loan_term_years = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        validators=[MinValueValidator(1)],
        verbose_name='Максимальный срок кредита, лет',
    )
    maximum_loan_amount = models.DecimalField(
        max_digits=15,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal('0'))],
        verbose_name='Максимальная сумма кредита',
    )
    rate_discount_percent = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[
            MinValueValidator(Decimal('0')),
            MaxValueValidator(Decimal('100')),
        ],
        verbose_name='Дисконт к ставке, п. п.',
    )
    source_key = models.CharField(
        max_length=64,
        null=True,
        blank=True,
        unique=True,
        editable=False,
        verbose_name='Ключ записи источника',
    )
    source_record_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        editable=False,
        verbose_name='ID записи источника',
    )
    source_sheet_row = models.PositiveIntegerField(
        null=True,
        blank=True,
        db_index=True,
        editable=False,
        verbose_name='Строка исходной таблицы',
    )
    source_program_column = models.CharField(
        max_length=1,
        blank=True,
        default='',
        editable=False,
        verbose_name='Столбец программы источника',
    )
    source_program_variant_index = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        editable=False,
        verbose_name='Номер варианта программы источника',
    )

    class Meta(BaseModel.Meta):
        """Метаданные ипотечных программ застройщиков."""

        db_table = 'developer_mortgage_program'
        verbose_name = 'Ипотечная программа застройщика'
        verbose_name_plural = 'Ипотечные программы застройщиков'
        ordering = [
            'company_group__name',
            'real_estate_complex__name',
            'bank__name',
            'mortgage_program__name',
        ]
        indexes = [
            models.Index(
                fields=['company_group', 'bank', 'mortgage_program'],
                name='dev_mort_group_bank_idx',
            ),
        ]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(grace_period_months__isnull=True)
                    | models.Q(grace_period_months__gte=1)
                ),
                name='dev_mort_grace_months_positive',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(grace_period_interest_rate__isnull=True)
                    | models.Q(
                        grace_period_interest_rate__gte=Decimal('0'),
                        grace_period_interest_rate__lte=Decimal('100'),
                    )
                ),
                name='dev_mort_grace_rate_range',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(minimum_initial_payment_percent__isnull=True)
                    | models.Q(
                        minimum_initial_payment_percent__gte=Decimal('0'),
                        minimum_initial_payment_percent__lte=Decimal('100'),
                    )
                ),
                name='dev_mort_initial_payment_range',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(interest_rate__isnull=True)
                    | models.Q(
                        interest_rate__gte=Decimal('0'),
                        interest_rate__lte=Decimal('100'),
                    )
                ),
                name='dev_mort_interest_rate_range',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(rate_discount_percent__isnull=True)
                    | models.Q(
                        rate_discount_percent__gte=Decimal('0'),
                        rate_discount_percent__lte=Decimal('100'),
                    )
                ),
                name='dev_mort_discount_range',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(maximum_loan_term_years__isnull=True)
                    | models.Q(maximum_loan_term_years__gte=1)
                ),
                name='dev_mort_max_term_positive',
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(maximum_loan_amount__isnull=True)
                    | models.Q(maximum_loan_amount__gte=Decimal('0'))
                ),
                name='dev_mort_max_amount_nonnegative',
            ),
        ]

    def clean(self):
        """Проверяет принадлежность выбранного ЖК группе компаний."""
        super().clean()
        if not self.company_group_id or not self.real_estate_complex_id:
            return

        real_estate_complex_model = self._meta.get_field(
            'real_estate_complex'
        ).remote_field.model
        complex_company_group_id = (
            real_estate_complex_model.objects.filter(
                pk=self.real_estate_complex_id
            )
            .values_list('developer__company_group_id', flat=True)
            .first()
        )
        if complex_company_group_id != self.company_group_id:
            raise ValidationError(
                {
                    'real_estate_complex': (
                        'Выбранный ЖК не относится к указанной группе '
                        'компаний.'
                    )
                }
            )

    def __str__(self):
        """Возвращает программу с областью действия и банком."""
        scope = self.real_estate_complex or 'Все ЖК группы'
        return (
            f'{self.company_group} / {scope} / '
            f'{self.bank} / {self.mortgage_program}'
        )


class KeyRate(BaseModel):
    """Ключевая ставка на дату заседания."""

    meeting_date = models.DateField(unique=True, verbose_name='Дата заседания')
    key_rate = models.DecimalField(
        max_digits=5, decimal_places=2, verbose_name='Ключевая ставка, %'
    )

    class Meta(BaseModel.Meta):
        """Метаданные таблицы ключевых ставок."""

        db_table = 'key_rate'
        verbose_name = 'Ключевая ставка'
        verbose_name_plural = 'Ключевые ставки'
        ordering = ['-meeting_date']

    def __str__(self):
        """Возвращает дату и размер ключевой ставки."""
        return f'{self.meeting_date}: {self.key_rate}%'
