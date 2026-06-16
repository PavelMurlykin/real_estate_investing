from django.db import models


class BaseModel(models.Model):
    """
    Абстрактная модель.
    Добавляет флаг is_active и временные метки created_at, updated_at.
    """

    is_active = models.BooleanField(
        default=True,
        db_index=True,
        verbose_name='Активно',
        help_text='Снимите галочку, чтобы скрыть запись.',
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        db_index=True,
        verbose_name='Дата создания',
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Дата изменения',
    )

    class Meta:
        """
        Метаданные абстрактного класса.
        """

        abstract = True
