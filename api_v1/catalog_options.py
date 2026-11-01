from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from bank.models import Bank, MortgageProgram
from location.models import City, District, Metro, MetroLine, Region
from property.models import (
    ApartmentDecoration, ApartmentLayout, CompanyGroup, Developer,
    RealEstateClass, RealEstateComplex, RealEstateComplexBuilding,
    RealEstateType, TransportAccessibilityType, WindowView,
)


class CatalogOptionQuerySerializer(serializers.Serializer):
    """Validate bounded searches and selected catalog identifiers."""

    q = serializers.CharField(required=False, allow_blank=True, max_length=100)
    page = serializers.IntegerField(min_value=1, default=1)
    pageSize = serializers.IntegerField(min_value=1, max_value=100, default=50)
    selected = serializers.IntegerField(required=False, min_value=1)
    selectedIds = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False, max_length=100,
    )
    regionId = serializers.IntegerField(required=False, min_value=1)
    cityId = serializers.IntegerField(required=False, min_value=1)
    districtId = serializers.IntegerField(required=False, min_value=1)
    developerId = serializers.IntegerField(required=False, min_value=1)
    realEstateComplexId = serializers.IntegerField(required=False, min_value=1)
    companyGroupId = serializers.IntegerField(required=False, min_value=1)
    metroLineId = serializers.IntegerField(required=False, min_value=1)
    activeOnly = serializers.BooleanField(default=False)


CATALOG_OPTIONS = {
    'regions': (Region, 'name', (), {}),
    'cities': (City, 'name', (), {'regionId': 'region_id'}),
    'districts': (District, 'name', ('city',), {'cityId': 'city_id'}),
    'developers': (Developer, 'name', ('company_group',),
                   {'companyGroupId': 'company_group_id'}),
    'company-groups': (CompanyGroup, 'name', (), {}),
    'complexes': (RealEstateComplex, 'name', ('district__city', 'developer'), {
        'cityId': 'district__city_id', 'districtId': 'district_id',
        'developerId': 'developer_id',
        'companyGroupId': 'developer__company_group_id',
    }),
    'buildings': (RealEstateComplexBuilding, 'number',
                  ('real_estate_complex__district__city',),
                  {'realEstateComplexId': 'real_estate_complex_id'}),
    'layouts': (ApartmentLayout, 'name', (), {}),
    'decorations': (ApartmentDecoration, 'name', (), {}),
    'window-views': (WindowView, 'name', (), {}),
    'real-estate-classes': (RealEstateClass, 'name', (), {}),
    'real-estate-types': (RealEstateType, 'name', (), {}),
    'transport-accessibility-types': (
        TransportAccessibilityType, 'name', (), {}
    ),
    'metro': (Metro, 'station', ('metro_line',), {
        'cityId': 'metro_line__city_id', 'metroLineId': 'metro_line_id',
    }),
    'metro-lines': (MetroLine, 'line', (), {'cityId': 'city_id'}),
    'banks': (Bank, 'name', (), {}),
    'mortgage-programs': (MortgageProgram, 'name', (), {}),
    'preferential-programs': (MortgageProgram, 'name', (), {}),
}


def serialize_catalog_option(item, label_field):
    """Expose only a public label and cascade context, never private fields."""
    label = getattr(item, label_field)
    if isinstance(item, Developer):
        label = item.get_display_name_with_company_group()
    elif isinstance(item, Metro):
        label = f'{item.station} · {item.metro_line.line}'
    option = {'id': item.pk, 'label': str(label)}
    if isinstance(item, City):
        option['regionId'] = item.region_id
    elif isinstance(item, District):
        option.update(cityId=item.city_id, regionId=item.city.region_id)
    elif isinstance(item, (RealEstateComplex, RealEstateComplexBuilding)):
        complex_object = (item if isinstance(item, RealEstateComplex)
                          else item.real_estate_complex)
        option.update(
            realEstateComplexId=complex_object.pk,
            developerId=complex_object.developer_id,
            districtId=complex_object.district_id,
            cityId=complex_object.district.city_id,
            regionId=complex_object.district.city.region_id,
        )
    return option


class CatalogOptionsAPIView(APIView):
    """Serve searchable public choices and preserve selected values."""

    permission_classes = (AllowAny,)

    def get(self, request, dictionary_key):
        """Search before pagination and retain selections outside the page."""
        configuration = CATALOG_OPTIONS.get(dictionary_key)
        if configuration is None:
            raise NotFound('Справочник не найден.')
        serializer = CatalogOptionQuerySerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        parameters = serializer.validated_data
        model, label_field, related, filters = configuration
        base_queryset = model.objects.all()
        if parameters['activeOnly']:
            base_queryset = base_queryset.filter(is_active=True)
        if dictionary_key == 'preferential-programs':
            base_queryset = base_queryset.filter(is_preferential=True)
        if related:
            base_queryset = base_queryset.select_related(*related)
        queryset = base_queryset
        for name, field in filters.items():
            if parameters.get(name):
                queryset = queryset.filter(**{field: parameters[name]})
        search = parameters.get('q', '').strip()
        if search:
            search_filter = Q(**{f'{label_field}__icontains': search})
            if model == Developer:
                search_filter |= Q(company_group__name__icontains=search)
            queryset = queryset.filter(search_filter)
        queryset = queryset.order_by(label_field, 'pk')
        count = queryset.count()
        page = parameters['page']
        page_size = parameters['pageSize']
        offset = (page - 1) * page_size
        items = list(queryset[offset:offset + page_size])
        selected_identifiers = set(parameters.get('selectedIds', []))
        if parameters.get('selected'):
            selected_identifiers.add(parameters['selected'])
        selected = {item.pk: item for item in items
                    if item.pk in selected_identifiers}
        missing = selected_identifiers - selected.keys()
        if missing:
            selected.update({item.pk: item for item in base_queryset.filter(
                pk__in=missing,
            ).order_by(label_field, 'pk')})
        return Response({
            'results': [serialize_catalog_option(item, label_field)
                        for item in items],
            'selected': [serialize_catalog_option(item, label_field)
                         for item in selected.values()],
            'totalCount': count, 'page': page,
            'nextPage': page + 1 if offset + page_size < count else None,
        })
