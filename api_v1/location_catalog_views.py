"""Expose canonical location dictionaries independently of legacy financial IDs."""

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models.deletion import ProtectedError
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers, status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.exceptions import MethodNotAllowed
from rest_framework.response import Response
from rest_framework.views import APIView

from location.catalog_service import (
    CATALOG_CATEGORIES, catalog_locations, delete_catalog_location,
    filter_catalog_locations, save_catalog_location,
)
from location.models import LocationCompatibilityEntry, Location, LocationType
from .geography_views import serialize_location
from .pagination import ApplicationPageNumberPagination
from .views import CanManageCatalogs


class LocationCatalogQuerySerializer(serializers.Serializer):
    """Validate bounded, canonical dictionary filters."""

    q = serializers.CharField(required=False, allow_blank=True, max_length=255)
    regionId = serializers.IntegerField(
        required=False, min_value=1, max_value=9223372036854775807,
    )
    ancestorId = serializers.IntegerField(
        required=False, min_value=1, max_value=9223372036854775807,
    )
    legacyRegionId = serializers.IntegerField(
        required=False, min_value=1, max_value=9223372036854775807,
    )
    legacyCityId = serializers.IntegerField(
        required=False, min_value=1, max_value=9223372036854775807,
    )
    typeId = serializers.IntegerField(required=False, min_value=1, max_value=9223372036854775807)
    status = serializers.ChoiceField(choices=['all', 'active', 'inactive'], default='all')
    ordering = serializers.ChoiceField(
        choices=['name', '-name', 'region', '-region', 'type', '-type', 'parent', '-parent'],
        default='name',
    )


class LocationCatalogWriteSerializer(serializers.Serializer):
    """Accept geographic fields only; financial and source identifiers are read-only."""

    name = serializers.CharField(max_length=255)
    typeId = serializers.PrimaryKeyRelatedField(
        source='location_type', queryset=LocationType.objects.all(),
    )
    parentId = serializers.PrimaryKeyRelatedField(
        source='parent', queryset=Location.objects.all(), required=False, allow_null=True,
    )
    isActive = serializers.BooleanField(source='is_active', default=True)


def location_catalog_payload(location, detailed=False):
    """Include stable canonical identity and official source metadata."""
    result = {
        **serialize_location(location), 'typeId': location.location_type_id,
        'sourceStatus': location.source_status, 'sourceVersion': location.source_version,
    }
    if detailed:
        result['identifiers'] = list(location.identifiers.order_by(
            'provider', 'value',
        ).values('provider', 'value'))
        result['aliases'] = list(location.aliases.order_by('name').values_list('name', flat=True))
    return result


@method_decorator(csrf_protect, name='dispatch')
class LocationCatalogAPIView(APIView):
    """Read publicly and restrict canonical dictionary writes to catalog managers."""

    def get_permissions(self):
        """Keep import authorization separate from ordinary dictionary editing."""
        if self.request.method in ('GET', 'HEAD', 'OPTIONS'):
            return [AllowAny()]
        return [IsAuthenticated(), CanManageCatalogs()]

    def category(self, key):
        """Reject unsupported levels rather than selecting another dictionary."""
        if key not in CATALOG_CATEGORIES:
            raise Http404
        return CATALOG_CATEGORIES[key]

    def get(self, request, dictionary_key, pk=None):
        """Paginate actual Location rows or return one canonical editor record."""
        category = self.category(dictionary_key)
        queryset = catalog_locations(dictionary_key)
        if pk is not None:
            if request.query_params.get('legacy') == '1':
                mapping = get_object_or_404(LocationCompatibilityEntry, model_name={
                    'regions': 'region', 'localities': 'city', 'districts': 'district',
                }[dictionary_key], legacy_id=pk)
                pk = mapping.location_id
            return Response(location_catalog_payload(get_object_or_404(queryset, pk=pk), True))
        serializer = LocationCatalogQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        parameters = serializer.validated_data
        if parameters.get('legacyCityId'):
            city_locations = LocationCompatibilityEntry.objects.filter(
                model_name='city', legacy_id=parameters['legacyCityId'],
            ).values('location_id')
            queryset = queryset.filter(ancestor_links__ancestor_id__in=city_locations)
        queryset = filter_catalog_locations(queryset, parameters)
        paginator = ApplicationPageNumberPagination()
        rows = paginator.paginate_queryset(queryset, request, view=self)
        response = paginator.get_paginated_response([location_catalog_payload(row) for row in rows])
        response.data['types'] = list(LocationType.objects.filter(
            category=category,
        ).order_by('name', 'pk').values('id', 'name'))
        return response

    def post(self, request, dictionary_key, pk=None):
        """Create a manual territory without adding a legacy dictionary row."""
        if pk is not None:
            raise MethodNotAllowed('POST')
        return self.save(request, dictionary_key)

    def patch(self, request, dictionary_key, pk=None):
        """Update an existing identity and keep every business foreign key."""
        if pk is None:
            raise MethodNotAllowed('PATCH')
        return self.save(request, dictionary_key, pk)

    def save(self, request, dictionary_key, pk=None):
        """Share authoritative validation and atomic hierarchy updates."""
        category = self.category(dictionary_key)
        instance = get_object_or_404(catalog_locations(dictionary_key), pk=pk) if pk else None
        serializer = LocationCatalogWriteSerializer(data=request.data, partial=instance is not None)
        serializer.is_valid(raise_exception=True)
        try:
            location = save_catalog_location(category, serializer.validated_data, instance)
        except DjangoValidationError as error:
            raise serializers.ValidationError(
                error.message_dict if hasattr(error, 'message_dict')
                else {'detail': error.messages},
            )
        return Response(
            location_catalog_payload(location, True),
            status=status.HTTP_200_OK if instance else status.HTTP_201_CREATED,
        )

    def delete(self, request, dictionary_key, pk=None):
        """Protect imported records, descendants, complexes, customers and metro."""
        if pk is None:
            raise MethodNotAllowed('DELETE')
        self.category(dictionary_key)
        location = get_object_or_404(catalog_locations(dictionary_key), pk=pk)
        try:
            delete_catalog_location(location)
        except (ProtectedError, DjangoValidationError):
            return Response({'detail': (
                'Удаление невозможно: запись связана с источником, дочерними '
                'территориями или данными приложения. Снимите флаг «Активно».')},
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)
