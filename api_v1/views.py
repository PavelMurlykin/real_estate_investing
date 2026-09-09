from django.contrib.auth import login, logout
from django.db.models import Q
from django.middleware.csrf import get_token
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.generics import ListAPIView
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bank.models import Bank
from location.models import City
from property.models import Developer, Property, RealEstateComplex
from users.forms import UserLoginForm
from users.roles import (
    can_manage_catalogs,
    can_sync_external_data,
    can_view_all_private_records,
    can_view_private_records,
)

from .pagination import ApplicationPageNumberPagination
from .serializers import (
    LoginRequestSerializer,
    PropertyListItemSerializer,
    PropertyListQuerySerializer,
)


def build_session_payload(user):
    """Build the stable authentication and capability response payload."""
    is_authenticated = user.is_authenticated
    user_payload = None
    if is_authenticated:
        user_payload = {
            'id': user.pk,
            'displayName': user.get_full_name().strip() or user.email,
            'email': user.email,
            'agencyName': user.agency_name,
        }

    return {
        'isAuthenticated': is_authenticated,
        'user': user_payload,
        'capabilities': {
            'manageCatalogs': can_manage_catalogs(user),
            'syncExternalData': can_sync_external_data(user),
            'viewPrivateRecords': can_view_private_records(user),
            'viewAllPrivateRecords': can_view_all_private_records(user),
        },
    }


@method_decorator(ensure_csrf_cookie, name='dispatch')
class SessionAPIView(APIView):
    """Expose the current session and set a CSRF cookie for the SPA."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Return the current user and application capabilities."""
        get_token(request)
        return Response(build_session_payload(request.user))


@method_decorator(csrf_protect, name='dispatch')
class LoginAPIView(APIView):
    """Authenticate a user with the existing Django authentication form."""

    authentication_classes = ()
    permission_classes = (AllowAny,)

    def post(self, request):
        """Create a Django session when submitted credentials are valid."""
        request_serializer = LoginRequestSerializer(data=request.data)
        request_serializer.is_valid(raise_exception=True)
        authentication_form = UserLoginForm(
            request=request._request,
            data={
                'username': request_serializer.validated_data['identifier'],
                'password': request_serializer.validated_data['password'],
            },
        )
        if not authentication_form.is_valid():
            return Response(
                {
                    'errors': {
                        'nonFieldErrors': list(
                            authentication_form.non_field_errors()
                        ),
                    }
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        authenticated_user = authentication_form.get_user()
        login(request._request, authenticated_user)
        return Response(build_session_payload(authenticated_user))


@method_decorator(csrf_protect, name='dispatch')
class LogoutAPIView(APIView):
    """End the authenticated Django session."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Clear the current session and return an empty success response."""
        logout(request._request)
        return Response(status=status.HTTP_204_NO_CONTENT)


class OverviewAPIView(APIView):
    """Return public summary data for the React home page."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Return bounded catalog counts and recently updated properties."""
        recent_properties = (
            Property.objects.select_related(
                'building__real_estate_complex__developer__company_group',
                'building__real_estate_complex__district__city',
                'layout',
                'decoration',
            )
            .order_by('-updated_at', '-id')[:4]
        )
        return Response(
            {
                'statistics': [
                    {
                        'key': 'properties',
                        'label': 'Объекты',
                        'value': Property.objects.count(),
                    },
                    {
                        'key': 'complexes',
                        'label': 'Жилые комплексы',
                        'value': RealEstateComplex.objects.filter(
                            is_active=True
                        ).count(),
                    },
                    {
                        'key': 'developers',
                        'label': 'Застройщики',
                        'value': Developer.objects.filter(is_active=True).count(),
                    },
                    {
                        'key': 'cities',
                        'label': 'Города',
                        'value': City.objects.filter(is_active=True).count(),
                    },
                    {
                        'key': 'banks',
                        'label': 'Банки',
                        'value': Bank.objects.filter(is_active=True).count(),
                    },
                ],
                'recentProperties': PropertyListItemSerializer(
                    recent_properties,
                    many=True,
                ).data,
            }
        )


class PropertyListAPIView(ListAPIView):
    """Return a filtered and paginated public property catalog."""

    serializer_class = PropertyListItemSerializer
    pagination_class = ApplicationPageNumberPagination
    permission_classes = (AllowAny,)
    ordering_fields = {
        'city': 'building__real_estate_complex__district__city__name',
        'developer': 'building__real_estate_complex__developer__name',
        'realEstateComplex': 'building__real_estate_complex__name',
        'building': 'building__number',
        'apartmentNumber': 'apartment_number',
        'layout': 'layout__name',
        'area': 'area',
        'propertyCost': 'property_cost',
    }

    def get_queryset(self):
        """Apply validated filters and deterministic ordering."""
        query_serializer = PropertyListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data

        queryset = Property.objects.select_related(
            'building__real_estate_complex__developer__company_group',
            'building__real_estate_complex__district__city',
            'layout',
            'decoration',
        )

        search = filters.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(apartment_number__icontains=search)
                | Q(building__number__icontains=search)
                | Q(building__real_estate_complex__name__icontains=search)
                | Q(
                    building__real_estate_complex__developer__name__icontains=(
                        search
                    )
                )
                | Q(
                    building__real_estate_complex__district__city__name__icontains=(
                        search
                    )
                )
            )

        filter_fields = {
            'city': 'building__real_estate_complex__district__city_id',
            'developer': 'building__real_estate_complex__developer_id',
            'realEstateComplex': 'building__real_estate_complex_id',
            'building': 'building_id',
            'layout': 'layout_id',
        }
        for query_name, model_field in filter_fields.items():
            value = filters.get(query_name)
            if value:
                queryset = queryset.filter(**{model_field: value})

        ordering = filters['ordering']
        descending = ordering.startswith('-')
        ordering_key = ordering.removeprefix('-')
        ordering_field = self.ordering_fields[ordering_key]
        ordering_prefix = '-' if descending else ''
        return queryset.order_by(
            f'{ordering_prefix}{ordering_field}',
            'apartment_number',
            'id',
        )
