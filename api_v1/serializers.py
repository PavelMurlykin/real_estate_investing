from decimal import Decimal

from rest_framework import serializers

from property.models import Property


class LoginRequestSerializer(serializers.Serializer):
    """Validate credentials submitted by the React frontend."""

    identifier = serializers.CharField(max_length=254, trim_whitespace=True)
    password = serializers.CharField(max_length=128, trim_whitespace=False)


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
