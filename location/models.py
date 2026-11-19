import uuid

from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models

from core.models import BaseModel


class LocationType(models.Model):
    """Describe a geographic level independently of its display name."""

    code = models.CharField(max_length=80, unique=True)
    category = models.CharField(max_length=24, db_index=True, choices=[
        ('region', 'Регион'), ('district', 'Административный район'),
        ('locality', 'Населённый пункт'), ('area', 'Административная территория'),
    ])
    name = models.CharField(max_length=150)
    abbreviation = models.CharField(max_length=40, blank=True)

    def __str__(self):
        """Return the official geographic type."""
        return self.name


class Location(BaseModel):
    """Store one canonical geographic territory with a flexible parent chain."""

    name = models.CharField(max_length=255, db_index=True)
    location_type = models.ForeignKey(LocationType, on_delete=models.PROTECT)
    parent = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='children',
    )
    region = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.PROTECT, related_name='regional_locations',
    )
    source_status = models.CharField(max_length=20, default='unverified')
    source_version = models.CharField(max_length=80, blank=True)
    needs_review = models.BooleanField(default=False)

    class Meta:
        """Keep homonyms distinct and index the most frequent scoped search."""

        ordering = ['name', 'pk']
        indexes = [models.Index(fields=['region', 'name'], name='location_region_name_idx')]

    def __str__(self):
        """Return the source spelling without inventing a hierarchy level."""
        return self.name

    def clean(self):
        """Reject cycles and parents from a different cached subject."""
        super().clean()
        ancestor, seen = self.parent, {self.pk} if self.pk else set()
        while ancestor:
            if ancestor.pk in seen:
                raise ValidationError({'parent': 'Цикл в административной иерархии.'})
            seen.add(ancestor.pk)
            if self.region_id and ancestor.region_id != self.region_id:
                raise ValidationError({'parent': 'Родительская территория относится к другому региону.'})
            ancestor = ancestor.parent


class LocationIdentifier(models.Model):
    """Attach multiple source identities to one canonical territory."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='identifiers')
    provider = models.CharField(max_length=40)
    value = models.CharField(max_length=200)

    class Meta:
        """Require a source identity to resolve to exactly one territory."""

        constraints = [models.UniqueConstraint(
            fields=['provider', 'value'], name='unique_location_source_identity',
        )]


class LocationAlias(models.Model):
    """Preserve historical and manually maintained names for searching."""

    location = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='aliases')
    name = models.CharField(max_length=255, db_index=True)

    class Meta:
        """Avoid duplicating an alias on the same geographic object."""

        constraints = [models.UniqueConstraint(
            fields=['location', 'name'], name='unique_location_alias',
        )]


class LocationClosure(models.Model):
    """Index ancestor searches without recursive work for every result row."""

    ancestor = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='descendant_links')
    descendant = models.ForeignKey(Location, on_delete=models.CASCADE, related_name='ancestor_links')
    depth = models.PositiveSmallIntegerField()

    class Meta:
        """Store one path distance for each pair in the geographic tree."""

        constraints = [models.UniqueConstraint(
            fields=['ancestor', 'descendant'], name='unique_location_ancestor',
        )]


class LegacyLocationMapping(models.Model):
    """Preserve old primary keys while mapping several roles to one territory."""

    model_name = models.CharField(max_length=30)
    legacy_id = models.PositiveBigIntegerField()
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name='legacy_mappings')
    method = models.CharField(max_length=30, default='preserved')
    legacy_name = models.CharField(max_length=255, blank=True)
    legacy_code = models.CharField(max_length=10, blank=True)
    legacy_source_identifier = models.CharField(max_length=200, blank=True)

    class Meta:
        """Keep legacy identifiers unambiguous within their original model."""

        constraints = [models.UniqueConstraint(
            fields=['model_name', 'legacy_id'], name='unique_legacy_location_mapping',
        )]


class Municipality(BaseModel):
    """Keep municipal divisions separate from geographic administrative districts."""

    name = models.CharField(max_length=255)
    municipality_type = models.CharField(max_length=100)
    identifier = models.CharField(max_length=200, unique=True)
    parent = models.ForeignKey('self', null=True, blank=True, on_delete=models.PROTECT)
    region = models.ForeignKey(Location, on_delete=models.PROTECT)
    locations = models.ManyToManyField(Location, related_name='municipalities', blank=True)


class MetroSystem(BaseModel):
    """Group metro lines without restricting stations to one locality."""

    name = models.CharField(max_length=150, unique=True)
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT)

    class Meta:
        """Keep network selectors ordered by their public name."""

        ordering = ['name', 'pk']
        verbose_name = 'Система метро'
        verbose_name_plural = 'Системы метро'


class LocationImportJob(models.Model):
    """Persist a resumable national import independently of browser requests."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    scope = models.CharField(max_length=20, default='russia', editable=False)
    status = models.CharField(max_length=20, default='queued', choices=[
        ('queued', 'В очереди'), ('running', 'Выполняется'),
        ('completed', 'Завершён'), ('failed', 'Ошибка'),
    ])
    phase = models.CharField(max_length=20, default='catalog')
    catalog = models.JSONField(default=list)
    counts = models.JSONField(default=dict)
    coverage = models.JSONField(default=dict)
    processed_cities = models.PositiveIntegerField(default=0)
    total_cities = models.PositiveIntegerField(default=0)
    current_city = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    kind = models.CharField(max_length=20, default='gar')
    source_version = models.CharField(max_length=80, blank=True)
    source_url = models.URLField(max_length=500, blank=True)
    processed_regions = models.PositiveSmallIntegerField(default=0)
    total_regions = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Allow only one queued or running national import at a time."""

        ordering = ['-created_at']
        constraints = [models.UniqueConstraint(
            fields=['scope'], condition=models.Q(status__in=['queued', 'running']),
            name='unique_active_location_import',
        )]


class ImportedLocation(BaseModel):
    """Keep stable source identities without changing existing primary keys."""

    source_identifier = models.CharField(
        max_length=200,
        unique=True,
        null=True,
        blank=True,
        editable=False,
        verbose_name='Идентификатор источника',
    )

    class Meta(BaseModel.Meta):
        """Keep source metadata abstract for location dictionaries."""

        abstract = True


class Region(ImportedLocation):
    """
    Справочник регионов.
    """

    name = models.CharField(max_length=100, unique=True, verbose_name='Регион')
    code = models.CharField(
        max_length=10, unique=True, verbose_name='Код региона'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'region'
        verbose_name = 'Регион'
        verbose_name_plural = 'Регионы'
        ordering = ['name']

    def __str__(self):
        """Возвращает название региона."""
        return self.name


class City(ImportedLocation):
    """
    Справочник городов.
    """

    name = models.CharField(max_length=100, verbose_name='Город')
    region = models.ForeignKey(
        Region, on_delete=models.PROTECT, verbose_name='Регион'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'city'
        verbose_name = 'Город'
        verbose_name_plural = 'Города'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'region'],
                name='unique_city_name_region',
            ),
        ]

    def __str__(self):
        """Возвращает название города."""
        return self.name


class District(ImportedLocation):
    """
    Справочник районов городов.
    """

    name = models.CharField(max_length=100, verbose_name='Район')
    city = models.ForeignKey(
        City, on_delete=models.PROTECT, verbose_name='Город'
    )

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'district'
        verbose_name = 'Район'
        verbose_name_plural = 'Районы'
        ordering = ['name']
        constraints = [
            models.UniqueConstraint(
                fields=['name', 'city'],
                name='unique_district_name_city',
            ),
        ]

    def __str__(self):
        """Возвращает название района."""
        return self.name


class MetroLine(ImportedLocation):
    """
    Справочник линий метро.
    """

    line = models.CharField(max_length=100, verbose_name='Линия')
    line_color = models.CharField(
        max_length=7,
        verbose_name='Цвет линии (RGB)',
        help_text='Код цвета линии в формате #RRGGBB.',
        validators=[
            RegexValidator(
                r'^#[0-9A-Fa-f]{6}$',
                'Введите цвет в формате #RRGGBB.',
            )
        ],
    )
    city = models.ForeignKey(
        City, null=True, blank=True, on_delete=models.PROTECT, verbose_name='Прежний город'
    )
    system = models.ForeignKey(MetroSystem, null=True, blank=True, on_delete=models.PROTECT)

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'metro_line'
        verbose_name = 'Линия метро'
        verbose_name_plural = 'Линии метро'
        ordering = ['system__name', 'line']
        constraints = [
            models.UniqueConstraint(
                fields=['line', 'city'],
                name='unique_metro_line_line_city',
            ),
            models.UniqueConstraint(
                fields=['line', 'system'], name='unique_metro_line_system',
                condition=models.Q(system__isnull=False),
            ),
        ]

    def __str__(self):
        """Возвращает строковое представление линии метро."""
        territory = self.system or self.city or 'система не указана'
        return f'{self.line} ({territory})'


class Metro(ImportedLocation):
    """
    Справочник станций метро.
    """

    station = models.CharField(max_length=100, verbose_name='Станция')
    metro_line = models.ForeignKey(
        MetroLine, on_delete=models.PROTECT, verbose_name='Линия метро'
    )
    location = models.ForeignKey(Location, null=True, blank=True, on_delete=models.PROTECT)
    location_is_inferred = models.BooleanField(
        default=True, verbose_name='Территория определена по системе метро',
    )
    lines = models.ManyToManyField(MetroLine, related_name='stations', blank=True)

    class Meta(BaseModel.Meta):
        """
        Метаданные таблицы.
        """

        db_table = 'metro'
        verbose_name = 'Метро'
        verbose_name_plural = 'Метро'
        ordering = ['metro_line__system__name', 'metro_line__line', 'station']
        constraints = [
            models.UniqueConstraint(
                fields=['station', 'metro_line'],
                name='unique_metro_station_line',
            ),
        ]

    def __str__(self):
        """Возвращает строковое представление станции метро."""
        return f'{self.station} ({self.metro_line.line})'
