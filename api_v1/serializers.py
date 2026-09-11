from copy import copy
from decimal import Decimal
from urllib.parse import urlencode

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.db import transaction
from django.urls import reverse
from django.utils import timezone
from rest_framework import serializers

from bank.models import MortgageProgram
from customer.models import Customer
from location.models import City, District, Metro, MetroLine, Region
from property.models import (
    ApartmentDecoration,
    ApartmentLayout,
    CompanyGroup,
    Developer,
    Property,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateComplexMetroAvailability,
    RealEstateType,
    TransportAccessibilityType,
    WindowView,
)
from property.validators import validate_property_image_upload

from .customer_service import build_customer_financial_capacity


class LoginRequestSerializer(serializers.Serializer):
    """Validate credentials submitted by the React frontend."""

    identifier = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


class CustomerListQuerySerializer(serializers.Serializer):
    """Validate URL-driven customer search, ordering, and pagination."""

    ORDERING_CHOICES = (
        '-createdAt',
        'createdAt',
        'name',
        '-name',
    )

    q = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    ordering = serializers.ChoiceField(
        required=False,
        choices=ORDERING_CHOICES,
        default='-createdAt',
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )


class CompanyGroupListQuerySerializer(serializers.Serializer):
    """Validate search, ordering, and pagination for company groups."""

    q = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    ordering = serializers.ChoiceField(
        required=False,
        choices=('name', '-name'),
        default='name',
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )


class CompanyGroupSerializer(serializers.ModelSerializer):
    """Serialize and validate a company group catalog entry."""

    developerCount = serializers.IntegerField(
        source='developer_count',
        read_only=True,
    )
    legacyEditUrl = serializers.SerializerMethodField(
        method_name='get_legacy_edit_url'
    )
    legacyDeleteUrl = serializers.SerializerMethodField(
        method_name='get_legacy_delete_url'
    )

    class Meta:
        """Define the stable company group API contract."""

        model = CompanyGroup
        fields = (
            'id',
            'name',
            'developerCount',
            'legacyEditUrl',
            'legacyDeleteUrl',
        )

    def get_legacy_edit_url(self, company_group):
        """Return the preserved Django edit form URL."""
        return reverse(
            'property:company_group_update',
            kwargs={'pk': company_group.pk},
        )

    def get_legacy_delete_url(self, company_group):
        """Return the preserved Django delete form URL."""
        return reverse(
            'property:company_group_delete',
            kwargs={'pk': company_group.pk},
        )


class PropertyDictionaryListQuerySerializer(serializers.Serializer):
    """Validate URL-driven filters for property dictionary entries."""

    q = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    status = serializers.ChoiceField(
        required=False,
        choices=('all', 'active', 'inactive'),
        default='all',
    )
    ordering = serializers.ChoiceField(
        required=False,
        choices=(
            'default', 'name', '-name', 'updatedAt', '-updatedAt',
            'status', '-status', 'weight', '-weight',
        ),
        default='default',
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )


class PropertyDictionaryEntrySerializer(serializers.Serializer):
    """Serialize one entry from a whitelisted property dictionary."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)
    description = serializers.CharField(allow_null=True, read_only=True)
    weight = serializers.SerializerMethodField(method_name='get_weight')
    usageCount = serializers.IntegerField(
        source='usage_count', read_only=True
    )
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    legacyEditUrl = serializers.SerializerMethodField(
        method_name='get_legacy_edit_url'
    )

    def get_weight(self, dictionary_entry):
        """Return a stable decimal coefficient only for class entries."""
        weight = getattr(dictionary_entry, 'weight', None)
        return format(weight, 'f') if weight is not None else None

    def get_legacy_edit_url(self, dictionary_entry):
        """Return the preserved Django inline-edit URL."""
        dictionary_key = self.context['dictionary_configuration']['legacy_key']
        query_string = urlencode(
            {'model': dictionary_key, 'edit': dictionary_entry.pk}
        )
        return f"{reverse('property:dictionary_catalog')}?{query_string}"


class PropertyDictionaryWriteSerializer(serializers.Serializer):
    """Validate and persist one whitelisted property dictionary entry."""

    name = serializers.CharField(max_length=100, trim_whitespace=True)
    description = serializers.CharField(
        required=False,
        allow_blank=True,
        allow_null=True,
        default=None,
    )
    weight = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=5,
        decimal_places=2,
    )
    isActive = serializers.BooleanField(
        source='is_active', required=False, default=True
    )

    def validate_name(self, value):
        """Collapse repeated whitespace without changing the display case."""
        return ' '.join(value.split())

    def validate_description(self, value):
        """Store an empty optional description consistently as null."""
        normalized_value = value.strip() if value else ''
        return normalized_value or None

    def validate(self, attributes):
        """Enforce dictionary shape and case-insensitive unique names."""
        configuration = self.context['dictionary_configuration']
        has_weight = configuration['has_weight']
        current_entry = self.instance

        if has_weight:
            current_weight = (
                current_entry.weight if current_entry is not None else None
            )
            if attributes.get('weight', current_weight) is None:
                raise serializers.ValidationError(
                    {'weight': 'Укажите коэффициент класса.'}
                )
        elif attributes.get('weight') is not None:
            raise serializers.ValidationError(
                {'weight': 'У этого справочника нет коэффициента.'}
            )

        name = attributes.get(
            'name', current_entry.name if current_entry is not None else ''
        )
        duplicate_entries = configuration['model'].objects.filter(
            name__iexact=name
        )
        if current_entry is not None:
            duplicate_entries = duplicate_entries.exclude(pk=current_entry.pk)
        if duplicate_entries.exists():
            raise serializers.ValidationError(
                {'name': 'Запись с таким названием уже существует.'}
            )
        return attributes

    def create(self, validated_data):
        """Create an entry through its whitelisted model configuration."""
        configuration = self.context['dictionary_configuration']
        if not configuration['has_weight']:
            validated_data.pop('weight', None)
        return configuration['model'].objects.create(**validated_data)

    def update(self, instance, validated_data):
        """Update only the fields allowed by the dictionary configuration."""
        configuration = self.context['dictionary_configuration']
        if not configuration['has_weight']:
            validated_data.pop('weight', None)
        for field_name, value in validated_data.items():
            setattr(instance, field_name, value)
        instance.save(update_fields=(*validated_data.keys(), 'updated_at'))
        return instance


class LocationDictionaryListQuerySerializer(serializers.Serializer):
    """Validate filters and pagination for location dictionaries."""

    q = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    status = serializers.ChoiceField(
        required=False,
        choices=('all', 'active', 'inactive'),
        default='all',
    )
    ordering = serializers.ChoiceField(
        required=False,
        choices=(
            'default', 'name', '-name', 'updatedAt', '-updatedAt',
            'status', '-status',
        ),
        default='default',
    )
    regionId = serializers.IntegerField(required=False, min_value=1)
    cityId = serializers.IntegerField(required=False, min_value=1)
    metroLineId = serializers.IntegerField(required=False, min_value=1)
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )


class LocationDictionaryOptionsQuerySerializer(serializers.Serializer):
    """Validate parent identifiers used by dependent location selectors."""

    regionId = serializers.IntegerField(required=False, min_value=1)
    cityId = serializers.IntegerField(required=False, min_value=1)


class LocationDictionaryEntrySerializer(serializers.Serializer):
    """Serialize one entry from a whitelisted location dictionary."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.SerializerMethodField(method_name='get_name')
    code = serializers.SerializerMethodField(method_name='get_code')
    region = serializers.SerializerMethodField(method_name='get_region')
    city = serializers.SerializerMethodField(method_name='get_city')
    metroLine = serializers.SerializerMethodField(
        method_name='get_metro_line'
    )
    usageCount = serializers.IntegerField(
        source='usage_count', read_only=True
    )
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    legacyEditUrl = serializers.SerializerMethodField(
        method_name='get_legacy_edit_url'
    )

    def get_configuration(self):
        """Return the location dictionary configuration for this request."""
        return self.context['dictionary_configuration']

    def get_name(self, dictionary_entry):
        """Return the configured display field under a stable API name."""
        return getattr(
            dictionary_entry,
            self.get_configuration()['name_field'],
        )

    def get_code(self, dictionary_entry):
        """Return the region code only when the model supports it."""
        return getattr(dictionary_entry, 'code', None)

    def get_region(self, dictionary_entry):
        """Return the owning region for nested location entries."""
        if isinstance(dictionary_entry, City):
            region = dictionary_entry.region
        elif isinstance(dictionary_entry, District):
            region = dictionary_entry.city.region
        elif isinstance(dictionary_entry, Metro):
            region = dictionary_entry.metro_line.city.region
        else:
            return None
        return {'id': region.pk, 'name': region.name}

    def get_city(self, dictionary_entry):
        """Return the owning city for districts and metro stations."""
        if isinstance(dictionary_entry, District):
            city = dictionary_entry.city
        elif isinstance(dictionary_entry, Metro):
            city = dictionary_entry.metro_line.city
        else:
            return None
        return {'id': city.pk, 'name': city.name}

    def get_metro_line(self, dictionary_entry):
        """Return metro-line identity and color for station entries."""
        if not isinstance(dictionary_entry, Metro):
            return None
        metro_line = dictionary_entry.metro_line
        return {
            'id': metro_line.pk,
            'name': metro_line.line,
            'color': metro_line.line_color,
        }

    def get_legacy_edit_url(self, dictionary_entry):
        """Return the preserved Django inline-edit URL."""
        query_string = urlencode(
            {
                'model': self.get_configuration()['legacy_key'],
                'edit': dictionary_entry.pk,
            }
        )
        return f"{reverse('location:location_catalog')}?{query_string}"


class LocationDictionaryWriteSerializer(serializers.Serializer):
    """Validate and persist a whitelisted location dictionary entry."""

    name = serializers.CharField(max_length=100, trim_whitespace=True)
    code = serializers.CharField(
        required=False,
        allow_blank=False,
        max_length=10,
        trim_whitespace=True,
    )
    regionId = serializers.IntegerField(required=False, min_value=1)
    cityId = serializers.IntegerField(required=False, min_value=1)
    metroLineId = serializers.IntegerField(required=False, min_value=1)
    isActive = serializers.BooleanField(
        source='is_active', required=False, default=True
    )

    def validate_name(self, value):
        """Collapse repeated whitespace without changing display case."""
        return ' '.join(value.split())

    def validate_code(self, value):
        """Normalize region codes for stable comparisons and display."""
        return value.strip().upper()

    def validate(self, attributes):
        """Resolve parent objects and enforce dictionary-specific uniqueness."""
        configuration = self.context['dictionary_configuration']
        current_entry = self.instance
        dictionary_key = configuration['key']
        relationship_fields = {
            'cities': ('regionId', 'region', Region),
            'districts': ('cityId', 'city', City),
            'metro': ('metroLineId', 'metro_line', MetroLine),
        }
        supported_api_fields = {'name', 'is_active'}
        if dictionary_key == 'regions':
            supported_api_fields.add('code')
        else:
            supported_api_fields.add(relationship_fields[dictionary_key][0])

        for field_name in ('code', 'regionId', 'cityId', 'metroLineId'):
            if (
                field_name in attributes
                and field_name not in supported_api_fields
            ):
                raise serializers.ValidationError(
                    {field_name: 'Поле недоступно для этого справочника.'}
                )

        model_name_field = configuration['name_field']
        if 'name' in attributes:
            attributes[model_name_field] = attributes.pop('name')

        if dictionary_key == 'regions':
            if current_entry is None and 'code' not in attributes:
                raise serializers.ValidationError(
                    {'code': 'Укажите код региона.'}
                )
        else:
            api_field, model_field, parent_model = relationship_fields[
                dictionary_key
            ]
            parent_identifier = attributes.pop(api_field, None)
            if parent_identifier is None and current_entry is None:
                raise serializers.ValidationError(
                    {api_field: 'Выберите связанную запись.'}
                )
            if parent_identifier is not None:
                try:
                    attributes[model_field] = parent_model.objects.get(
                        pk=parent_identifier
                    )
                except parent_model.DoesNotExist as error:
                    raise serializers.ValidationError(
                        {api_field: 'Связанная запись не найдена.'}
                    ) from error

        name = attributes.get(
            model_name_field,
            getattr(current_entry, model_name_field, ''),
        )
        duplicate_filters = {f'{model_name_field}__iexact': name}
        parent_model_field = configuration.get('parent_model_field')
        if parent_model_field:
            current_parent = getattr(
                current_entry,
                parent_model_field,
                None,
            )
            duplicate_filters[parent_model_field] = attributes.get(
                parent_model_field,
                current_parent,
            )
        duplicate_entries = configuration['model'].objects.filter(
            **duplicate_filters
        )
        if current_entry is not None:
            duplicate_entries = duplicate_entries.exclude(pk=current_entry.pk)
        if duplicate_entries.exists():
            raise serializers.ValidationError(
                {'name': 'Запись с таким названием уже существует.'}
            )

        if dictionary_key == 'regions':
            code = attributes.get('code', getattr(current_entry, 'code', ''))
            duplicate_codes = Region.objects.filter(code__iexact=code)
            if current_entry is not None:
                duplicate_codes = duplicate_codes.exclude(pk=current_entry.pk)
            if duplicate_codes.exists():
                raise serializers.ValidationError(
                    {'code': 'Регион с таким кодом уже существует.'}
                )
        return attributes

    def create(self, validated_data):
        """Create an entry through its whitelisted model configuration."""
        configuration = self.context['dictionary_configuration']
        return configuration['model'].objects.create(**validated_data)

    def update(self, instance, validated_data):
        """Update only validated fields and refresh the modification time."""
        for field_name, value in validated_data.items():
            setattr(instance, field_name, value)
        instance.save(update_fields=(*validated_data.keys(), 'updated_at'))
        return instance


class DeveloperListQuerySerializer(serializers.Serializer):
    """Validate URL-driven developer filters and pagination."""

    q = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    companyGroupId = serializers.IntegerField(required=False, min_value=1)
    regionId = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(
        required=False,
        choices=('all', 'active', 'inactive'),
        default='all',
    )
    ordering = serializers.ChoiceField(
        required=False,
        choices=(
            'name',
            '-name',
            'companyGroup',
            '-companyGroup',
            'createdAt',
            '-createdAt',
        ),
        default='name',
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )


class DeveloperPublicSerializer(serializers.ModelSerializer):
    """Serialize the non-sensitive developer directory fields."""

    companyGroup = serializers.SerializerMethodField(
        method_name='get_company_group'
    )
    regions = serializers.SerializerMethodField(method_name='get_regions')
    complexCount = serializers.IntegerField(
        source='complex_count',
        read_only=True,
    )
    isActive = serializers.BooleanField(source='is_active', read_only=True)

    class Meta:
        """Define the public developer list contract."""

        model = Developer
        fields = (
            'id',
            'name',
            'companyGroup',
            'regions',
            'complexCount',
            'isActive',
        )

    def get_company_group(self, developer):
        """Return the optional company group without another query."""
        if not developer.company_group_id:
            return None
        return {
            'id': developer.company_group_id,
            'name': developer.company_group.name,
        }

    def get_regions(self, developer):
        """Return prefetched developer regions in deterministic order."""
        return [
            {'id': region.pk, 'name': region.name}
            for region in sorted(
                developer.regions.all(),
                key=lambda region: (region.name, region.pk),
            )
        ]


class DeveloperSerializer(DeveloperPublicSerializer):
    """Validate mutations and expose full data only to catalog managers."""

    companyGroupId = serializers.PrimaryKeyRelatedField(
        source='company_group',
        queryset=CompanyGroup.objects.order_by('name', 'pk'),
        allow_null=True,
        required=False,
        write_only=True,
    )
    regionIds = serializers.PrimaryKeyRelatedField(
        source='regions',
        queryset=Region.objects.order_by('name', 'pk'),
        many=True,
        required=False,
        write_only=True,
    )
    legalAddress = serializers.CharField(
        source='legal_address',
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    actualAddress = serializers.CharField(
        source='actual_address',
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    taxpayerIdentificationNumber = serializers.CharField(
        source='taxpayer_identification_number',
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    taxRegistrationReasonCode = serializers.CharField(
        source='tax_registration_reason_code',
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    primaryStateRegistrationNumber = serializers.CharField(
        source='primary_state_registration_number',
        allow_blank=True,
        allow_null=True,
        required=False,
    )
    isActive = serializers.BooleanField(source='is_active', required=False)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    legacyEditUrl = serializers.SerializerMethodField(
        method_name='get_legacy_edit_url'
    )
    legacyDeleteUrl = serializers.SerializerMethodField(
        method_name='get_legacy_delete_url'
    )

    class Meta(DeveloperPublicSerializer.Meta):
        """Define the manager-only developer detail contract."""

        fields = DeveloperPublicSerializer.Meta.fields + (
            'description',
            'companyGroupId',
            'regionIds',
            'legalAddress',
            'actualAddress',
            'taxpayerIdentificationNumber',
            'taxRegistrationReasonCode',
            'primaryStateRegistrationNumber',
            'createdAt',
            'updatedAt',
            'legacyEditUrl',
            'legacyDeleteUrl',
        )

    def get_legacy_edit_url(self, developer):
        """Return the preserved Django developer edit form URL."""
        return reverse(
            'property:developer_update',
            kwargs={'pk': developer.pk},
        )

    def get_legacy_delete_url(self, developer):
        """Return the preserved Django developer delete form URL."""
        return reverse(
            'property:developer_delete',
            kwargs={'pk': developer.pk},
        )


class CustomerCalculationListQuerySerializer(serializers.Serializer):
    """Validate filters and pagination for a customer's calculations."""

    ORDERING_CHOICES = (
        'createdAt',
        '-createdAt',
        'city',
        '-city',
        'realEstateComplex',
        '-realEstateComplex',
        'finalPropertyCost',
        '-finalPropertyCost',
        'monthlyPayment',
        '-monthlyPayment',
        'annualRate',
        '-annualRate',
    )

    q = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    programType = serializers.ChoiceField(
        required=False,
        choices=('all', 'market', 'trench'),
        default='all',
    )
    ordering = serializers.ChoiceField(
        required=False,
        choices=ORDERING_CHOICES,
        default='-createdAt',
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )


class CustomerCalculationLinkCreateSerializer(serializers.Serializer):
    """Validate saved calculations selected for a customer."""

    programType = serializers.ChoiceField(choices=('market', 'trench'))
    calculationIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        allow_empty=False,
        max_length=100,
    )

    def validate_calculationIds(self, calculation_identifiers):
        """Remove duplicate identifiers while preserving request order."""
        return list(dict.fromkeys(calculation_identifiers))


class CustomerCalculationSelectionSerializer(serializers.Serializer):
    """Validate one linked calculation selected for an export."""

    programType = serializers.ChoiceField(choices=('market', 'trench'))
    linkId = serializers.IntegerField(min_value=1)


class CustomerCalculationExportRequestSerializer(serializers.Serializer):
    """Validate a bounded set of calculation links for Word export."""

    selections = CustomerCalculationSelectionSerializer(
        many=True,
        allow_empty=False,
    )

    def validate_selections(self, selections):
        """Reject oversized or duplicate synchronous export requests."""
        if len(selections) > 100:
            raise serializers.ValidationError(
                'За один раз можно выгрузить не более 100 расчётов.'
            )
        selection_keys = {
            (selection['programType'], selection['linkId'])
            for selection in selections
        }
        if len(selection_keys) != len(selections):
            raise serializers.ValidationError(
                'Один расчёт выбран несколько раз.'
            )
        return selections


class CustomerFormOptionsQuerySerializer(serializers.Serializer):
    """Validate the city used to load a bounded district list."""

    desiredCity = serializers.IntegerField(required=False, min_value=1)


class CustomerWriteSerializer(serializers.ModelSerializer):
    """Validate and atomically persist a customer form payload."""

    MODEL_TO_API_FIELD_NAMES = {
        'first_name': 'firstName',
        'last_name': 'lastName',
        'birth_date': 'birthDate',
        'birth_year': 'birthYear',
        'residence_city': 'residenceCityId',
        'initial_payment_amount': 'initialPaymentAmount',
        'max_monthly_payment': 'maximumMonthlyPayment',
        'has_owned_property': 'hasOwnedProperty',
        'purchase_goal': 'purchaseGoal',
        'desired_city': 'desiredCityId',
        'desired_district': 'desiredDistrictId',
        'area_min': 'areaMinimum',
        'area_max': 'areaMaximum',
        'desired_floor': 'desiredFloor',
        'cardinal_directions': 'cardinalDirections',
    }
    NORMALIZED_FIELD_NAMES = (
        'first_name',
        'last_name',
        'phone',
        'email',
        'age',
        'birth_date',
        'birth_year',
        'residence_city',
        'initial_payment_amount',
        'max_monthly_payment',
        'has_owned_property',
        'purchase_goal',
        'desired_city',
        'desired_district',
        'area_min',
        'area_max',
        'desired_floor',
        'cardinal_directions',
        'comment',
    )

    firstName = serializers.CharField(
        source='first_name',
        max_length=150,
        trim_whitespace=True,
        write_only=True,
        error_messages={'blank': 'Поле "Имя" обязательно для заполнения.'},
    )
    lastName = serializers.CharField(
        source='last_name',
        max_length=150,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        write_only=True,
    )
    phone = serializers.CharField(
        max_length=30,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        write_only=True,
    )
    email = serializers.EmailField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        write_only=True,
    )
    age = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        max_value=32767,
        write_only=True,
    )
    birthDate = serializers.DateField(
        source='birth_date',
        required=False,
        allow_null=True,
        write_only=True,
    )
    birthYear = serializers.IntegerField(
        source='birth_year',
        required=False,
        allow_null=True,
        min_value=0,
        max_value=32767,
        write_only=True,
    )
    residenceCityId = serializers.PrimaryKeyRelatedField(
        source='residence_city',
        queryset=City.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    initialPaymentAmount = serializers.DecimalField(
        source='initial_payment_amount',
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        allow_null=True,
        write_only=True,
    )
    maximumMonthlyPayment = serializers.DecimalField(
        source='max_monthly_payment',
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        allow_null=True,
        write_only=True,
    )
    preferentialProgramIds = serializers.PrimaryKeyRelatedField(
        source='preferential_programs',
        queryset=MortgageProgram.objects.filter(is_preferential=True),
        many=True,
        required=False,
        write_only=True,
    )
    hasOwnedProperty = serializers.BooleanField(
        source='has_owned_property',
        required=False,
        allow_null=True,
        write_only=True,
    )
    purchaseGoal = serializers.ChoiceField(
        source='purchase_goal',
        choices=Customer.PURCHASE_GOAL_CHOICES,
        required=False,
        allow_blank=True,
        write_only=True,
    )
    desiredCityId = serializers.PrimaryKeyRelatedField(
        source='desired_city',
        queryset=City.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    desiredDistrictId = serializers.PrimaryKeyRelatedField(
        source='desired_district',
        queryset=District.objects.all(),
        required=False,
        allow_null=True,
        write_only=True,
    )
    desiredLayoutIds = serializers.PrimaryKeyRelatedField(
        source='desired_layouts',
        queryset=ApartmentLayout.objects.all(),
        many=True,
        required=False,
        write_only=True,
    )
    areaMinimum = serializers.DecimalField(
        source='area_min',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        allow_null=True,
        write_only=True,
    )
    areaMaximum = serializers.DecimalField(
        source='area_max',
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0'),
        required=False,
        allow_null=True,
        write_only=True,
    )
    desiredFloor = serializers.CharField(
        source='desired_floor',
        max_length=100,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        write_only=True,
    )
    cardinalDirections = serializers.ListField(
        source='cardinal_directions',
        child=serializers.ChoiceField(
            choices=Customer.CARDINAL_DIRECTION_CHOICES
        ),
        required=False,
        allow_empty=True,
        write_only=True,
    )
    comment = serializers.CharField(
        required=False,
        allow_blank=True,
        trim_whitespace=True,
        write_only=True,
    )

    class Meta:
        """Define the explicit mutable customer fields."""

        model = Customer
        fields = (
            'id',
            'firstName',
            'lastName',
            'phone',
            'email',
            'age',
            'birthDate',
            'birthYear',
            'residenceCityId',
            'initialPaymentAmount',
            'maximumMonthlyPayment',
            'preferentialProgramIds',
            'hasOwnedProperty',
            'purchaseGoal',
            'desiredCityId',
            'desiredDistrictId',
            'desiredLayoutIds',
            'areaMinimum',
            'areaMaximum',
            'desiredFloor',
            'cardinalDirections',
            'comment',
        )
        read_only_fields = ('id',)

    def _raise_customer_validation_error(self, error):
        """Translate model validation field names to the API contract."""
        if hasattr(error, 'message_dict'):
            details = {
                self.MODEL_TO_API_FIELD_NAMES.get(field_name, field_name): (
                    messages
                )
                for field_name, messages in error.message_dict.items()
            }
        else:
            details = {'nonFieldErrors': error.messages}
        raise serializers.ValidationError(details) from error

    def validate(self, attributes):
        """Apply the established Customer model validation and normalization."""
        if 'cardinal_directions' in attributes:
            attributes['cardinal_directions'] = ', '.join(
                attributes['cardinal_directions']
            )

        customer = (
            copy(self.instance)
            if self.instance is not None
            else Customer(user=self.context['request'].user)
        )
        many_to_many_field_names = {
            'preferential_programs',
            'desired_layouts',
        }
        for field_name, value in attributes.items():
            if field_name not in many_to_many_field_names:
                setattr(customer, field_name, value)

        try:
            customer.clean()
        except DjangoValidationError as error:
            self._raise_customer_validation_error(error)

        for field_name in self.NORMALIZED_FIELD_NAMES:
            attributes[field_name] = getattr(customer, field_name)
        return attributes

    @transaction.atomic
    def create(self, validated_data):
        """Create the owner-scoped customer and its many-to-many links."""
        preferential_programs = validated_data.pop(
            'preferential_programs',
            [],
        )
        desired_layouts = validated_data.pop('desired_layouts', [])
        customer = Customer.objects.create(
            user=self.context['request'].user,
            **validated_data,
        )
        customer.preferential_programs.set(preferential_programs)
        customer.desired_layouts.set(desired_layouts)
        return customer

    @transaction.atomic
    def update(self, customer, validated_data):
        """Update an allowed customer and replace supplied relation choices."""
        preferential_programs = validated_data.pop(
            'preferential_programs',
            None,
        )
        desired_layouts = validated_data.pop('desired_layouts', None)
        for field_name, value in validated_data.items():
            setattr(customer, field_name, value)
        customer.save()
        if preferential_programs is not None:
            customer.preferential_programs.set(preferential_programs)
        if desired_layouts is not None:
            customer.desired_layouts.set(desired_layouts)
        return customer


class CustomerListItemSerializer(serializers.ModelSerializer):
    """Serialize one private customer list row without additional queries."""

    fullName = serializers.CharField(source='full_name', read_only=True)
    residenceCity = serializers.CharField(
        source='residence_city.name',
        allow_null=True,
        read_only=True,
    )
    createdAt = serializers.DateTimeField(
        source='created_at',
        read_only=True,
    )
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    legacyDetailUrl = serializers.SerializerMethodField(
        method_name='get_legacy_detail_url'
    )

    class Meta:
        """Define the bounded fields used by the customer list."""

        model = Customer
        fields = (
            'id',
            'fullName',
            'phone',
            'email',
            'residenceCity',
            'createdAt',
            'isActive',
            'legacyDetailUrl',
        )

    def get_legacy_detail_url(self, customer):
        """Return the preserved Django customer detail URL."""
        return reverse('customer:detail', kwargs={'pk': customer.pk})


class CustomerDetailSerializer(serializers.ModelSerializer):
    """Serialize an owner-scoped customer profile and financial capacity."""

    firstName = serializers.CharField(source='first_name', read_only=True)
    lastName = serializers.CharField(source='last_name', read_only=True)
    fullName = serializers.CharField(source='full_name', read_only=True)
    birthDate = serializers.DateField(
        source='birth_date',
        allow_null=True,
        read_only=True,
    )
    birthYear = serializers.IntegerField(
        source='birth_year',
        allow_null=True,
        read_only=True,
    )
    residenceCity = serializers.CharField(
        source='residence_city.name',
        allow_null=True,
        read_only=True,
    )
    residenceCityId = serializers.IntegerField(
        source='residence_city_id',
        allow_null=True,
        read_only=True,
    )
    initialPaymentAmount = serializers.DecimalField(
        source='initial_payment_amount',
        max_digits=15,
        decimal_places=2,
        allow_null=True,
        read_only=True,
    )
    maximumMonthlyPayment = serializers.DecimalField(
        source='max_monthly_payment',
        max_digits=15,
        decimal_places=2,
        allow_null=True,
        read_only=True,
    )
    preferentialPrograms = serializers.SerializerMethodField(
        method_name='get_preferential_programs'
    )
    hasOwnedProperty = serializers.BooleanField(
        source='has_owned_property',
        allow_null=True,
        read_only=True,
    )
    purchaseGoal = serializers.CharField(
        source='purchase_goal',
        read_only=True,
    )
    purchaseGoalLabel = serializers.SerializerMethodField(
        method_name='get_purchase_goal_label'
    )
    desiredCity = serializers.CharField(
        source='desired_city.name',
        allow_null=True,
        read_only=True,
    )
    desiredCityId = serializers.IntegerField(
        source='desired_city_id',
        allow_null=True,
        read_only=True,
    )
    desiredDistrict = serializers.CharField(
        source='desired_district.name',
        allow_null=True,
        read_only=True,
    )
    desiredDistrictId = serializers.IntegerField(
        source='desired_district_id',
        allow_null=True,
        read_only=True,
    )
    desiredLayouts = serializers.SerializerMethodField(
        method_name='get_desired_layouts'
    )
    areaMinimum = serializers.DecimalField(
        source='area_min',
        max_digits=10,
        decimal_places=2,
        allow_null=True,
        read_only=True,
    )
    areaMaximum = serializers.DecimalField(
        source='area_max',
        max_digits=10,
        decimal_places=2,
        allow_null=True,
        read_only=True,
    )
    desiredFloor = serializers.CharField(
        source='desired_floor',
        read_only=True,
    )
    cardinalDirections = serializers.CharField(
        source='cardinal_directions',
        read_only=True,
    )
    calculated = serializers.SerializerMethodField()
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    createdAt = serializers.DateTimeField(
        source='created_at',
        read_only=True,
    )
    updatedAt = serializers.DateTimeField(
        source='updated_at',
        read_only=True,
    )
    legacyDetailUrl = serializers.SerializerMethodField(
        method_name='get_legacy_detail_url'
    )
    legacyEditUrl = serializers.SerializerMethodField(
        method_name='get_legacy_edit_url'
    )
    legacyDeleteUrl = serializers.SerializerMethodField(
        method_name='get_legacy_delete_url'
    )
    legacyMortgageUrl = serializers.SerializerMethodField(
        method_name='get_legacy_mortgage_url'
    )

    class Meta:
        """Define private fields used by the React customer profile."""

        model = Customer
        fields = (
            'id',
            'firstName',
            'lastName',
            'fullName',
            'phone',
            'email',
            'age',
            'birthDate',
            'birthYear',
            'residenceCity',
            'residenceCityId',
            'initialPaymentAmount',
            'maximumMonthlyPayment',
            'preferentialPrograms',
            'hasOwnedProperty',
            'purchaseGoal',
            'purchaseGoalLabel',
            'desiredCity',
            'desiredCityId',
            'desiredDistrict',
            'desiredDistrictId',
            'desiredLayouts',
            'areaMinimum',
            'areaMaximum',
            'desiredFloor',
            'cardinalDirections',
            'comment',
            'calculated',
            'isActive',
            'createdAt',
            'updatedAt',
            'legacyDetailUrl',
            'legacyEditUrl',
            'legacyDeleteUrl',
            'legacyMortgageUrl',
        )

    def get_preferential_programs(self, customer):
        """Return prefetched preferential program names."""
        return [
            {'id': program.pk, 'name': program.name}
            for program in customer.preferential_programs.all()
        ]

    def get_purchase_goal_label(self, customer):
        """Return the translated purchase-goal label or an empty string."""
        if not customer.purchase_goal:
            return ''
        return customer.get_purchase_goal_display()

    def get_desired_layouts(self, customer):
        """Return prefetched desired layout labels."""
        return [
            {'id': layout.pk, 'name': layout.name}
            for layout in customer.desired_layouts.all()
        ]

    def get_calculated(self, customer):
        """Return financial capacity using the view's single key-rate lookup."""
        return build_customer_financial_capacity(
            customer,
            self.context['key_rate'],
        )

    def get_legacy_detail_url(self, customer):
        """Return the preserved Django customer profile URL."""
        return reverse('customer:detail', kwargs={'pk': customer.pk})

    def get_legacy_edit_url(self, customer):
        """Return the preserved Django customer edit URL."""
        return reverse('customer:update', kwargs={'pk': customer.pk})

    def get_legacy_delete_url(self, customer):
        """Return the preserved Django customer delete URL."""
        return reverse('customer:delete', kwargs={'pk': customer.pk})

    def get_legacy_mortgage_url(self, customer):
        """Return the preserved customer-aware mortgage calculator URL."""
        return (
            f"{reverse('mortgage:mortgage_calculator')}"
            f'?customer={customer.pk}'
        )


class RealEstateComplexListQuerySerializer(serializers.Serializer):
    """Validate filters, sorting, and pagination for residential complexes."""

    search = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    developerId = serializers.IntegerField(required=False, min_value=1)
    cityId = serializers.IntegerField(required=False, min_value=1)
    realEstateClassId = serializers.IntegerField(required=False, min_value=1)
    realEstateTypeId = serializers.IntegerField(required=False, min_value=1)
    buildingCount = serializers.IntegerField(required=False, min_value=0)
    status = serializers.ChoiceField(
        required=False,
        choices=('all', 'active', 'inactive'),
        default='all',
    )
    ordering = serializers.ChoiceField(
        required=False,
        choices=(
            'name',
            '-name',
            'developer',
            '-developer',
            'city',
            '-city',
            'realEstateClass',
            '-realEstateClass',
            'realEstateType',
            '-realEstateType',
            'buildingCount',
            '-buildingCount',
        ),
        default='developer',
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )


class RealEstateComplexOptionsQuerySerializer(serializers.Serializer):
    """Validate the selected location hierarchy for complex form choices."""

    regionId = serializers.IntegerField(required=False, min_value=1)
    cityId = serializers.IntegerField(required=False, min_value=1)


class RealEstateComplexListItemSerializer(serializers.ModelSerializer):
    """Serialize one residential-complex directory row."""

    developer = serializers.SerializerMethodField()
    city = serializers.CharField(source='district.city.name', read_only=True)
    realEstateClass = serializers.CharField(
        source='real_estate_class.name',
        read_only=True,
    )
    realEstateType = serializers.CharField(
        source='real_estate_type.name',
        read_only=True,
    )
    buildingCount = serializers.IntegerField(
        source='building_count',
        read_only=True,
    )
    isActive = serializers.BooleanField(source='is_active', read_only=True)

    class Meta:
        """Define the public residential-complex list contract."""

        model = RealEstateComplex
        fields = (
            'id',
            'name',
            'developer',
            'city',
            'realEstateClass',
            'realEstateType',
            'buildingCount',
            'isActive',
        )

    def get_developer(self, real_estate_complex):
        """Return the established developer label including company group."""
        developer = real_estate_complex.developer
        return {
            'id': developer.pk,
            'name': developer.name,
            'label': developer.get_display_name_with_company_group(),
        }


class RealEstateComplexBuildingSerializer(serializers.ModelSerializer):
    """Serialize a building included in a residential-complex card."""

    commissioningDate = serializers.DateField(
        source='commissioning_date', allow_null=True, read_only=True
    )
    commissioningYear = serializers.IntegerField(
        source='commissioning_year', allow_null=True, read_only=True
    )
    commissioningQuarter = serializers.IntegerField(
        source='commissioning_quarter', allow_null=True, read_only=True
    )
    commissioning = serializers.SerializerMethodField()
    keyHandoverDate = serializers.DateField(
        source='key_handover_date', allow_null=True, read_only=True
    )
    keyHandoverYear = serializers.IntegerField(
        source='key_handover_year', allow_null=True, read_only=True
    )
    keyHandoverQuarter = serializers.IntegerField(
        source='key_handover_quarter', allow_null=True, read_only=True
    )
    keyHandover = serializers.SerializerMethodField(
        method_name='get_key_handover'
    )
    propertyCount = serializers.IntegerField(
        source='property_count', read_only=True, default=0
    )
    isActive = serializers.BooleanField(source='is_active', read_only=True)

    class Meta:
        """Define fields returned for a residential-complex building."""

        model = RealEstateComplexBuilding
        fields = (
            'id', 'number', 'address', 'commissioningDate',
            'commissioningYear', 'commissioningQuarter', 'commissioning',
            'keyHandoverDate', 'keyHandoverYear', 'keyHandoverQuarter',
            'keyHandover', 'propertyCount', 'isActive',
        )

    def get_commissioning(self, building):
        """Return a stable date or quarter label for commissioning."""
        return _serialize_building_period(building.get_commissioning_display())

    def get_key_handover(self, building):
        """Return a stable date or quarter label for key handover."""
        return _serialize_building_period(building.get_key_handover_display())


class RealEstateComplexMetroAvailabilitySerializer(serializers.ModelSerializer):
    """Serialize one metro-access row for a residential complex."""

    metroId = serializers.IntegerField(source='metro_id', read_only=True)
    station = serializers.CharField(source='metro.station', read_only=True)
    line = serializers.CharField(
        source='metro.metro_line.line', read_only=True
    )
    lineColor = serializers.CharField(
        source='metro.metro_line.line_color', read_only=True
    )
    transportAccessibilityTypeId = serializers.IntegerField(
        source='transport_accessibility_type_id', read_only=True
    )
    transportAccessibilityType = serializers.CharField(
        source='transport_accessibility_type.name', read_only=True
    )
    walkingTimeMinutes = serializers.IntegerField(
        source='walking_time_minutes', read_only=True
    )
    isActive = serializers.BooleanField(source='is_active', read_only=True)

    class Meta:
        """Define fields returned for one metro-access row."""

        model = RealEstateComplexMetroAvailability
        fields = (
            'id', 'metroId', 'station', 'line', 'lineColor',
            'transportAccessibilityTypeId',
            'transportAccessibilityType', 'walkingTimeMinutes', 'isActive',
        )


class RealEstateComplexDetailSerializer(serializers.ModelSerializer):
    """Serialize the complete public residential-complex card."""

    developerId = serializers.IntegerField(source='developer_id', read_only=True)
    developer = serializers.SerializerMethodField()
    regionId = serializers.IntegerField(
        source='district.city.region_id', read_only=True
    )
    region = serializers.CharField(
        source='district.city.region.name', read_only=True
    )
    cityId = serializers.IntegerField(source='district.city_id', read_only=True)
    city = serializers.CharField(source='district.city.name', read_only=True)
    districtId = serializers.IntegerField(source='district_id', read_only=True)
    district = serializers.CharField(source='district.name', read_only=True)
    realEstateClassId = serializers.IntegerField(
        source='real_estate_class_id', read_only=True
    )
    realEstateClass = serializers.CharField(
        source='real_estate_class.name', read_only=True
    )
    realEstateTypeId = serializers.IntegerField(
        source='real_estate_type_id', read_only=True
    )
    realEstateType = serializers.CharField(
        source='real_estate_type.name', read_only=True
    )
    mapUrl = serializers.SerializerMethodField(method_name='get_map_url')
    presentationUrl = serializers.SerializerMethodField(
        method_name='get_presentation_url'
    )
    investmentPotential = serializers.CharField(
        source='investment_potential', allow_null=True, read_only=True
    )
    photoUrl = serializers.SerializerMethodField(method_name='get_photo_url')
    buildings = serializers.SerializerMethodField()
    metroAvailability = serializers.SerializerMethodField(
        method_name='get_metro_availability'
    )
    isActive = serializers.BooleanField(source='is_active', read_only=True)
    createdAt = serializers.DateTimeField(source='created_at', read_only=True)
    updatedAt = serializers.DateTimeField(source='updated_at', read_only=True)
    legacyDetailUrl = serializers.SerializerMethodField(
        method_name='get_legacy_detail_url'
    )
    legacyEditUrl = serializers.SerializerMethodField(
        method_name='get_legacy_edit_url'
    )
    legacyDeleteUrl = serializers.SerializerMethodField(
        method_name='get_legacy_delete_url'
    )

    class Meta:
        """Define fields used by the React residential-complex screens."""

        model = RealEstateComplex
        fields = (
            'id', 'name', 'description', 'developerId', 'developer',
            'regionId', 'region', 'cityId', 'city', 'districtId', 'district',
            'realEstateClassId', 'realEstateClass', 'realEstateTypeId',
            'realEstateType', 'mapUrl', 'presentationUrl',
            'investmentPotential', 'photoUrl', 'buildings',
            'metroAvailability', 'isActive', 'createdAt', 'updatedAt',
            'legacyDetailUrl', 'legacyEditUrl', 'legacyDeleteUrl',
        )

    def get_developer(self, real_estate_complex):
        """Return the developer identity and its established display label."""
        developer = real_estate_complex.developer
        return {
            'id': developer.pk,
            'name': developer.name,
            'label': developer.get_display_name_with_company_group(),
        }

    def get_map_url(self, real_estate_complex):
        """Return a validated external map URL or omit an unsafe value."""
        return _validate_external_url(real_estate_complex.map_link)

    def get_presentation_url(self, real_estate_complex):
        """Return a validated external presentation URL when safe."""
        return _validate_external_url(real_estate_complex.presentation_link)

    def get_photo_url(self, real_estate_complex):
        """Return the optional complex photo URL."""
        return real_estate_complex.photo.url if real_estate_complex.photo else None

    def get_buildings(self, real_estate_complex):
        """Serialize prefetched buildings without per-row database access."""
        return RealEstateComplexBuildingSerializer(
            real_estate_complex.api_buildings, many=True
        ).data

    def get_metro_availability(self, real_estate_complex):
        """Serialize prefetched metro-access rows without extra queries."""
        return RealEstateComplexMetroAvailabilitySerializer(
            real_estate_complex.api_metro_availability, many=True
        ).data

    def get_legacy_detail_url(self, real_estate_complex):
        """Return the preserved Django residential-complex card URL."""
        return reverse(
            'property:complex_detail', kwargs={'pk': real_estate_complex.pk}
        )

    def get_legacy_edit_url(self, real_estate_complex):
        """Return the preserved Django residential-complex form URL."""
        return reverse(
            'property:complex_update', kwargs={'pk': real_estate_complex.pk}
        )

    def get_legacy_delete_url(self, real_estate_complex):
        """Return the preserved Django residential-complex delete URL."""
        return reverse(
            'property:complex_delete', kwargs={'pk': real_estate_complex.pk}
        )


class RealEstateComplexBuildingWriteSerializer(serializers.Serializer):
    """Validate one building submitted with a residential complex."""

    id = serializers.IntegerField(required=False, min_value=1)
    number = serializers.CharField(max_length=100, trim_whitespace=True)
    address = serializers.CharField(
        required=False, allow_blank=True, allow_null=True,
        max_length=255, default=None,
    )
    commissioningDate = serializers.DateField(
        source='commissioning_date', required=False,
        allow_null=True, default=None,
    )
    commissioningYear = serializers.IntegerField(
        source='commissioning_year', required=False, allow_null=True,
        min_value=2000, max_value=2100, default=None,
    )
    commissioningQuarter = serializers.ChoiceField(
        source='commissioning_quarter', required=False, allow_null=True,
        choices=RealEstateComplexBuilding.Quarter.choices, default=None,
    )
    keyHandoverDate = serializers.DateField(
        source='key_handover_date', required=False,
        allow_null=True, default=None,
    )
    keyHandoverYear = serializers.IntegerField(
        source='key_handover_year', required=False, allow_null=True,
        min_value=2000, max_value=2100, default=None,
    )
    keyHandoverQuarter = serializers.ChoiceField(
        source='key_handover_quarter', required=False, allow_null=True,
        choices=RealEstateComplexBuilding.Quarter.choices, default=None,
    )
    isActive = serializers.BooleanField(
        source='is_active', required=False, default=True
    )

    def validate(self, attributes):
        """Require either an exact date or a complete year-and-quarter pair."""
        self._validate_period(attributes, 'commissioning')
        self._validate_period(attributes, 'key_handover')
        return attributes

    def _validate_period(self, attributes, field_prefix):
        """Validate one building milestone represented in two possible ways."""
        exact_date = attributes.get(f'{field_prefix}_date')
        year = attributes.get(f'{field_prefix}_year')
        quarter = attributes.get(f'{field_prefix}_quarter')
        public_prefix = (
            'commissioning' if field_prefix == 'commissioning'
            else 'keyHandover'
        )
        if exact_date and (year or quarter):
            message = 'Укажите либо точную дату, либо год и квартал.'
            raise serializers.ValidationError(
                {
                    f'{public_prefix}Date': message,
                    f'{public_prefix}Year': message,
                    f'{public_prefix}Quarter': message,
                }
            )
        if bool(year) != bool(quarter):
            message = 'Для квартального срока укажите год и квартал.'
            raise serializers.ValidationError(
                {
                    f'{public_prefix}Year': message,
                    f'{public_prefix}Quarter': message,
                }
            )


class RealEstateComplexMetroAvailabilityWriteSerializer(
    serializers.Serializer
):
    """Validate one metro-access row submitted with a complex."""

    id = serializers.IntegerField(required=False, min_value=1)
    metroId = serializers.PrimaryKeyRelatedField(
        source='metro',
        queryset=Metro.objects.select_related('metro_line__city'),
    )
    transportAccessibilityTypeId = serializers.PrimaryKeyRelatedField(
        source='transport_accessibility_type',
        queryset=TransportAccessibilityType.objects.all(),
    )
    walkingTimeMinutes = serializers.IntegerField(
        source='walking_time_minutes', min_value=1, max_value=1440
    )
    isActive = serializers.BooleanField(
        source='is_active', required=False, default=True
    )


class RealEstateComplexWriteSerializer(serializers.ModelSerializer):
    """Validate and atomically persist a residential complex and its rows."""

    developerId = serializers.PrimaryKeyRelatedField(
        source='developer', queryset=Developer.objects.all()
    )
    districtId = serializers.PrimaryKeyRelatedField(
        source='district',
        queryset=District.objects.select_related('city__region'),
    )
    realEstateClassId = serializers.PrimaryKeyRelatedField(
        source='real_estate_class', queryset=RealEstateClass.objects.all()
    )
    realEstateTypeId = serializers.PrimaryKeyRelatedField(
        source='real_estate_type', queryset=RealEstateType.objects.all()
    )
    mapLink = serializers.CharField(
        source='map_link', required=False, allow_blank=True, allow_null=True
    )
    presentationLink = serializers.CharField(
        source='presentation_link', required=False,
        allow_blank=True, allow_null=True,
    )
    investmentPotential = serializers.CharField(
        source='investment_potential', required=False,
        allow_blank=True, allow_null=True,
    )
    photo = serializers.ImageField(
        required=False, allow_null=True,
        validators=(validate_property_image_upload,),
    )
    clearPhoto = serializers.BooleanField(
        write_only=True, required=False, default=False
    )
    buildings = serializers.JSONField(required=False, write_only=True)
    metroAvailability = serializers.JSONField(required=False, write_only=True)
    isActive = serializers.BooleanField(source='is_active', required=False)

    class Meta:
        """Define fields accepted by residential-complex mutations."""

        model = RealEstateComplex
        fields = (
            'name', 'description', 'developerId', 'districtId',
            'realEstateClassId', 'realEstateTypeId', 'mapLink',
            'presentationLink', 'investmentPotential', 'photo', 'clearPhoto',
            'buildings', 'metroAvailability', 'isActive',
        )
        extra_kwargs = {
            'description': {
                'required': False, 'allow_blank': True, 'allow_null': True,
            },
        }
        validators = ()

    def validate_name(self, value):
        """Normalize whitespace while keeping the user-provided spelling."""
        return ' '.join(value.split())

    def validate_mapLink(self, value):
        """Accept only optional HTTP(S) map links."""
        return self._validate_external_link(value)

    def validate_presentationLink(self, value):
        """Accept only optional HTTP(S) presentation links."""
        return self._validate_external_link(value)

    @staticmethod
    def _validate_external_link(value):
        """Normalize an optional link and reject unsafe URL schemes."""
        normalized_value = value.strip() if value else None
        if not normalized_value:
            return None
        if _validate_external_url(normalized_value) is None:
            raise serializers.ValidationError(
                'Укажите корректную ссылку с протоколом http или https.'
            )
        return normalized_value

    def validate_buildings(self, value):
        """Validate and normalize the bounded replacement building list."""
        if not isinstance(value, list):
            raise serializers.ValidationError('Ожидался список корпусов.')
        if len(value) > 100:
            raise serializers.ValidationError(
                'За один раз можно сохранить не более 100 корпусов.'
            )
        serializer = RealEstateComplexBuildingWriteSerializer(
            data=value, many=True
        )
        serializer.is_valid(raise_exception=True)
        normalized_buildings = serializer.validated_data
        normalized_numbers = [
            building['number'].casefold()
            for building in normalized_buildings
        ]
        if len(normalized_numbers) != len(set(normalized_numbers)):
            raise serializers.ValidationError(
                'Номера корпусов внутри одного ЖК не должны повторяться.'
            )
        return normalized_buildings

    def validate_metroAvailability(self, value):
        """Validate and normalize the bounded replacement metro-access list."""
        if not isinstance(value, list):
            raise serializers.ValidationError(
                'Ожидался список вариантов доступности метро.'
            )
        if len(value) > 100:
            raise serializers.ValidationError(
                'За один раз можно сохранить не более 100 станций метро.'
            )
        serializer = RealEstateComplexMetroAvailabilityWriteSerializer(
            data=value, many=True
        )
        serializer.is_valid(raise_exception=True)
        normalized_rows = serializer.validated_data
        metro_identifiers = [row['metro'].pk for row in normalized_rows]
        if len(metro_identifiers) != len(set(metro_identifiers)):
            raise serializers.ValidationError(
                'Одна станция метро не может быть добавлена дважды.'
            )
        return normalized_rows

    def validate(self, attributes):
        """Validate uniqueness, location consistency, and child ownership."""
        real_estate_complex = self.instance
        name = attributes.get(
            'name', real_estate_complex.name if real_estate_complex else ''
        )
        developer = attributes.get(
            'developer',
            real_estate_complex.developer if real_estate_complex else None,
        )
        duplicate_queryset = RealEstateComplex.objects.filter(
            name__iexact=name, developer=developer
        )
        if real_estate_complex:
            duplicate_queryset = duplicate_queryset.exclude(
                pk=real_estate_complex.pk
            )
        if duplicate_queryset.exists():
            raise serializers.ValidationError(
                {'name': 'ЖК с таким названием у застройщика уже существует.'}
            )

        district = attributes.get(
            'district',
            real_estate_complex.district if real_estate_complex else None,
        )
        if 'metroAvailability' in attributes and district:
            for row in attributes['metroAvailability']:
                if row['metro'].metro_line.city_id != district.city_id:
                    raise serializers.ValidationError(
                        {
                            'metroAvailability': (
                                'Все станции метро должны относиться к '
                                'выбранному городу.'
                            )
                        }
                    )
        self._validate_related_identifiers(attributes)
        return attributes

    def _validate_related_identifiers(self, attributes):
        """Reject child identifiers outside the edited complex."""
        real_estate_complex = self.instance
        relation_configuration = (
            (
                'buildings', RealEstateComplexBuilding,
                'Корпус не относится к редактируемому ЖК.',
            ),
            (
                'metroAvailability', RealEstateComplexMetroAvailability,
                'Станция не относится к редактируемому ЖК.',
            ),
        )
        for field_name, model, ownership_message in relation_configuration:
            if field_name not in attributes:
                continue
            submitted_identifiers = {
                row['id'] for row in attributes[field_name] if row.get('id')
            }
            if not real_estate_complex:
                if submitted_identifiers:
                    raise serializers.ValidationError(
                        {field_name: ownership_message}
                    )
                continue
            existing_identifiers = set(
                model.objects.filter(
                    real_estate_complex=real_estate_complex
                ).values_list('pk', flat=True)
            )
            if not submitted_identifiers.issubset(existing_identifiers):
                raise serializers.ValidationError(
                    {field_name: ownership_message}
                )
            if field_name == 'buildings':
                removed_identifiers = (
                    existing_identifiers - submitted_identifiers
                )
                if Property.objects.filter(
                    building_id__in=removed_identifiers
                ).exists():
                    raise serializers.ValidationError(
                        {
                            field_name: (
                                'Нельзя удалить корпус, к которому привязаны '
                                'объекты недвижимости.'
                            )
                        }
                    )

    def create(self, validated_data):
        """Create a complex and all submitted child rows atomically."""
        buildings = validated_data.pop('buildings', [])
        metro_availability = validated_data.pop('metroAvailability', [])
        validated_data.pop('clearPhoto', None)
        with transaction.atomic():
            real_estate_complex = super().create(validated_data)
            self._sync_buildings(real_estate_complex, buildings)
            self._sync_metro_availability(
                real_estate_complex, metro_availability
            )
        return real_estate_complex

    def update(self, instance, validated_data):
        """Update a complex and optional replacement child lists atomically."""
        missing_related_rows = object()
        buildings = validated_data.pop('buildings', missing_related_rows)
        metro_availability = validated_data.pop(
            'metroAvailability', missing_related_rows
        )
        clear_photo = validated_data.pop('clearPhoto', False)
        previous_photo = instance.photo if instance.photo else None
        if clear_photo and 'photo' not in validated_data:
            validated_data['photo'] = None

        with transaction.atomic():
            real_estate_complex = super().update(instance, validated_data)
            if buildings is not missing_related_rows:
                self._sync_buildings(real_estate_complex, buildings)
            if metro_availability is not missing_related_rows:
                self._sync_metro_availability(
                    real_estate_complex, metro_availability
                )
            if previous_photo and (
                not real_estate_complex.photo
                or real_estate_complex.photo.name != previous_photo.name
            ):
                transaction.on_commit(
                    lambda: self._delete_replaced_photo(
                        real_estate_complex,
                        previous_photo.name,
                        previous_photo.storage,
                    )
                )
        return real_estate_complex

    def _sync_buildings(self, real_estate_complex, submitted_buildings):
        """Replace building rows with bounded bulk database operations."""
        existing_buildings = {
            building.pk: building
            for building in RealEstateComplexBuilding.objects.filter(
                real_estate_complex=real_estate_complex
            )
        }
        submitted_identifiers = {
            building['id']
            for building in submitted_buildings
            if building.get('id')
        }
        RealEstateComplexBuilding.objects.filter(
            real_estate_complex=real_estate_complex
        ).exclude(pk__in=submitted_identifiers).delete()

        updated_buildings = []
        created_buildings = []
        timestamp = timezone.now()
        mutable_fields = (
            'number', 'address', 'commissioning_date',
            'commissioning_year', 'commissioning_quarter',
            'key_handover_date', 'key_handover_year',
            'key_handover_quarter', 'is_active',
        )
        for submitted_building in submitted_buildings:
            building_data = dict(submitted_building)
            building_identifier = building_data.pop('id', None)
            if building_identifier:
                building = existing_buildings[building_identifier]
                for field_name in mutable_fields:
                    setattr(building, field_name, building_data[field_name])
                building.updated_at = timestamp
                updated_buildings.append(building)
            else:
                created_buildings.append(
                    RealEstateComplexBuilding(
                        real_estate_complex=real_estate_complex,
                        **building_data,
                    )
                )
        if updated_buildings:
            RealEstateComplexBuilding.objects.bulk_update(
                updated_buildings, (*mutable_fields, 'updated_at')
            )
        if created_buildings:
            RealEstateComplexBuilding.objects.bulk_create(created_buildings)

    def _sync_metro_availability(
        self,
        real_estate_complex,
        submitted_metro_availability,
    ):
        """Replace metro-access rows with bounded bulk database operations."""
        existing_rows = {
            row.pk: row
            for row in RealEstateComplexMetroAvailability.objects.filter(
                real_estate_complex=real_estate_complex
            )
        }
        submitted_identifiers = {
            row['id']
            for row in submitted_metro_availability
            if row.get('id')
        }
        RealEstateComplexMetroAvailability.objects.filter(
            real_estate_complex=real_estate_complex
        ).exclude(pk__in=submitted_identifiers).delete()

        updated_rows = []
        created_rows = []
        timestamp = timezone.now()
        mutable_fields = (
            'metro', 'transport_accessibility_type',
            'walking_time_minutes', 'is_active',
        )
        for submitted_row in submitted_metro_availability:
            row_data = dict(submitted_row)
            row_identifier = row_data.pop('id', None)
            if row_identifier:
                availability = existing_rows[row_identifier]
                for field_name in mutable_fields:
                    setattr(availability, field_name, row_data[field_name])
                availability.updated_at = timestamp
                updated_rows.append(availability)
            else:
                created_rows.append(
                    RealEstateComplexMetroAvailability(
                        real_estate_complex=real_estate_complex,
                        **row_data,
                    )
                )
        if updated_rows:
            RealEstateComplexMetroAvailability.objects.bulk_update(
                updated_rows, (*mutable_fields, 'updated_at')
            )
        if created_rows:
            RealEstateComplexMetroAvailability.objects.bulk_create(
                created_rows
            )

    def _delete_replaced_photo(
        self,
        real_estate_complex,
        photo_name,
        storage,
    ):
        """Delete an old photo after the database transaction commits."""
        if (
            real_estate_complex.photo
            and real_estate_complex.photo.name == photo_name
        ):
            return
        if storage.exists(photo_name):
            storage.delete(photo_name)


class PropertyListQuerySerializer(serializers.Serializer):
    """Validate filters, sorting, and pagination for the property list."""

    ORDERING_CHOICES = (
        'city',
        '-city',
        'developer',
        '-developer',
        'realEstateComplex',
        '-realEstateComplex',
        'building',
        '-building',
        'apartmentNumber',
        '-apartmentNumber',
        'layout',
        '-layout',
        'area',
        '-area',
        'propertyCost',
        '-propertyCost',
    )

    search = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    city = serializers.IntegerField(required=False, min_value=1)
    developer = serializers.IntegerField(required=False, min_value=1)
    realEstateComplex = serializers.IntegerField(required=False, min_value=1)
    building = serializers.IntegerField(required=False, min_value=1)
    layout = serializers.IntegerField(required=False, min_value=1)
    ordering = serializers.ChoiceField(
        required=False,
        choices=ORDERING_CHOICES,
        default='city',
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )


class PropertyFormOptionsQuerySerializer(serializers.Serializer):
    """Validate the hierarchy selected in the React property form."""

    regionId = serializers.IntegerField(required=False, min_value=1)
    cityId = serializers.IntegerField(required=False, min_value=1)
    districtId = serializers.IntegerField(required=False, min_value=1)
    developerId = serializers.IntegerField(required=False, min_value=1)
    realEstateComplexId = serializers.IntegerField(
        required=False,
        min_value=1,
    )


class PropertyListItemSerializer(serializers.ModelSerializer):
    """Serialize one property row without triggering per-row queries."""

    city = serializers.CharField(
        source='building.real_estate_complex.district.city.name',
        read_only=True,
    )
    developer = serializers.SerializerMethodField()
    realEstateComplex = serializers.CharField(
        source='building.real_estate_complex.name',
        read_only=True,
    )
    building = serializers.CharField(source='building.number', read_only=True)
    apartmentNumber = serializers.CharField(
        source='apartment_number',
        read_only=True,
    )
    layout = serializers.CharField(source='layout.name', read_only=True)
    decoration = serializers.CharField(source='decoration.name', read_only=True)
    area = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    floor = serializers.IntegerField(read_only=True)
    propertyCost = serializers.DecimalField(
        source='property_cost',
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )
    detailUrl = serializers.SerializerMethodField(
        method_name='get_detail_url'
    )

    class Meta:
        """Define the public fields used by property list screens."""

        model = Property
        fields = (
            'id',
            'city',
            'developer',
            'realEstateComplex',
            'building',
            'apartmentNumber',
            'layout',
            'decoration',
            'area',
            'floor',
            'propertyCost',
            'detailUrl',
        )

    def get_developer(self, property_object):
        """Return the established developer label including company group."""
        developer = property_object.building.real_estate_complex.developer
        return developer.get_display_name_with_company_group()

    def get_detail_url(self, property_object):
        """Return the existing detail URL during incremental migration."""
        return property_object.get_absolute_url()


def _serialize_building_period(value):
    """Return a stable date or quarter label for a building milestone."""
    if not value:
        return None
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return str(value)


def _validate_external_url(value):
    """Return only external HTTP(S) URLs safe to place in a client link."""
    if not value:
        return None
    validator = URLValidator(schemes=('http', 'https'))
    try:
        validator(value)
    except DjangoValidationError:
        return None
    return value


class PropertyDetailSerializer(serializers.ModelSerializer):
    """Serialize the complete public property card without extra queries."""

    apartmentNumber = serializers.CharField(
        source='apartment_number',
        read_only=True,
    )
    regionId = serializers.IntegerField(
        source='building.real_estate_complex.district.city.region_id',
        read_only=True,
    )
    cityId = serializers.IntegerField(
        source='building.real_estate_complex.district.city_id',
        read_only=True,
    )
    districtId = serializers.IntegerField(
        source='building.real_estate_complex.district_id',
        read_only=True,
    )
    developerId = serializers.IntegerField(
        source='building.real_estate_complex.developer_id',
        read_only=True,
    )
    realEstateComplexId = serializers.IntegerField(
        source='building.real_estate_complex_id',
        read_only=True,
    )
    buildingId = serializers.IntegerField(source='building_id', read_only=True)
    layoutId = serializers.IntegerField(source='layout_id', read_only=True)
    decorationId = serializers.IntegerField(
        source='decoration_id',
        read_only=True,
    )
    windowViewIds = serializers.SerializerMethodField(
        method_name='get_window_view_ids'
    )
    developer = serializers.SerializerMethodField()
    realEstateComplex = serializers.CharField(
        source='building.real_estate_complex.name',
        read_only=True,
    )
    realEstateClass = serializers.CharField(
        source='building.real_estate_complex.real_estate_class.name',
        read_only=True,
    )
    realEstateType = serializers.CharField(
        source='building.real_estate_complex.real_estate_type.name',
        read_only=True,
    )
    district = serializers.CharField(
        source='building.real_estate_complex.district.name',
        read_only=True,
    )
    city = serializers.CharField(
        source='building.real_estate_complex.district.city.name',
        read_only=True,
    )
    region = serializers.CharField(
        source='building.real_estate_complex.district.city.region.name',
        read_only=True,
    )
    building = serializers.CharField(
        source='building.number',
        read_only=True,
    )
    buildingAddress = serializers.CharField(
        source='building.address',
        allow_null=True,
        read_only=True,
    )
    commissioning = serializers.SerializerMethodField()
    keyHandover = serializers.SerializerMethodField(
        method_name='get_key_handover'
    )
    layout = serializers.CharField(source='layout.name', read_only=True)
    layoutDescription = serializers.CharField(
        source='layout.description',
        allow_null=True,
        read_only=True,
    )
    decoration = serializers.CharField(
        source='decoration.name',
        read_only=True,
    )
    decorationDescription = serializers.CharField(
        source='decoration.description',
        allow_null=True,
        read_only=True,
    )
    windowViews = serializers.SerializerMethodField(
        method_name='get_window_views'
    )
    area = serializers.DecimalField(
        max_digits=10,
        decimal_places=2,
        read_only=True,
    )
    propertyCost = serializers.DecimalField(
        source='property_cost',
        max_digits=15,
        decimal_places=2,
        read_only=True,
    )
    mapUrl = serializers.SerializerMethodField(method_name='get_map_url')
    presentationUrl = serializers.SerializerMethodField(
        method_name='get_presentation_url'
    )
    images = serializers.SerializerMethodField()
    createdAt = serializers.DateTimeField(
        source='created_at',
        read_only=True,
    )
    updatedAt = serializers.DateTimeField(
        source='updated_at',
        read_only=True,
    )
    legacyDetailUrl = serializers.SerializerMethodField(
        method_name='get_legacy_detail_url'
    )
    legacyEditUrl = serializers.SerializerMethodField(
        method_name='get_legacy_edit_url'
    )
    legacyDeleteUrl = serializers.SerializerMethodField(
        method_name='get_legacy_delete_url'
    )

    class Meta:
        """Define fields used by the React property detail screen."""

        model = Property
        fields = (
            'id',
            'apartmentNumber',
            'regionId',
            'cityId',
            'districtId',
            'developerId',
            'realEstateComplexId',
            'buildingId',
            'layoutId',
            'decorationId',
            'windowViewIds',
            'developer',
            'realEstateComplex',
            'realEstateClass',
            'realEstateType',
            'district',
            'city',
            'region',
            'building',
            'buildingAddress',
            'commissioning',
            'keyHandover',
            'layout',
            'layoutDescription',
            'decoration',
            'decorationDescription',
            'windowViews',
            'area',
            'floor',
            'propertyCost',
            'mapUrl',
            'presentationUrl',
            'images',
            'createdAt',
            'updatedAt',
            'legacyDetailUrl',
            'legacyEditUrl',
            'legacyDeleteUrl',
        )

    def get_developer(self, property_object):
        """Return the established developer label including company group."""
        developer = property_object.building.real_estate_complex.developer
        return developer.get_display_name_with_company_group()

    def get_commissioning(self, property_object):
        """Return a date or quarter label for commissioning."""
        return _serialize_building_period(
            property_object.building.get_commissioning_display()
        )

    def get_key_handover(self, property_object):
        """Return a date or quarter label for key handover."""
        return _serialize_building_period(
            property_object.building.get_key_handover_display()
        )

    def get_window_views(self, property_object):
        """Return prefetched window-view labels in dictionary order."""
        return [
            window_view.name
            for window_view in property_object.window_views.all()
        ]

    def get_window_view_ids(self, property_object):
        """Return prefetched identifiers used to initialize the edit form."""
        return [
            window_view.pk
            for window_view in property_object.window_views.all()
        ]

    def get_map_url(self, property_object):
        """Return a validated map URL or omit an unsafe stored value."""
        real_estate_complex = (
            property_object.building.real_estate_complex
        )
        return _validate_external_url(real_estate_complex.map_link)

    def get_presentation_url(self, property_object):
        """Return a validated presentation URL or omit an unsafe value."""
        real_estate_complex = (
            property_object.building.real_estate_complex
        )
        return _validate_external_url(
            real_estate_complex.presentation_link
        )

    def get_images(self, property_object):
        """Return all supported image slots with nullable media URLs."""
        image_fields = (
            ('layout', 'Планировка', property_object.layout_image),
            ('floorPlan', 'План этажа', property_object.floor_plan_image),
            ('windowView', 'Вид из окна', property_object.window_view_image),
        )
        return [
            {
                'kind': kind,
                'label': label,
                'url': image_field.url if image_field else None,
            }
            for kind, label, image_field in image_fields
        ]

    def get_legacy_detail_url(self, property_object):
        """Return the preserved Django property detail URL."""
        return property_object.get_absolute_url()

    def get_legacy_edit_url(self, property_object):
        """Return the preserved Django edit form URL."""
        return reverse('property:update', kwargs={'pk': property_object.pk})

    def get_legacy_delete_url(self, property_object):
        """Return the preserved Django delete confirmation URL."""
        return reverse('property:delete', kwargs={'pk': property_object.pk})


class PropertyWriteSerializer(serializers.ModelSerializer):
    """Validate and persist a property submitted by the React form."""

    IMAGE_CLEAR_FIELDS = (
        ('clearLayoutImage', 'layout_image'),
        ('clearFloorPlanImage', 'floor_plan_image'),
        ('clearWindowViewImage', 'window_view_image'),
    )

    apartmentNumber = serializers.CharField(
        source='apartment_number',
        max_length=50,
    )
    buildingId = serializers.PrimaryKeyRelatedField(
        source='building',
        queryset=RealEstateComplexBuilding.objects.all(),
    )
    decorationId = serializers.PrimaryKeyRelatedField(
        source='decoration',
        queryset=ApartmentDecoration.objects.all(),
    )
    layoutId = serializers.PrimaryKeyRelatedField(
        source='layout',
        queryset=ApartmentLayout.objects.all(),
    )
    propertyCost = serializers.DecimalField(
        source='property_cost',
        max_digits=15,
        decimal_places=2,
    )
    windowViewIds = serializers.PrimaryKeyRelatedField(
        source='window_views',
        queryset=WindowView.objects.all(),
        many=True,
        required=False,
    )
    replaceWindowViews = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )
    layoutImage = serializers.ImageField(
        source='layout_image',
        required=False,
        allow_null=True,
        validators=(validate_property_image_upload,),
    )
    floorPlanImage = serializers.ImageField(
        source='floor_plan_image',
        required=False,
        allow_null=True,
        validators=(validate_property_image_upload,),
    )
    windowViewImage = serializers.ImageField(
        source='window_view_image',
        required=False,
        allow_null=True,
        validators=(validate_property_image_upload,),
    )
    clearLayoutImage = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )
    clearFloorPlanImage = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )
    clearWindowViewImage = serializers.BooleanField(
        write_only=True,
        required=False,
        default=False,
    )

    class Meta:
        """Define fields accepted by property create and update endpoints."""

        model = Property
        fields = (
            'apartmentNumber',
            'buildingId',
            'decorationId',
            'layoutId',
            'area',
            'floor',
            'propertyCost',
            'windowViewIds',
            'replaceWindowViews',
            'layoutImage',
            'floorPlanImage',
            'windowViewImage',
            'clearLayoutImage',
            'clearFloorPlanImage',
            'clearWindowViewImage',
        )

    def create(self, validated_data):
        """Create a property and its optional window-view relations."""
        self._pop_clear_flags(validated_data)
        validated_data.pop('replaceWindowViews', None)
        return super().create(validated_data)

    def update(self, instance, validated_data):
        """Update fields and safely remove explicitly cleared image files."""
        clear_flags = self._pop_clear_flags(validated_data)
        replace_window_views = validated_data.pop(
            'replaceWindowViews',
            False,
        )
        window_views_were_submitted = 'window_views' in validated_data
        previous_images = []
        for clear_field, image_field in self.IMAGE_CLEAR_FIELDS:
            if not clear_flags[clear_field]:
                continue
            previous_image = getattr(instance, image_field)
            if previous_image:
                previous_images.append(
                    (image_field, previous_image.name, previous_image.storage)
                )
            if image_field not in validated_data:
                validated_data[image_field] = None

        with transaction.atomic():
            property_object = super().update(instance, validated_data)
            if replace_window_views and not window_views_were_submitted:
                property_object.window_views.clear()
            transaction.on_commit(
                lambda: self._delete_replaced_images(
                    property_object,
                    previous_images,
                )
            )
        return property_object

    def _pop_clear_flags(self, validated_data):
        """Remove transport-only image flags from validated model data."""
        return {
            clear_field: validated_data.pop(clear_field, False)
            for clear_field, _ in self.IMAGE_CLEAR_FIELDS
        }

    def _delete_replaced_images(self, property_object, previous_images):
        """Delete old storage objects after the database update commits."""
        for image_field, image_name, storage in previous_images:
            current_image = getattr(property_object, image_field)
            if current_image and current_image.name == image_name:
                continue
            if storage.exists(image_name):
                storage.delete(image_name)


class MortgageCalculationRequestSerializer(serializers.Serializer):
    """Validate a side-effect-free market mortgage calculation request."""

    propertyCost = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01'),
    )
    priceAdjustmentType = serializers.ChoiceField(
        choices=('discount', 'markup'),
        default='discount',
    )
    priceAdjustmentUnit = serializers.ChoiceField(
        choices=('percent', 'rubles'),
        default='percent',
    )
    priceAdjustmentValue = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0'),
        default=Decimal('0'),
    )
    initialPaymentUnit = serializers.ChoiceField(
        choices=('percent', 'rubles'),
        default='percent',
    )
    initialPaymentValue = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0'),
    )
    initialPaymentDate = serializers.DateField()
    mortgageTermMonths = serializers.IntegerField(
        min_value=1,
        max_value=600,
    )
    annualRate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0.01'),
        max_value=Decimal('100'),
    )
    hasGracePeriod = serializers.BooleanField(default=False)
    gracePeriodTermMonths = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=1,
        max_value=599,
    )
    gracePeriodRate = serializers.DecimalField(
        required=False,
        allow_null=True,
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0.01'),
        max_value=Decimal('100'),
    )

    def validate(self, attributes):
        """Validate cross-field monetary and grace-period constraints."""
        property_cost = attributes['propertyCost']
        adjustment_value = attributes['priceAdjustmentValue']
        adjustment_unit = attributes['priceAdjustmentUnit']

        if adjustment_unit == 'percent':
            adjustment_rubles = property_cost * adjustment_value / 100
        else:
            adjustment_rubles = adjustment_value

        if attributes['priceAdjustmentType'] == 'discount':
            final_property_cost = property_cost - adjustment_rubles
        else:
            final_property_cost = property_cost + adjustment_rubles

        errors = {}
        if final_property_cost <= 0:
            errors['priceAdjustmentValue'] = (
                'Скидка должна быть меньше стоимости объекта.'
            )

        initial_payment_value = attributes['initialPaymentValue']
        if attributes['initialPaymentUnit'] == 'percent':
            if initial_payment_value > 100:
                errors['initialPaymentValue'] = (
                    'Первоначальный взнос не может превышать 100%.'
                )
        elif initial_payment_value > final_property_cost:
            errors['initialPaymentValue'] = (
                'Первоначальный взнос не может превышать итоговую стоимость.'
            )

        if attributes['hasGracePeriod']:
            grace_period_term = attributes.get('gracePeriodTermMonths')
            grace_period_rate = attributes.get('gracePeriodRate')
            if grace_period_term is None:
                errors['gracePeriodTermMonths'] = (
                    'Укажите срок льготного периода.'
                )
            elif grace_period_term >= attributes['mortgageTermMonths']:
                errors['gracePeriodTermMonths'] = (
                    'Льготный период должен быть короче срока ипотеки.'
                )
            if grace_period_rate is None:
                errors['gracePeriodRate'] = (
                    'Укажите ставку льготного периода.'
                )
        else:
            attributes['gracePeriodTermMonths'] = 0
            attributes['gracePeriodRate'] = None

        if errors:
            raise serializers.ValidationError(errors)
        return attributes


class TrenchMortgageEntryRequestSerializer(serializers.Serializer):
    """Validate one dated tranche in the mortgage release schedule."""

    date = serializers.DateField()
    amountUnit = serializers.ChoiceField(
        choices=('percent', 'rubles'),
        default='percent',
    )
    amountValue = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01'),
        required=False,
        allow_null=True,
    )
    annualRate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0'),
        max_value=Decimal('100'),
    )

    def validate(self, attributes):
        """Reject percentage tranche values above the complete loan."""
        if (
            attributes['amountUnit'] == 'percent'
            and attributes.get('amountValue') is not None
            and attributes['amountValue'] > Decimal('100')
        ):
            raise serializers.ValidationError(
                {
                    'amountValue': (
                        'Размер одного транша не может превышать 100%.'
                    )
                }
            )
        return attributes


class TrenchMortgageCalculationRequestSerializer(serializers.Serializer):
    """Validate a side-effect-free trench mortgage calculation request."""

    propertyCost = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0.01'),
    )
    priceAdjustmentType = serializers.ChoiceField(
        choices=('discount', 'markup'),
        default='discount',
    )
    priceAdjustmentUnit = serializers.ChoiceField(
        choices=('percent', 'rubles'),
        default='percent',
    )
    priceAdjustmentValue = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0'),
        default=Decimal('0'),
    )
    initialPaymentUnit = serializers.ChoiceField(
        choices=('percent', 'rubles'),
        default='percent',
    )
    initialPaymentValue = serializers.DecimalField(
        max_digits=15,
        decimal_places=2,
        min_value=Decimal('0'),
    )
    initialPaymentDate = serializers.DateField()
    mortgageTermMonths = serializers.IntegerField(
        min_value=1,
        max_value=600,
    )
    annualRate = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal('0'),
        max_value=Decimal('100'),
    )
    trenches = serializers.ListField(
        child=TrenchMortgageEntryRequestSerializer(),
        min_length=1,
        max_length=5,
    )

    def validate(self, attributes):
        """Validate financial values, tranche amounts, and date ordering."""
        property_cost = attributes['propertyCost']
        adjustment_value = attributes['priceAdjustmentValue']
        if attributes['priceAdjustmentUnit'] == 'percent':
            adjustment_rubles = property_cost * adjustment_value / 100
        else:
            adjustment_rubles = adjustment_value

        if attributes['priceAdjustmentType'] == 'discount':
            final_property_cost = property_cost - adjustment_rubles
        else:
            final_property_cost = property_cost + adjustment_rubles

        errors = {}
        if final_property_cost <= 0:
            errors['priceAdjustmentValue'] = (
                'Скидка должна быть меньше стоимости объекта.'
            )

        initial_payment_value = attributes['initialPaymentValue']
        if attributes['initialPaymentUnit'] == 'percent':
            if initial_payment_value >= 100:
                errors['initialPaymentValue'] = (
                    'Для траншевой ипотеки взнос должен быть меньше 100%.'
                )
        elif initial_payment_value >= final_property_cost:
            errors['initialPaymentValue'] = (
                'Взнос должен быть меньше итоговой стоимости объекта.'
            )

        trenches = attributes['trenches']
        trench_errors = {}
        for trench_index, trench in enumerate(trenches[:-1]):
            if trench.get('amountValue') is None:
                trench_errors[trench_index] = {
                    'amountValue': (
                        'Укажите размер транша; последний будет рассчитан '
                        'автоматически.'
                    )
                }
        for trench_index, (previous, current) in enumerate(
            zip(trenches, trenches[1:]),
            start=1,
        ):
            if current['date'] < previous['date']:
                trench_errors.setdefault(trench_index, {})['date'] = (
                    'Даты траншей должны идти по возрастанию.'
                )
        if trench_errors:
            errors['trenches'] = trench_errors

        if errors:
            raise serializers.ValidationError(errors)

        trenches[-1]['amountValue'] = None
        return attributes


class SavedMortgageCalculationCreateSerializer(serializers.Serializer):
    """Validate a request to persist a property-backed calculation."""

    propertyId = serializers.PrimaryKeyRelatedField(
        source='property',
        queryset=Property.objects.all(),
    )
    customerId = serializers.IntegerField(required=False, min_value=1)
    parameters = MortgageCalculationRequestSerializer()


class SavedTrenchMortgageCalculationCreateSerializer(serializers.Serializer):
    """Validate a request to persist a property-backed trench scenario."""

    propertyId = serializers.PrimaryKeyRelatedField(
        source='property',
        queryset=Property.objects.all(),
    )
    customerId = serializers.IntegerField(required=False, min_value=1)
    parameters = TrenchMortgageCalculationRequestSerializer()


class SavedMortgageCalculationListQuerySerializer(serializers.Serializer):
    """Validate bounded filtering and ordering for saved calculations."""

    ORDERING_CHOICES = (
        'createdAt',
        '-createdAt',
        'finalPropertyCost',
        '-finalPropertyCost',
        'mainMonthlyPayment',
        '-mainMonthlyPayment',
        'mortgageTermMonths',
        '-mortgageTermMonths',
        'annualRate',
        '-annualRate',
    )

    q = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    customerId = serializers.IntegerField(required=False, min_value=1)
    ordering = serializers.ChoiceField(
        required=False,
        choices=ORDERING_CHOICES,
        default='-createdAt',
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )


class SavedTrenchMortgageCalculationListQuerySerializer(
    serializers.Serializer
):
    """Validate bounded filtering and ordering for tranche history."""

    ORDERING_CHOICES = (
        'createdAt',
        '-createdAt',
        'finalPropertyCost',
        '-finalPropertyCost',
        'mortgageTermMonths',
        '-mortgageTermMonths',
        'annualRate',
        '-annualRate',
        'trenchCount',
        '-trenchCount',
    )

    q = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    customerId = serializers.IntegerField(required=False, min_value=1)
    ordering = serializers.ChoiceField(
        required=False,
        choices=ORDERING_CHOICES,
        default='-createdAt',
    )
    page = serializers.IntegerField(required=False, min_value=1, default=1)
    pageSize = serializers.IntegerField(
        required=False,
        min_value=1,
        max_value=100,
        default=20,
    )
