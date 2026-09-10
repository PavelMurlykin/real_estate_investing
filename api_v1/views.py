from django.conf import settings
from django.contrib.auth import login, logout
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.db.models import Count, Prefetch, Q
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
    RetrieveUpdateDestroyAPIView,
)
from rest_framework.permissions import (
    AllowAny,
    BasePermission,
    IsAuthenticated,
)
from rest_framework.response import Response
from rest_framework.views import APIView

from bank.models import (
    Bank,
    BankProgram,
    KeyRate,
    MortgageProgram,
    MortgageProgramRegionalCreditLimit,
)
from customer.models import (
    Customer,
    CustomerCalculation,
    CustomerTrenchCalculation,
)
from customer.views import (
    _build_customer_word_calculation,
    _export_single_customer_word_calculation,
    _get_selected_customer_calculation_links,
)
from location.models import City, District, Region
from mortgage.excel import export_saved_mortgage_calculation_excel
from mortgage.models import MortgageCalculation
from mortgage.word import (
    export_customer_mortgage_calculations_word,
    export_saved_mortgage_calculation_word,
    export_trench_mortgage_word,
)
from property.models import (
    ApartmentDecoration,
    ApartmentLayout,
    CompanyGroup,
    Developer,
    Property,
    RealEstateComplex,
    RealEstateComplexBuilding,
    WindowView,
)
from trench_mortgage.models import TrenchMortgageCalculation
from trench_mortgage.views import _export_trench_excel
from users.forms import UserLoginForm
from users.roles import (
    can_manage_catalogs,
    can_sync_external_data,
    can_view_all_private_records,
    can_view_private_records,
)

from .customer_calculation_service import (
    build_customer_calculation_queryset,
    serialize_customer_calculation_link,
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
    CompanyGroupListQuerySerializer,
    CompanyGroupSerializer,
    DeveloperListQuerySerializer,
    DeveloperPublicSerializer,
    DeveloperSerializer,
    CustomerDetailSerializer,
    CustomerCalculationExportRequestSerializer,
    CustomerCalculationLinkCreateSerializer,
    CustomerCalculationListQuerySerializer,
    CustomerFormOptionsQuerySerializer,
    CustomerListItemSerializer,
    CustomerListQuerySerializer,
    CustomerWriteSerializer,
    LoginRequestSerializer,
    MortgageCalculationRequestSerializer,
    PropertyDetailSerializer,
    PropertyFormOptionsQuerySerializer,
    PropertyListItemSerializer,
    PropertyListQuerySerializer,
    PropertyWriteSerializer,
    SavedMortgageCalculationCreateSerializer,
    SavedMortgageCalculationListQuerySerializer,
    SavedTrenchMortgageCalculationCreateSerializer,
    SavedTrenchMortgageCalculationListQuerySerializer,
    TrenchMortgageCalculationRequestSerializer,
)
from .trench_mortgage_service import (
    TrenchMortgageValidationError,
    build_saved_trench_mortgage_data,
    calculate_trench_mortgage,
    create_saved_trench_mortgage,
    serialize_saved_trench_mortgage_detail,
    serialize_saved_trench_mortgage_list_item,
)


class CanManageCatalogs(BasePermission):
    """Allow unsafe catalog operations only to application moderators."""

    def has_permission(self, request, view):
        """Return whether the current user may manage shared catalogs."""
        return can_manage_catalogs(request.user)


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


def _saved_trench_mortgage_calculation_queryset(user):
    """Return saved tranche calculations scoped to the current role."""
    queryset = TrenchMortgageCalculation.objects.select_related(
        'property',
        'property__layout',
        'property__decoration',
        'property__building',
        'property__building__real_estate_complex',
        'property__building__real_estate_complex__developer__company_group',
        'property__building__real_estate_complex__district__city',
        'property__building__real_estate_complex__real_estate_class',
    ).prefetch_related('trenches')
    if can_view_all_private_records(user):
        return queryset
    return queryset.filter(user=user)


@method_decorator(csrf_protect, name='dispatch')
class SavedTrenchMortgageCalculationListCreateAPIView(APIView):
    """List owner-scoped tranche scenarios and persist new ones."""

    permission_classes = (IsAuthenticated,)
    ordering_fields = {
        'createdAt': 'timestamp',
        'finalPropertyCost': 'final_property_cost',
        'mortgageTermMonths': 'mortgage_term',
        'annualRate': 'annual_rate',
        'trenchCount': 'trench_count',
    }

    def get(self, request):
        """Return bounded, searchable tranche-calculation history."""
        query_serializer = SavedTrenchMortgageCalculationListQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        queryset = _saved_trench_mortgage_calculation_queryset(request.user)

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
        linked_calculation_identifiers = set()
        customer_identifier = filters.get('customerId')
        if customer_identifier:
            customer = get_object_or_404(
                _customer_queryset(request.user),
                pk=customer_identifier,
            )
            linked_calculation_identifiers = set(
                CustomerTrenchCalculation.objects.filter(
                    customer=customer,
                    calculation_id__in=(
                        calculation.pk for calculation in calculations
                    ),
                ).values_list('calculation_id', flat=True)
            )
        return paginator.get_paginated_response(
            [
                serialize_saved_trench_mortgage_list_item(
                    calculation,
                    is_linked=(
                        calculation.pk in linked_calculation_identifiers
                    ),
                )
                for calculation in calculations
            ]
        )

    def post(self, request):
        """Recalculate and save a validated trench mortgage atomically."""
        request_serializer = SavedTrenchMortgageCalculationCreateSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)
        validated_data = request_serializer.validated_data
        customer = None
        customer_identifier = validated_data.get('customerId')
        if customer_identifier:
            customer = get_object_or_404(
                _customer_queryset(request.user),
                pk=customer_identifier,
            )
        with transaction.atomic():
            try:
                response_payload = create_saved_trench_mortgage(
                    parameters=validated_data['parameters'],
                    property_object=validated_data['property'],
                    user=request.user,
                )
            except TrenchMortgageValidationError as error:
                _raise_trench_mortgage_validation_error(error)
            if customer is not None:
                CustomerTrenchCalculation.objects.create(
                    customer=customer,
                    calculation_id=response_payload['id'],
                )
        return Response(response_payload, status=status.HTTP_201_CREATED)


@method_decorator(csrf_protect, name='dispatch')
class SavedTrenchMortgageCalculationDetailAPIView(APIView):
    """Return or delete one owner-scoped saved tranche scenario."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        """Return a private tranche scenario or a non-disclosing 404."""
        calculation = get_object_or_404(
            _saved_trench_mortgage_calculation_queryset(request.user),
            pk=pk,
        )
        return Response(serialize_saved_trench_mortgage_detail(calculation))

    def delete(self, request, pk):
        """Delete a private tranche scenario without exposing owners."""
        calculation = get_object_or_404(
            _saved_trench_mortgage_calculation_queryset(request.user),
            pk=pk,
        )
        calculation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class SavedTrenchMortgageCalculationExportAPIView(APIView):
    """Export one owner-scoped tranche calculation in a safe format."""

    permission_classes = (IsAuthenticated,)
    exporters = {
        'excel': _export_trench_excel,
        'word': export_trench_mortgage_word,
    }

    def get(self, request, pk, export_format):
        """Return a private tranche scenario as a file attachment."""
        exporter = self.exporters.get(export_format)
        if exporter is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        calculation = get_object_or_404(
            _saved_trench_mortgage_calculation_queryset(request.user),
            pk=pk,
        )
        calculation_data = build_saved_trench_mortgage_data(calculation)
        return exporter(calculation_data)


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
        linked_calculation_identifiers = set()
        customer_identifier = filters.get('customerId')
        if customer_identifier:
            customer = get_object_or_404(
                _customer_queryset(request.user),
                pk=customer_identifier,
            )
            linked_calculation_identifiers = set(
                CustomerCalculation.objects.filter(
                    customer=customer,
                    calculation_id__in=(
                        calculation.pk for calculation in calculations
                    ),
                ).values_list('calculation_id', flat=True)
            )
        return paginator.get_paginated_response(
            [
                serialize_saved_mortgage_list_item(
                    calculation,
                    is_linked=(
                        calculation.pk in linked_calculation_identifiers
                    ),
                )
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
        customer = None
        customer_identifier = validated_data.get('customerId')
        if customer_identifier:
            customer = get_object_or_404(
                _customer_queryset(request.user),
                pk=customer_identifier,
            )
        with transaction.atomic():
            calculation = create_saved_market_mortgage(
                parameters=validated_data['parameters'],
                property_object=validated_data['property'],
                user=request.user,
            )
            if customer is not None:
                CustomerCalculation.objects.create(
                    customer=customer,
                    calculation=calculation,
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


def _company_group_queryset():
    """Return company groups annotated with their developer count."""
    return CompanyGroup.objects.annotate(developer_count=Count('developers'))


@method_decorator(csrf_protect, name='dispatch')
class CompanyGroupListCreateAPIView(ListCreateAPIView):
    """List company groups publicly and let moderators create entries."""

    serializer_class = CompanyGroupSerializer
    pagination_class = ApplicationPageNumberPagination

    def get_permissions(self):
        """Keep reads public and protect catalog creation."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def get_queryset(self):
        """Apply validated search and deterministic ordering."""
        query_serializer = CompanyGroupListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        queryset = _company_group_queryset()
        search = filters.get('q', '')
        if search:
            queryset = queryset.filter(name__icontains=search)
        ordering = filters['ordering']
        return queryset.order_by(ordering, 'pk')

    def create(self, request, *args, **kwargs):
        """Create an entry and return its annotated representation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        company_group = serializer.save()
        company_group = _company_group_queryset().get(pk=company_group.pk)
        response_serializer = self.get_serializer(company_group)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class CompanyGroupDetailAPIView(RetrieveUpdateDestroyAPIView):
    """Retrieve a company group and protect its mutations."""

    serializer_class = CompanyGroupSerializer
    queryset = _company_group_queryset()

    def get_permissions(self):
        """Keep reads public and protect update and delete operations."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def update(self, request, *args, **kwargs):
        """Update an entry and return its annotated representation."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        company_group = serializer.save()
        company_group = _company_group_queryset().get(pk=company_group.pk)
        return Response(self.get_serializer(company_group).data)

    def destroy(self, request, *args, **kwargs):
        """Delete an unused group or explain its protected dependency."""
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    'detail': (
                        'Группу компаний нельзя удалить, пока с ней '
                        'связаны застройщики.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


def _developer_queryset():
    """Return developers with all data needed by their API representation."""
    return (
        Developer.objects.select_related('company_group')
        .prefetch_related('regions')
        .annotate(
            complex_count=Count('realestatecomplex', distinct=True)
        )
    )


@method_decorator(csrf_protect, name='dispatch')
class DeveloperListCreateAPIView(ListCreateAPIView):
    """List safe developer fields and let moderators create entries."""

    pagination_class = ApplicationPageNumberPagination
    ordering_fields = {
        'name': 'name',
        'companyGroup': 'company_group__name',
        'createdAt': 'created_at',
    }

    def get_permissions(self):
        """Keep safe directory reads public and protect creation."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def get_serializer_class(self):
        """Keep sensitive developer fields out of public list responses."""
        if self.request.method == 'GET':
            return DeveloperPublicSerializer
        return DeveloperSerializer

    def get_queryset(self):
        """Apply validated public filters and deterministic ordering."""
        query_serializer = DeveloperListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        queryset = _developer_queryset()

        search = filters.get('q', '')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(company_group__name__icontains=search)
            )
        if filters.get('companyGroupId'):
            queryset = queryset.filter(
                company_group_id=filters['companyGroupId']
            )
        if filters.get('regionId'):
            queryset = queryset.filter(regions__id=filters['regionId'])
        if filters['status'] != 'all':
            queryset = queryset.filter(
                is_active=filters['status'] == 'active'
            )

        ordering = filters['ordering']
        ordering_prefix = '-' if ordering.startswith('-') else ''
        ordering_key = ordering.removeprefix('-')
        ordering_field = self.ordering_fields[ordering_key]
        return queryset.order_by(
            f'{ordering_prefix}{ordering_field}',
            'name',
            'pk',
        )

    def create(self, request, *args, **kwargs):
        """Create a developer and return its manager-only representation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            developer = serializer.save()
        developer = _developer_queryset().get(pk=developer.pk)
        return Response(
            self.get_serializer(developer).data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class DeveloperDetailAPIView(RetrieveUpdateDestroyAPIView):
    """Expose full developer data only to catalog managers."""

    serializer_class = DeveloperSerializer
    queryset = _developer_queryset()
    permission_classes = (IsAuthenticated, CanManageCatalogs)

    def update(self, request, *args, **kwargs):
        """Update a developer and return its complete representation."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            developer = serializer.save()
        developer = _developer_queryset().get(pk=developer.pk)
        return Response(self.get_serializer(developer).data)

    def destroy(self, request, *args, **kwargs):
        """Delete an unused developer or explain its protected dependency."""
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    'detail': (
                        'Застройщика нельзя удалить, пока с ним связаны '
                        'жилые комплексы.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class DeveloperOptionsAPIView(APIView):
    """Return bounded non-sensitive dictionaries for developer screens."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Return company groups and regions with truncation metadata."""
        maximum_results = settings.PUBLIC_CATALOG_API_MAX_RESULTS
        company_groups, company_groups_truncated = _build_bounded_option_rows(
            CompanyGroup.objects.order_by('name', 'pk'),
            maximum_results,
        )
        regions, regions_truncated = _build_bounded_option_rows(
            Region.objects.order_by('name', 'pk'),
            maximum_results,
        )
        return Response(
            {
                'companyGroups': company_groups,
                'regions': regions,
                'truncated': {
                    'companyGroups': company_groups_truncated,
                    'regions': regions_truncated,
                },
            }
        )


def _property_detail_queryset():
    """Return the optimized queryset shared by property detail responses."""
    return Property.objects.select_related(
        'building__real_estate_complex__developer__company_group',
        'building__real_estate_complex__district__city__region',
        'building__real_estate_complex__real_estate_class',
        'building__real_estate_complex__real_estate_type',
        'layout',
        'decoration',
    ).prefetch_related('window_views')


@method_decorator(csrf_protect, name='dispatch')
class PropertyListAPIView(ListCreateAPIView):
    """List public properties and let moderators create a property."""

    serializer_class = PropertyListItemSerializer
    pagination_class = ApplicationPageNumberPagination
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

    def get_permissions(self):
        """Keep catalog reads public and protect the create operation."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def get_serializer_class(self):
        """Use separate public read and moderator write contracts."""
        if self.request.method == 'GET':
            return PropertyListItemSerializer
        return PropertyWriteSerializer

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

    def create(self, request, *args, **kwargs):
        """Create a property and return the full detail representation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        property_object = serializer.save()
        property_object = _property_detail_queryset().get(
            pk=property_object.pk
        )
        response_serializer = PropertyDetailSerializer(
            property_object,
            context=self.get_serializer_context(),
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class PropertyDetailAPIView(RetrieveUpdateDestroyAPIView):
    """Read a property publicly and protect moderator mutations."""

    queryset = _property_detail_queryset()

    def get_permissions(self):
        """Keep detail reads public and protect update and delete."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def get_serializer_class(self):
        """Use separate public read and moderator write contracts."""
        if self.request.method == 'GET':
            return PropertyDetailSerializer
        return PropertyWriteSerializer

    def update(self, request, *args, **kwargs):
        """Update a property and return its full detail representation."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        property_object = serializer.save()
        property_object = _property_detail_queryset().get(
            pk=property_object.pk
        )
        response_serializer = PropertyDetailSerializer(
            property_object,
            context=self.get_serializer_context(),
        )
        return Response(response_serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Delete a property or report protected dependent records."""
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    'detail': (
                        'Объект нельзя удалить, пока с ним связаны расчёты.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class PropertyFormOptionsAPIView(APIView):
    """Return bounded hierarchical dictionaries for the property form."""

    permission_classes = (IsAuthenticated, CanManageCatalogs)

    def get(self, request):
        """Return choices restricted by the selected parent identifiers."""
        query_serializer = PropertyFormOptionsQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        maximum_results = settings.PUBLIC_CATALOG_API_MAX_RESULTS

        regions, regions_truncated = _build_bounded_option_rows(
            Region.objects.order_by('name', 'pk'),
            maximum_results,
        )
        cities_queryset = City.objects.none()
        if filters.get('regionId'):
            cities_queryset = City.objects.filter(
                region_id=filters['regionId']
            ).order_by('name', 'pk')
        cities, cities_truncated = _build_bounded_option_rows(
            cities_queryset,
            maximum_results,
        )

        districts_queryset = District.objects.none()
        if filters.get('cityId'):
            districts_queryset = District.objects.filter(
                city_id=filters['cityId']
            ).order_by('name', 'pk')
        districts, districts_truncated = _build_bounded_option_rows(
            districts_queryset,
            maximum_results,
        )

        developer_objects = list(
            Developer.objects.select_related('company_group').order_by(
                'name',
                'pk',
            )[:maximum_results + 1]
        )
        developers = [
            {
                'id': developer.pk,
                'label': developer.get_display_name_with_company_group(),
            }
            for developer in developer_objects[:maximum_results]
        ]
        developers_truncated = len(developer_objects) > maximum_results

        complexes_queryset = RealEstateComplex.objects.none()
        if filters.get('districtId') and filters.get('developerId'):
            complexes_queryset = RealEstateComplex.objects.filter(
                district_id=filters['districtId'],
                developer_id=filters['developerId'],
            ).order_by('name', 'pk')
        real_estate_complexes, complexes_truncated = (
            _build_bounded_option_rows(
                complexes_queryset,
                maximum_results,
            )
        )

        buildings_queryset = RealEstateComplexBuilding.objects.none()
        if filters.get('realEstateComplexId'):
            buildings_queryset = RealEstateComplexBuilding.objects.filter(
                real_estate_complex_id=filters['realEstateComplexId']
            ).order_by('number', 'pk')
        building_objects = list(
            buildings_queryset[:maximum_results + 1]
        )
        buildings = [
            {'id': building.pk, 'number': building.number}
            for building in building_objects[:maximum_results]
        ]
        buildings_truncated = len(building_objects) > maximum_results

        layouts, layouts_truncated = _build_bounded_option_rows(
            ApartmentLayout.objects.order_by('name', 'pk'),
            maximum_results,
        )
        decorations, decorations_truncated = _build_bounded_option_rows(
            ApartmentDecoration.objects.order_by('name', 'pk'),
            maximum_results,
        )
        window_views, window_views_truncated = _build_bounded_option_rows(
            WindowView.objects.order_by('name', 'pk'),
            maximum_results,
        )

        return Response(
            {
                'regions': regions,
                'cities': cities,
                'districts': districts,
                'developers': developers,
                'realEstateComplexes': real_estate_complexes,
                'buildings': buildings,
                'layouts': layouts,
                'decorations': decorations,
                'windowViews': window_views,
                'truncated': {
                    'regions': regions_truncated,
                    'cities': cities_truncated,
                    'districts': districts_truncated,
                    'developers': developers_truncated,
                    'realEstateComplexes': complexes_truncated,
                    'buildings': buildings_truncated,
                    'layouts': layouts_truncated,
                    'decorations': decorations_truncated,
                    'windowViews': window_views_truncated,
                },
            }
        )


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
class CustomerDetailAPIView(RetrieveUpdateDestroyAPIView):
    """Return, update, or delete one owner-scoped customer."""

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


def _customer_calculation_link_configuration(program_type, user):
    """Return the link model and owner-scoped calculation queryset."""
    if program_type == 'market':
        return CustomerCalculation, _saved_mortgage_calculation_queryset(user)
    if program_type == 'trench':
        return (
            CustomerTrenchCalculation,
            _saved_trench_mortgage_calculation_queryset(user),
        )
    return None, None


@method_decorator(csrf_protect, name='dispatch')
class CustomerCalculationListCreateAPIView(APIView):
    """List and attach owner-scoped calculations for one customer."""

    permission_classes = (IsAuthenticated,)

    def get(self, request, pk):
        """Return a filtered and paginated union of linked calculations."""
        customer = get_object_or_404(
            _customer_queryset(request.user),
            pk=pk,
        )
        query_serializer = CustomerCalculationListQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        queryset = build_customer_calculation_queryset(
            customer,
            request.user,
            query_serializer.validated_data,
        )
        paginator = ApplicationPageNumberPagination()
        calculation_rows = paginator.paginate_queryset(
            queryset,
            request,
            view=self,
        )
        return paginator.get_paginated_response(
            [
                serialize_customer_calculation_link(row)
                for row in calculation_rows
            ]
        )

    def post(self, request, pk):
        """Attach a bounded set of accessible saved calculations."""
        customer = get_object_or_404(
            _customer_queryset(request.user),
            pk=pk,
        )
        request_serializer = CustomerCalculationLinkCreateSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)
        validated_data = request_serializer.validated_data
        program_type = validated_data['programType']
        calculation_identifiers = validated_data['calculationIds']
        link_model, calculation_queryset = (
            _customer_calculation_link_configuration(
                program_type,
                request.user,
            )
        )
        accessible_identifiers = set(
            calculation_queryset.filter(
                pk__in=calculation_identifiers
            ).values_list('pk', flat=True)
        )
        if len(accessible_identifiers) != len(calculation_identifiers):
            raise ValidationError(
                {
                    'calculationIds': [
                        'Один или несколько расчётов недоступны.'
                    ]
                }
            )
        existing_identifiers = set(
            link_model.objects.filter(
                customer=customer,
                calculation_id__in=accessible_identifiers,
            ).values_list('calculation_id', flat=True)
        )
        new_identifiers = accessible_identifiers - existing_identifiers
        with transaction.atomic():
            link_model.objects.bulk_create(
                [
                    link_model(
                        customer=customer,
                        calculation_id=calculation_identifier,
                    )
                    for calculation_identifier in new_identifiers
                ],
                ignore_conflicts=True,
            )
        return Response(
            {
                'createdCount': len(new_identifiers),
                'linkedCalculationIds': sorted(accessible_identifiers),
            },
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class CustomerCalculationLinkDetailAPIView(APIView):
    """Remove one calculation link while preserving the calculation."""

    permission_classes = (IsAuthenticated,)

    def delete(self, request, pk, program_type, link_pk):
        """Delete an owner-scoped customer link or return a safe 404."""
        customer = get_object_or_404(
            _customer_queryset(request.user),
            pk=pk,
        )
        link_model, _ = _customer_calculation_link_configuration(
            program_type,
            request.user,
        )
        if link_model is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        link_queryset = link_model.objects.filter(customer=customer)
        if not can_view_all_private_records(request.user):
            link_queryset = link_queryset.filter(
                calculation__user=request.user
            )
        calculation_link = get_object_or_404(link_queryset, pk=link_pk)
        calculation_link.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


@method_decorator(csrf_protect, name='dispatch')
class CustomerCalculationWordExportAPIView(APIView):
    """Export selected owner-scoped customer calculations to Word."""

    permission_classes = (IsAuthenticated,)

    def post(self, request, pk):
        """Return one established or one grouped Word report."""
        customer = get_object_or_404(
            _customer_queryset(request.user),
            pk=pk,
        )
        request_serializer = CustomerCalculationExportRequestSerializer(
            data=request.data
        )
        request_serializer.is_valid(raise_exception=True)
        selections = [
            (selection['programType'], selection['linkId'])
            for selection in request_serializer.validated_data['selections']
        ]
        selected_links = _get_selected_customer_calculation_links(
            customer,
            request.user,
            selections,
        )
        if len(selected_links) != len(selections):
            raise ValidationError(
                {
                    'selections': [
                        'Один или несколько расчётов недоступны.'
                    ]
                }
            )
        if len(selected_links) == 1:
            return _export_single_customer_word_calculation(
                selected_links[0]
            )
        return export_customer_mortgage_calculations_word(
            _build_customer_word_calculation(link)
            for link in selected_links
        )
