from django.db.models import Count, Q
from django.utils.text import Truncator
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from location.models import City
from property.models import RealEstateComplex
from property.location_filters import apply_location_scopes, selected_scopes
from .location_parameters import LocationScopeQuerySerializer

from .pagination import ApplicationPageNumberPagination
from .serializers import (
    RealEstateComplexListItemSerializer, _validate_external_url,
)


class HomepageQuerySerializer(LocationScopeQuerySerializer):
    """Validate bounded homepage requests while retaining legacy city fallback."""

    city = serializers.CharField(required=False, allow_blank=True, max_length=20)
    page = serializers.IntegerField(required=False, min_value=1)
    pageSize = serializers.IntegerField(required=False, min_value=1, max_value=100)
    allLocations = serializers.BooleanField(default=False)


class HomepageComplexSerializer(RealEstateComplexListItemSerializer):
    """Return the legacy homepage's photo, location and public complex links."""

    district = serializers.CharField(source='geography.district', read_only=True)
    description = serializers.SerializerMethodField()
    photoUrl = serializers.SerializerMethodField(method_name='get_photo_url')
    mapUrl = serializers.SerializerMethodField(method_name='get_map_url')
    presentationUrl = serializers.SerializerMethodField(
        method_name='get_presentation_url'
    )

    class Meta(RealEstateComplexListItemSerializer.Meta):
        """Extend the bounded public list without loading detail collections."""

        fields = RealEstateComplexListItemSerializer.Meta.fields + (
            'district', 'description', 'photoUrl', 'mapUrl', 'presentationUrl',
        )

    def get_description(self, complex_object):
        """Match the legacy homepage's 220-character text preview."""
        return Truncator(complex_object.description or '').chars(220)

    def get_photo_url(self, complex_object):
        """Return the stored photo without reading its contents."""
        return complex_object.photo.url if complex_object.photo else None

    def get_map_url(self, complex_object):
        """Use the same safe map URL policy as the complex detail endpoint."""
        return _validate_external_url(complex_object.map_link)

    def get_presentation_url(self, complex_object):
        """Return the validated optional presentation link."""
        return _validate_external_url(complex_object.presentation_link)


class HomepageComplexListAPIView(ListAPIView):
    """Restore active complexes in the selected city with bounded pagination."""

    permission_classes = (AllowAny,)
    serializer_class = HomepageComplexSerializer
    pagination_class = ApplicationPageNumberPagination

    def get_queryset(self):
        """Apply the legacy active-city and active-district rules before paging."""
        serializer = HomepageQuerySerializer(data=self.request.query_params)
        serializer.is_valid(raise_exception=True)
        self.location_scopes = serializer.validated_data
        if selected_scopes(self.location_scopes) or self.location_scopes['allLocations']:
            self.selected_city = None
            return apply_location_scopes(RealEstateComplex.objects.filter(is_active=True).select_related(
                'developer__company_group', 'district__city__region',
                'real_estate_class', 'real_estate_type',
            ).annotate(building_count=Count('realestatecomplexbuilding', distinct=True)), self.location_scopes).order_by('name', 'pk')
        identifier = serializer.validated_data.get('city', '')
        cities = City.objects.filter(is_active=True).order_by('name', 'pk')
        selected = None
        if identifier.isdecimal() and 0 < int(identifier) <= 9223372036854775807:
            selected = cities.filter(pk=int(identifier)).first()
        self.selected_city = selected or (
            cities.filter(name='Санкт-Петербург').first() or cities.first()
        )
        if self.selected_city is None:
            return RealEstateComplex.objects.none()
        return RealEstateComplex.objects.filter(
            Q(district__is_active=True, district__city=self.selected_city)
            | Q(district__isnull=True, location_links__is_primary=True,
                location_links__location__ancestor_links__ancestor__legacy_mappings__model_name='city',
                location_links__location__ancestor_links__ancestor__legacy_mappings__legacy_id=self.selected_city.pk),
            is_active=True,
        ).select_related(
            'developer__company_group', 'district__city__region',
            'real_estate_class', 'real_estate_type',
        ).annotate(
            building_count=Count('realestatecomplexbuilding', distinct=True)
        ).order_by('name', 'pk')

    def list(self, request, *args, **kwargs):
        """Include the resolved city so invalid and missing URLs stay coherent."""
        response = super().list(request, *args, **kwargs)
        response.data['selectedCity'] = (
            {'id': self.selected_city.pk, 'name': self.selected_city.name}
            if self.selected_city else None
        )
        return response
