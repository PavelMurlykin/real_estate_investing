from decimal import Decimal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.core.validators import URLValidator
from django.urls import reverse
from rest_framework import serializers

from customer.models import Customer
from property.models import Property

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
    desiredDistrict = serializers.CharField(
        source='desired_district.name',
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
            'initialPaymentAmount',
            'maximumMonthlyPayment',
            'preferentialPrograms',
            'hasOwnedProperty',
            'purchaseGoal',
            'purchaseGoalLabel',
            'desiredCity',
            'desiredDistrict',
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


class SavedMortgageCalculationCreateSerializer(serializers.Serializer):
    """Validate a request to persist a property-backed calculation."""

    propertyId = serializers.PrimaryKeyRelatedField(
        source='property',
        queryset=Property.objects.all(),
    )
    parameters = MortgageCalculationRequestSerializer()


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
