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
