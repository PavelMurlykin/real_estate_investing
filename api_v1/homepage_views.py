from django.db.models import Count, Q
from django.utils.text import Truncator
from rest_framework import serializers
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny

from location.legacy_catalog import legacy_choices
from location.models import Location
from property.location_context import geography_prefetch, locality_filter
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
    canonicalLocations = serializers.BooleanField(default=False)


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

    def to_representation(self, instance):
        """Include precise place names for geocoding in the canonical map."""
        payload = super().to_representation(instance)
        if self.context['view'].canonical_locations:
            geography = instance.geography
            components = (geography.city, geography.district, geography.region)
            payload['locationLabel'] = ', '.join(dict.fromkeys(filter(None, components)))
        return payload


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
        self.canonical_locations = self.location_scopes['canonicalLocations']
        self.selected_city = None
        self.territory_label = None
        identifier = serializer.validated_data.get('city', '')
        city_id = int(identifier) if identifier.isdecimal() else None
        if city_id and city_id > 9223372036854775807:
            city_id = None
        scopes = selected_scopes(self.location_scopes)
        if self.canonical_locations:
            if scopes:
                most_specific = next((self.location_scopes[field] for field in (
                    'localityId', 'districtLocationId', 'regionLocationId', 'locationId',
                ) if self.location_scopes.get(field)))
                self.territory_label = Location.objects.filter(pk=most_specific).values_list('name', flat=True).first()
            elif city_id or not self.location_scopes['allLocations']:
                localities = Location.objects.filter(locality_filter(), is_active=True).order_by('name', 'pk')
                mapped = localities.filter(
                    legacy_mappings__model_name='city', legacy_mappings__legacy_id=city_id,
                ).values_list('pk', 'name').first() if city_id else None
                if mapped is None and not self.location_scopes['allLocations']:
                    mapped = localities.filter(name='Санкт-Петербург').values_list('pk', 'name').first()
                if mapped:
                    self.location_scopes['localityId'], self.territory_label = mapped
                    scopes = [mapped[0]]
                elif not self.location_scopes['allLocations']:
                    return RealEstateComplex.objects.none()
        if scopes or self.location_scopes['allLocations']:
            complexes = RealEstateComplex.objects.filter(is_active=True).select_related(
                'developer__company_group',
                'real_estate_class', 'real_estate_type',
            ).annotate(building_count=Count('realestatecomplexbuilding', distinct=True)).order_by('name', 'pk')
            if self.canonical_locations:
                complexes = complexes.prefetch_related(geography_prefetch())
            return apply_location_scopes(complexes, self.location_scopes)
        cities = legacy_choices('city', active_only=True)
        selected = cities.filter(legacy_id=city_id).first() if city_id else None
        self.selected_city = selected or (
            cities.filter(legacy_name='Санкт-Петербург').first() or cities.first()
        )
        if self.selected_city is None:
            return RealEstateComplex.objects.none()
        return RealEstateComplex.objects.filter(
            Q(district_id__in=legacy_choices('district', city_id=self.selected_city.legacy_id, active_only=True)
              .order_by().values('legacy_id'))
            | Q(district_id__isnull=True, location_links__is_primary=True,
                location_links__location__ancestor_links__ancestor__legacy_mappings__model_name='city',
                location_links__location__ancestor_links__ancestor__legacy_mappings__legacy_id=self.selected_city.legacy_id),
            is_active=True,
        ).select_related(
            'developer__company_group',
            'real_estate_class', 'real_estate_type',
        ).annotate(
            building_count=Count('realestatecomplexbuilding', distinct=True)
        ).order_by('name', 'pk')

    def list(self, request, *args, **kwargs):
        """Include the resolved city so invalid and missing URLs stay coherent."""
        response = super().list(request, *args, **kwargs)
        response.data['selectedCity'] = (
            {'id': self.selected_city.legacy_id, 'name': self.selected_city.legacy_name}
            if self.selected_city else None
        )
        if self.canonical_locations:
            response.data['territoryLabel'] = self.territory_label or (
                self.selected_city.legacy_name if self.selected_city else None
            )
        return response
