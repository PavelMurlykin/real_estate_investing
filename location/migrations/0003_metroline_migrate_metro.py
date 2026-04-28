import django.core.validators
import django.db.models.deletion
from django.db import migrations, models


def move_metro_lines(apps, schema_editor):
    Metro = apps.get_model('location', 'Metro')
    MetroLine = apps.get_model('location', 'MetroLine')

    for station in Metro.objects.all():
        metro_line, _ = MetroLine.objects.get_or_create(
            line=station.line,
            city_id=station.city_id,
            defaults={
                'line_color': station.line_color,
                'is_active': station.is_active,
            },
        )
        station.metro_line_id = metro_line.pk
        station.save(update_fields=['metro_line'])


class Migration(migrations.Migration):

    dependencies = [
        ('location', '0002_metro'),
    ]

    operations = [
        migrations.CreateModel(
            name='MetroLine',
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
                        auto_now_add=True, verbose_name='Дата создания'
                    ),
                ),
                (
                    'updated_at',
                    models.DateTimeField(
                        auto_now=True, verbose_name='Дата изменения'
                    ),
                ),
                (
                    'line',
                    models.CharField(max_length=100, verbose_name='Линия'),
                ),
                (
                    'line_color',
                    models.CharField(
                        help_text='Код цвета линии в формате #RRGGBB.',
                        max_length=7,
                        validators=[
                            django.core.validators.RegexValidator(
                                '^#[0-9A-Fa-f]{6}$',
                                'Введите цвет в формате #RRGGBB.',
                            )
                        ],
                        verbose_name='Цвет линии (RGB)',
                    ),
                ),
                (
                    'city',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to='location.city',
                        verbose_name='Город',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Линия метро',
                'verbose_name_plural': 'Линии метро',
                'db_table': 'metro_line',
                'ordering': ['city__name', 'line'],
                'abstract': False,
                'unique_together': {('line', 'city')},
            },
        ),
        migrations.AddField(
            model_name='metro',
            name='metro_line',
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='location.metroline',
                verbose_name='Линия метро',
            ),
        ),
        migrations.RunPython(move_metro_lines, migrations.RunPython.noop),
        migrations.AlterUniqueTogether(
            name='metro',
            unique_together={('station', 'metro_line')},
        ),
        migrations.AlterField(
            model_name='metro',
            name='metro_line',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                to='location.metroline',
                verbose_name='Линия метро',
            ),
        ),
        migrations.RemoveField(
            model_name='metro',
            name='line_color',
        ),
        migrations.RemoveField(
            model_name='metro',
            name='line',
        ),
        migrations.RemoveField(
            model_name='metro',
            name='city',
        ),
        migrations.AlterModelOptions(
            name='metro',
            options={
                'ordering': [
                    'metro_line__city__name',
                    'metro_line__line',
                    'station',
                ],
                'verbose_name': 'Метро',
                'verbose_name_plural': 'Метро',
            },
        ),
    ]
