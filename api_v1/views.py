from django.conf import settings
from django.contrib.auth import login, logout
from django.db.models import Prefetch, Q
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.generics import (
    ListAPIView,
    ListCreateAPIView,
    RetrieveAPIView,
    RetrieveUpdateAPIView,
)
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from bank.models import (
    Bank,
    BankProgram,
    KeyRate,
    MortgageProgram,
    MortgageProgramRegionalCreditLimit,
)
from customer.models import Customer
from location.models import City, District
from mortgage.excel import export_saved_mortgage_calculation_excel
from mortgage.models import MortgageCalculation
from mortgage.word import export_saved_mortgage_calculation_word
from property.models import (
    ApartmentLayout,
    Developer,
    Property,
    RealEstateComplex,
)
from users.forms import UserLoginForm
from users.roles import (
    can_manage_catalogs,
    can_sync_external_data,
    can_view_all_private_records,
    can_view_private_records,
)

from .mortgage_service import (
    build_saved_mortgage_payment_schedule,
    calculate_market_mortgage,
    create_saved_market_mortgage,
    serialize_saved_mortgage_detail,
    serialize_saved_mortgage_list_item,
)
from .pagination import ApplicationPageNumberPagination
from .serializers import (
    CustomerDetailSerializer,
    CustomerFormOptionsQuerySerializer,
    CustomerListItemSerializer,
    CustomerListQuerySerializer,
    CustomerWriteSerializer,
    LoginRequestSerializer,
    MortgageCalculationRequestSerializer,
    PropertyDetailSerializer,
    PropertyListItemSerializer,
    PropertyListQuerySerializer,
    SavedMortgageCalculationCreateSerializer,
    SavedMortgageCalculationListQuerySerializer,
    SavedTrenchMortgageCalculationCreateSerializer,
    TrenchMortgageCalculationRequestSerializer,
)
from .trench_mortgage_service import (
    TrenchMortgageValidationError,
    calculate_trench_mortgage,
    create_saved_trench_mortgage,
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
                        'value': Developer.objects.filter(
                            is_active=True
                        ).count(),
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


class MortgageOptionsAPIView(APIView):
    """Return active bank programs and defaults for the calculator."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Return a bounded, query-efficient set of mortgage options."""
        latest_key_rate = (
            KeyRate.objects.filter(is_active=True)
            .order_by('-meeting_date')
            .values_list('key_rate', flat=True)
            .first()
        )
        active_regional_limits = (
            MortgageProgramRegionalCreditLimit.objects.filter(is_active=True)
            .order_by('region_id')
        )
        bank_programs = list(
            BankProgram.objects.select_related('bank', 'mortgage_program')
            .prefetch_related(
                Prefetch(
                    'mortgage_program__regional_credit_limits',
                    queryset=active_regional_limits,
                    to_attr='active_regional_credit_limits',
                )
            )
            .filter(
                is_active=True,
                bank__is_active=True,
                mortgage_program__is_active=True,
            )
            .order_by('bank__name', 'mortgage_program__name', 'id')
        )

        banks_by_identifier = {}
        programs = []
        for bank_program in bank_programs:
            banks_by_identifier.setdefault(
                bank_program.bank_id,
                {
                    'id': bank_program.bank_id,
                    'name': bank_program.bank.name,
                    'logoUrl': bank_program.bank.logo_url,
                },
            )
            mortgage_program = bank_program.mortgage_program
            programs.append(
                {
                    'id': bank_program.pk,
                    'bankId': bank_program.bank_id,
                    'programId': mortgage_program.pk,
                    'programName': mortgage_program.name,
                    'interestRate': str(bank_program.interest_rate),
                    'minimumInitialPaymentPercent': str(
                        bank_program.minimum_initial_payment_percent
                    ),
                    'maximumLoanTermYears': (
                        bank_program.maximum_loan_term_years
                    ),
                    'isPreferential': mortgage_program.is_preferential,
                    'creditLimit': (
                        str(mortgage_program.credit_limit)
                        if mortgage_program.credit_limit is not None
                        else None
                    ),
                    'regionalCreditLimits': [
                        {
                            'regionId': regional_limit.region_id,
                            'creditLimit': str(
                                regional_limit.credit_limit
                            ),
                        }
                        for regional_limit in (
                            mortgage_program.active_regional_credit_limits
                        )
                    ],
                }
            )

        return Response(
            {
                'defaultInitialPaymentDate': timezone.localdate().isoformat(),
                'keyRate': str(latest_key_rate or 0),
                'banks': list(banks_by_identifier.values()),
                'programs': programs,
            }
        )


@method_decorator(csrf_protect, name='dispatch')
class MortgageCalculationAPIView(APIView):
    """Calculate a market mortgage without persisting user data."""

    permission_classes = (AllowAny,)

    def post(self, request):
        """Validate calculator inputs and return summary plus schedule."""
        request_serializer = MortgageCalculationRequestSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)
        return Response(
            calculate_market_mortgage(request_serializer.validated_data)
        )


def _raise_trench_mortgage_validation_error(error):
    """Translate established domain validation into the API error shape."""
    raise ValidationError(
        {'nonFieldErrors': list(error.messages)}
    ) from error


@method_decorator(csrf_protect, name='dispatch')
class TrenchMortgageCalculationAPIView(APIView):
    """Calculate a trench mortgage without persisting user data."""

    permission_classes = (AllowAny,)

    def post(self, request):
        """Validate tranche inputs and return summary plus schedule."""
        request_serializer = TrenchMortgageCalculationRequestSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)
        try:
            _, response_payload = calculate_trench_mortgage(
                request_serializer.validated_data
            )
        except TrenchMortgageValidationError as error:
            _raise_trench_mortgage_validation_error(error)
        return Response(response_payload)


@method_decorator(csrf_protect, name='dispatch')
class SavedTrenchMortgageCalculationCreateAPIView(APIView):
    """Persist an authenticated user's property-backed trench scenario."""

    permission_classes = (IsAuthenticated,)

    def post(self, request):
        """Recalculate and save a validated trench mortgage atomically."""
        request_serializer = SavedTrenchMortgageCalculationCreateSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)
        validated_data = request_serializer.validated_data
        try:
            response_payload = create_saved_trench_mortgage(
                parameters=validated_data['parameters'],
                property_object=validated_data['property'],
                user=request.user,
            )
        except TrenchMortgageValidationError as error:
            _raise_trench_mortgage_validation_error(error)
        return Response(response_payload, status=status.HTTP_201_CREATED)


def _saved_mortgage_calculation_queryset(user):
    """Return saved calculations scoped to the current application role."""
    queryset = MortgageCalculation.objects.select_related(
        'property',
        'property__layout',
        'property__decoration',
        'property__building',
        'property__building__real_estate_complex',
        'property__building__real_estate_complex__developer__company_group',
        'property__building__real_estate_complex__district__city',
        'property__building__real_estate_complex__real_estate_class',
    )
    if can_view_all_private_records(user):
        return queryset
    return queryset.filter(user=user)


def _customer_queryset(user):
    """Return customers visible to their owner or an application admin."""
    queryset = Customer.objects.all()
    if can_view_all_private_records(user):
        return queryset
    return queryset.filter(user=user)


def _build_bounded_option_rows(queryset, maximum_results):
    """Serialize a name queryset and report whether its bound was reached."""
    rows = list(queryset.values('id', 'name')[:maximum_results + 1])
    return rows[:maximum_results], len(rows) > maximum_results


@method_decorator(csrf_protect, name='dispatch')
class SavedMortgageCalculationListCreateAPIView(APIView):
    """List owner-scoped calculations and save a validated scenario."""

    permission_classes = (IsAuthenticated,)
    ordering_fields = {
        'createdAt': 'timestamp',
        'finalPropertyCost': 'final_property_cost',
        'mainMonthlyPayment': 'main_monthly_payment',
        'mortgageTermMonths': 'mortgage_term',
        'annualRate': 'annual_rate',
    }

    def get(self, request):
        """Return a bounded, filterable saved-calculation history."""
        query_serializer = SavedMortgageCalculationListQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        queryset = _saved_mortgage_calculation_queryset(request.user)

        search = filters.get('q', '')
        if search:
            queryset = queryset.filter(
                Q(property__apartment_number__icontains=search)
                | Q(property__building__number__icontains=search)
                | Q(
                    property__building__real_estate_complex__name__icontains=(
                        search
                    )
                )
                | Q(
                    property__building__real_estate_complex__district__city__name__icontains=(
                        search
                    )
                )
            )

        ordering = filters['ordering']
        descending = ordering.startswith('-')
        ordering_key = ordering.removeprefix('-')
        ordering_field = self.ordering_fields[ordering_key]
        ordering_prefix = '-' if descending else ''
        queryset = queryset.order_by(
            f'{ordering_prefix}{ordering_field}',
            '-pk',
        )

        paginator = ApplicationPageNumberPagination()
        calculations = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )
        return paginator.get_paginated_response(
            [
                serialize_saved_mortgage_list_item(calculation)
                for calculation in calculations
            ]
        )

    def post(self, request):
        """Recalculate and persist an authenticated user's scenario."""
        request_serializer = SavedMortgageCalculationCreateSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)
        validated_data = request_serializer.validated_data
        calculation = create_saved_market_mortgage(
            parameters=validated_data['parameters'],
            property_object=validated_data['property'],
            user=request.user,
        )
        calculation = _saved_mortgage_calculation_queryset(
            request.user
        ).get(pk=calculation.pk)
        return Response(
            serialize_saved_mortgage_detail(calculation),
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class SavedMortgageCalculationDetailAPIView(APIView):
    """Return or delete one owner-scoped saved calculation."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        """Return a private calculation or a non-disclosing 404."""
        calculation = get_object_or_404(
            _saved_mortgage_calculation_queryset(request.user),
            pk=pk,
        )
        return Response(serialize_saved_mortgage_detail(calculation))

    def delete(self, request, pk):
        """Delete a private calculation without disclosing other owners."""
        calculation = get_object_or_404(
            _saved_mortgage_calculation_queryset(request.user),
            pk=pk,
        )
        calculation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SavedMortgageCalculationExportAPIView(APIView):
    """Export one owner-scoped saved calculation in an approved format."""

    permission_classes = (IsAuthenticated,)
    exporters = {
        'excel': export_saved_mortgage_calculation_excel,
        'word': export_saved_mortgage_calculation_word,
    }

    def get(self, request, pk, export_format):
        """Return a private calculation as an attachment or a safe 404."""
        exporter = self.exporters.get(export_format)
        if exporter is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        calculation = get_object_or_404(
            _saved_mortgage_calculation_queryset(request.user),
            pk=pk,
        )
        payment_schedule = build_saved_mortgage_payment_schedule(calculation)
        return exporter(calculation, payment_schedule)


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


class PropertyDetailAPIView(RetrieveAPIView):
    """Return one public property with all detail-screen relationships."""

    serializer_class = PropertyDetailSerializer
    permission_classes = (AllowAny,)
    queryset = Property.objects.select_related(
        'building__real_estate_complex__developer__company_group',
        'building__real_estate_complex__district__city__region',
        'building__real_estate_complex__real_estate_class',
        'building__real_estate_complex__real_estate_type',
        'layout',
        'decoration',
    ).prefetch_related('window_views')


class CustomerFormOptionsAPIView(APIView):
    """Return bounded dictionaries needed by the React customer form."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        """Return active choices and districts for the selected city."""
        query_serializer = CustomerFormOptionsQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        maximum_results = settings.PUBLIC_CATALOG_API_MAX_RESULTS
        desired_city_identifier = query_serializer.validated_data.get(
            'desiredCity'
        )

        cities, cities_truncated = _build_bounded_option_rows(
            City.objects.filter(is_active=True).order_by('name', 'pk'),
            maximum_results,
        )
        districts_queryset = District.objects.none()
        if desired_city_identifier:
            districts_queryset = District.objects.filter(
                is_active=True,
                city_id=desired_city_identifier,
            ).order_by('name', 'pk')
        districts, districts_truncated = _build_bounded_option_rows(
            districts_queryset,
            maximum_results,
        )
        layouts, layouts_truncated = _build_bounded_option_rows(
            ApartmentLayout.objects.filter(is_active=True).order_by(
                'name',
                'pk',
            ),
            maximum_results,
        )
        preferential_programs, programs_truncated = (
            _build_bounded_option_rows(
                MortgageProgram.objects.filter(
                    is_active=True,
                    is_preferential=True,
                ).order_by('name', 'pk'),
                maximum_results,
            )
        )

        return Response(
            {
                'cities': cities,
                'districts': districts,
                'layouts': layouts,
                'preferentialPrograms': preferential_programs,
                'purchaseGoals': [
                    {'value': value, 'label': label}
                    for value, label in Customer.PURCHASE_GOAL_CHOICES
                ],
                'cardinalDirections': [
                    {'value': value, 'label': label}
                    for value, label in Customer.CARDINAL_DIRECTION_CHOICES
                ],
                'truncated': {
                    'cities': cities_truncated,
                    'districts': districts_truncated,
                    'layouts': layouts_truncated,
                    'preferentialPrograms': programs_truncated,
                },
            }
        )


@method_decorator(csrf_protect, name='dispatch')
class CustomerListAPIView(ListCreateAPIView):
    """Return a searchable, owner-scoped, paginated customer directory."""

    serializer_class = CustomerListItemSerializer
    pagination_class = ApplicationPageNumberPagination
    permission_classes = (IsAuthenticated,)
    ordering_fields = {
        'createdAt': ('created_at',),
        'name': ('first_name', 'last_name'),
    }

    def get_serializer_class(self):
        """Use a dedicated write contract for customer creation."""
        if self.request.method == 'POST':
            return CustomerWriteSerializer
        return CustomerListItemSerializer

    def perform_create(self, serializer):
        """Create a customer owned by the authenticated request user."""
        serializer.save()

    def get_queryset(self):
        """Apply validated customer filters and deterministic ordering."""
        query_serializer = CustomerListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        queryset = _customer_queryset(self.request.user).select_related(
            'residence_city'
        )
        search = filters.get('q', '')
        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search)
                | Q(last_name__icontains=search)
                | Q(phone__icontains=search)
                | Q(email__icontains=search)
            )

        ordering = filters['ordering']
        descending = ordering.startswith('-')
        ordering_key = ordering.removeprefix('-')
        ordering_prefix = '-' if descending else ''
        ordering_fields = [
            f'{ordering_prefix}{field_name}'
            for field_name in self.ordering_fields[ordering_key]
        ]
        return queryset.order_by(*ordering_fields, '-pk')


@method_decorator(csrf_protect, name='dispatch')
class CustomerDetailAPIView(RetrieveUpdateAPIView):
    """Return one owner-scoped customer and calculated buying capacity."""

    serializer_class = CustomerDetailSerializer
    permission_classes = (IsAuthenticated,)

    def get_serializer_class(self):
        """Use the private read or write serializer for the HTTP method."""
        if self.request.method in {'PUT', 'PATCH'}:
            return CustomerWriteSerializer
        return CustomerDetailSerializer

    def get_queryset(self):
        """Load the customer profile relations without per-field queries."""
        return (
            _customer_queryset(self.request.user)
            .select_related(
                'residence_city',
                'desired_city__region',
                'desired_district',
            )
            .prefetch_related(
                'desired_layouts',
                Prefetch(
                    'preferential_programs',
                    queryset=MortgageProgram.objects.prefetch_related(
                        'regional_credit_limits'
                    ),
                ),
            )
        )

    def get_serializer_context(self):
        """Add the authoritative key rate only to read serialization."""
        context = super().get_serializer_context()
        if self.request.method == 'GET':
            context['key_rate'] = Customer.get_actual_cbr_key_rate()
        return context
