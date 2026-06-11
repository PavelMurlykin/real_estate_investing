from decimal import Decimal

import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def migrate_preferential_program_credit_limits(apps, schema_editor):
    """Переносит старые типы программ в базовые кредитные лимиты."""
    mortgage_program_model = apps.get_model('bank', 'MortgageProgram')
    mortgage_program_model.objects.filter(
        preferential_program_type='information_technology',
        credit_limit__isnull=True,
    ).update(credit_limit=Decimal('9000000'))
    mortgage_program_model.objects.filter(
        preferential_program_type='family',
        credit_limit__isnull=True,
    ).update(credit_limit=Decimal('6000000'))


class Migration(migrations.Migration):
    """Добавляет кредитные лимиты ипотечных программ."""

    dependencies = [
        ('bank', '0003_mortgageprogram_preferential_program_type'),
        ('location', '0003_metroline_migrate_metro'),
    ]

    operations = [
        migrations.AddField(
            model_name='mortgageprogram',
            name='credit_limit',
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                max_digits=15,
                null=True,
                validators=[
                    django.core.validators.MinValueValidator(Decimal('0'))
                ],
                verbose_name='Кредитный лимит',
            ),
        ),
        migrations.RunPython(
            migrate_preferential_program_credit_limits,
            migrations.RunPython.noop,
        ),
        migrations.RemoveField(
            model_name='mortgageprogram',
            name='preferential_program_type',
        ),
        migrations.CreateModel(
            name='MortgageProgramRegionalCreditLimit',
            fields=[
                (
                    'id',
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name='ID',
                    ),
                ),
                (
                    'is_active',
                    models.BooleanField(
                        default=True,
                        help_text='Снимите галочку, чтобы скрыть запись.',
                        verbose_name='Активно',
                    ),
                ),
                (
                    'created_at',
                    models.DateTimeField(
                        auto_now_add=True,
                        verbose_name='Дата создания',
                    ),
                ),
                (
                    'updated_at',
                    models.DateTimeField(
                        auto_now=True,
                        verbose_name='Дата изменения',
                    ),
                ),
                (
                    'credit_limit',
                    models.DecimalField(
                        decimal_places=2,
                        max_digits=15,
                        validators=[
                            django.core.validators.MinValueValidator(
                                Decimal('0')
                            )
                        ],
                        verbose_name='Кредитный лимит',
                    ),
                ),
                (
                    'mortgage_program',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='regional_credit_limits',
                        to='bank.mortgageprogram',
                        verbose_name='Ипотечная программа',
                    ),
                ),
                (
                    'region',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='mortgage_program_credit_limits',
                        to='location.region',
                        verbose_name='Регион',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Региональный лимит ипотечной программы',
                'verbose_name_plural': 'Региональные лимиты ипотечных программ',
                'db_table': 'mortgage_program_regional_credit_limit',
                'ordering': ['mortgage_program__name', 'region__name'],
                'abstract': False,
                'constraints': [
                    models.UniqueConstraint(
                        fields=('mortgage_program', 'region'),
                        name='unique_mortgage_program_region_credit_limit',
                    )
                ],
            },
        ),
    ]
