import django.db.models.deletion
from django.db import migrations, models


def migrate_trench_mortgage_terms(apps, schema_editor):
    """Convert saved trench mortgage terms from years to months."""
    calculation_model = apps.get_model(
        'trench_mortgage', 'TrenchMortgageCalculation'
    )
    trench_model = apps.get_model('trench_mortgage', 'Trench')

    for calculation in calculation_model.objects.all():
        calculation.base_property_cost = calculation.final_property_cost
        first_trench = (
            trench_model.objects.filter(calculation=calculation)
            .order_by('trench_number')
            .first()
        )
        if first_trench is not None:
            calculation.annual_rate = first_trench.annual_rate
        calculation.mortgage_term = calculation.mortgage_term * 12
        calculation.save(
            update_fields=[
                'base_property_cost',
                'annual_rate',
                'mortgage_term',
            ]
        )


def rollback_trench_mortgage_terms(apps, schema_editor):
    """Convert saved trench mortgage terms from months back to years."""
    calculation_model = apps.get_model(
        'trench_mortgage', 'TrenchMortgageCalculation'
    )
    for calculation in calculation_model.objects.all():
        calculation.mortgage_term = calculation.mortgage_term // 12
        calculation.save(update_fields=['mortgage_term'])


class Migration(migrations.Migration):
    """Align trench mortgage saved calculations with mortgage calculations."""

    dependencies = [
        ('trench_mortgage', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='trenchmortgagecalculation',
            name='annual_rate',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=5,
                verbose_name='Годовая ставка, %',
            ),
        ),
        migrations.AddField(
            model_name='trenchmortgagecalculation',
            name='base_property_cost',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=15,
                verbose_name='Базовая стоимость объекта, руб.',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='trenchmortgagecalculation',
            name='discount_markup_type',
            field=models.CharField(
                choices=[
                    ('discount', 'Скидка'),
                    ('markup', 'Удорожание'),
                ],
                default='discount',
                max_length=10,
                verbose_name='Тип изменения цены',
            ),
        ),
        migrations.AddField(
            model_name='trenchmortgagecalculation',
            name='discount_markup_value',
            field=models.DecimalField(
                decimal_places=2,
                default=0,
                max_digits=5,
                verbose_name='Значение, %',
            ),
        ),
        migrations.RunPython(
            migrate_trench_mortgage_terms,
            rollback_trench_mortgage_terms,
        ),
        migrations.AlterField(
            model_name='trenchmortgagecalculation',
            name='mortgage_term',
            field=models.IntegerField(verbose_name='Срок кредита, мес.'),
        ),
        migrations.AlterField(
            model_name='trenchmortgagecalculation',
            name='property',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to='property.property',
                verbose_name='Объект',
            ),
        ),
    ]
