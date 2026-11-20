"""Public geographic search and permission-checked precise complex bindings."""

from django.db import transaction
from django.db.models import Prefetch, Q, prefetch_related_objects
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework import serializers
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from location.models import LocationCompatibilityEntry, Location, LocationClosure
from location.presentation import geographic_label
from property.models import RealEstateComplex, RealEstateComplexLocation
from .catalog_options import CatalogOptionQuerySerializer
from .views import CanManageCatalogs


def serialize_location(location):
    """Return canonical identity independently of legacy dictionary IDs."""
    return {
        'id': location.pk, 'label': geographic_label(location), 'name': location.name,
        'type': location.location_type.name, 'category': location.location_type.category,
        'parentId': location.parent_id, 'regionId': location.region_id,
        'parent': location.parent.name if location.parent_id else None,
        'region': location.region.name if location.region_id else None,
        'needsReview': location.needs_review, 'isActive': location.is_active,
    }


def geographic_queryset():
    """Resolve all display context without one query per search result."""
    return Location.objects.select_related('location_type', 'parent', 'region')


class GeographyQuerySerializer(CatalogOptionQuerySerializer):
    """Bound catalog searches before pagination."""

    category = serializers.ChoiceField(
        choices=['region', 'district', 'locality', 'area'], required=False,
    )
    ancestorId = serializers.IntegerField(min_value=1, required=False)
    relatedToId = serializers.IntegerField(min_value=1, required=False)
    legacyRegionId = serializers.IntegerField(min_value=1, required=False)
    legacyCityId = serializers.IntegerField(min_value=1, required=False)
    legacyRegionLookupId = serializers.IntegerField(min_value=1, required=False)
    includeContext = serializers.BooleanField(default=False)


class GeographyAPIView(APIView):
    """Serve the complete local catalog without contacting a provider on search."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Search and paginate geographic roles, including federal-city dual roles."""
        serializer = GeographyQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        parameters = serializer.validated_data
        base = geographic_queryset()
        queryset = base
        if parameters.get('legacyCityId'):
            queryset = queryset.filter(legacy_mappings__model_name='city',
                                       legacy_mappings__legacy_id=parameters['legacyCityId'])
        if parameters.get('legacyRegionLookupId'):
            queryset = queryset.filter(
                legacy_mappings__model_name='region',
                legacy_mappings__legacy_id=parameters['legacyRegionLookupId'],
                location_type__category='region',
            )
        if parameters.get('category') == 'locality':
            queryset = queryset.filter(
                Q(location_type__category='locality') | Q(
                    location_type__category='region',
                    location_type__abbreviation__in=['г', 'г.', 'г.ф.з.'],
                ),
            )
        elif parameters.get('category'):
            queryset = queryset.filter(location_type__category=parameters['category'])
        if parameters.get('regionId'):
            queryset = queryset.filter(region_id=parameters['regionId'])
        if parameters.get('legacyRegionId'):
            queryset = queryset.filter(region_id__in=LocationCompatibilityEntry.objects.filter(
                model_name='region', legacy_id=parameters['legacyRegionId'],
            ).values_list('location_id', flat=True))
        if parameters.get('ancestorId'):
            queryset = queryset.filter(ancestor_links__ancestor_id=parameters['ancestorId'])
        if parameters.get('relatedToId'):
            queryset = queryset.filter(
                Q(ancestor_links__ancestor_id=parameters['relatedToId'])
                | Q(descendant_links__descendant_id=parameters['relatedToId']),
            ).distinct()
        if parameters['activeOnly']:
            queryset = queryset.filter(is_active=True)
        search = parameters.get('q', '').strip()
        if search:
            queryset = queryset.filter(Q(name__icontains=search) | Q(aliases__name__icontains=search)).distinct()
        queryset = queryset.order_by('name', 'pk')
        count = queryset.count()
        page, size = parameters['page'], parameters['pageSize']
        offset = (page - 1) * size
        selected = parameters.get('selectedIds', []) + ([parameters['selected']] if parameters.get('selected') else [])
        rows = list(queryset[offset:offset + size])
        selected_rows = list(base.filter(pk__in=selected))
        if parameters['includeContext']:
            prefetch_related_objects(rows + selected_rows, Prefetch(
                'ancestor_links', queryset=LocationClosure.objects.select_related(
                    'ancestor__location_type',
                ).order_by('depth'),
            ))

        def option_payload(location):
            """Attach canonical scope identifiers only when requested by a form."""
            payload = serialize_location(location)
            if parameters['includeContext']:
                payload['regionLocationId'] = location.region_id
                payload['districtLocationId'] = next((
                    link.ancestor_id for link in location.ancestor_links.all()
                    if link.ancestor.location_type.category == 'district'
                ), None)
            return payload

        return Response({
            'results': [option_payload(row) for row in rows],
            'selected': [option_payload(row) for row in selected_rows],
            'totalCount': count, 'page': page,
            'nextPage': page + 1 if offset + size < count else None,
        })


class ComplexLocationItemSerializer(serializers.Serializer):
    """Resolve only existing active geographic identities."""
    locationId = serializers.PrimaryKeyRelatedField(queryset=Location.objects.filter(is_active=True))
    isPrimary = serializers.BooleanField()
    isHistorical = serializers.BooleanField(default=False)


class BuildingLocationItemSerializer(serializers.Serializer):
    """Accept an explicit territory or primary-territory inheritance."""
    id = serializers.IntegerField(min_value=1)
    locationId = serializers.IntegerField(min_value=1, allow_null=True)


class ComplexLocationsSerializer(serializers.Serializer):
    """Validate a complete atomic replacement of complex territory bindings."""
    locations = ComplexLocationItemSerializer(many=True, allow_empty=False, max_length=100)
    buildings = BuildingLocationItemSerializer(many=True, required=False, max_length=1000)

    def validate_locations(self, rows):
        """Require distinct territories and exactly one primary binding."""
        if sum(row['isPrimary'] for row in rows) != 1:
            raise serializers.ValidationError('Укажите ровно одну основную территорию.')
        if len({row['locationId'].pk for row in rows}) != len(rows):
            raise serializers.ValidationError('Территории не должны повторяться.')
        if any(row['isPrimary'] and row['isHistorical'] for row in rows):
            raise serializers.ValidationError('Основная территория не может быть исторической.')
        return rows


def serialize_complex_locations(complex_object):
    """Expose bindings and effective inherited building territories."""
    links = list(complex_object.location_links.select_related(
        'location__location_type', 'location__parent', 'location__region',
    ).order_by('-is_primary', 'pk'))
    primary = next((row for row in links if row.is_primary), None)
    return {
        'locations': [{**serialize_location(row.location), 'isPrimary': row.is_primary,
                       'isHistorical': row.is_historical} for row in links],
        'buildings': [{
            'id': row.pk, 'number': row.number,
            'locationId': row.complex_location.location_id if row.complex_location_id else None,
            'effectiveLocationId': (row.complex_location.location_id if row.complex_location_id
                                    else primary.location_id if primary else None),
        } for row in complex_object.realestatecomplexbuilding_set.select_related('complex_location').order_by('pk')],
    }


@method_decorator(csrf_protect, name='dispatch')
class ComplexLocationsAPIView(APIView):
    """Refine existing complexes without rewriting legacy or metro references."""

    def get_permissions(self):
        """Keep reads public and protect every catalog mutation."""
        return (AllowAny(),) if self.request.method == 'GET' else (IsAuthenticated(), CanManageCatalogs())

    def get(self, request, pk):
        """Read precise territory bindings without provider requests."""
        return Response(serialize_complex_locations(get_object_or_404(RealEstateComplex, pk=pk)))

    @transaction.atomic
    def put(self, request, pk):
        """Lock the complex and validate building ownership before any mutation."""
        complex_object = get_object_or_404(RealEstateComplex.objects.select_for_update(), pk=pk)
        serializer = ComplexLocationsSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        rows = serializer.validated_data['locations']
        building_rows = serializer.validated_data.get('buildings', [])
        ids = {row['locationId'].pk for row in rows}
        buildings = {row.pk: row for row in complex_object.realestatecomplexbuilding_set.select_related('complex_location')}
        if len({row['id'] for row in building_rows}) != len(building_rows):
            raise serializers.ValidationError({'buildings': 'Корпуса не должны повторяться.'})
        for row in building_rows:
            if row['id'] not in buildings or row['locationId'] is not None and row['locationId'] not in ids:
                raise serializers.ValidationError({'buildings': 'Выберите корпус этого ЖК и одну из его территорий.'})
        updates = {row['id']: row['locationId'] for row in building_rows}
        for building in buildings.values():
            target = updates.get(building.pk, building.complex_location.location_id if building.complex_location_id else None)
            if target is not None and target not in ids:
                raise serializers.ValidationError({'buildings': 'Сначала измените территорию корпуса, использующего удаляемую связь.'})
        complex_object.location_links.filter(is_primary=True).update(is_primary=False)
        links = {}
        for row in rows:
            link, _ = RealEstateComplexLocation.objects.update_or_create(
                real_estate_complex=complex_object, location=row['locationId'],
                defaults={'is_primary': row['isPrimary'], 'is_historical': row['isHistorical']},
            )
            links[row['locationId'].pk] = link
        for identifier, target in updates.items():
            building = buildings[identifier]
            building.complex_location = links.get(target)
            building.save(update_fields=['complex_location', 'updated_at'])
        complex_object.location_links.exclude(location_id__in=ids).delete()
        return Response(serialize_complex_locations(complex_object))
