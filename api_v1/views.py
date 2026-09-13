from django.conf import settings
from django.contrib.auth import login, logout
from django.db import transaction
from django.db.models import (
    Count,
    DecimalField,
    ExpressionWrapper,
    F,
    Min,
    Prefetch,
    Q,
    Window,
)
from django.db.models.deletion import ProtectedError
from django.db.models.functions import Lead
from django.middleware.csrf import get_token
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect, ensure_csrf_cookie
from rest_framework import status
from rest_framework.exceptions import NotFound, ValidationError
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
from rest_framework.parsers import MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from bank.developer_mortgage_program_importer import (
    DeveloperMortgageProgramImportError,
    import_developer_mortgage_programs,
)
from bank.forms import DeveloperMortgageProgramImportForm
from bank.key_rate_sync import KeyRateSyncError, sync_key_rates
from bank.models import (
    Bank,
    BankProgram,
    DeveloperMortgageProgram,
    KeyRate,
    MortgageProgram,
    MortgageProgramAlias,
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
from location.models import City, District, Metro, MetroLine, Region
from mortgage.excel import export_saved_mortgage_calculation_excel
from mortgage.models import MortgageCalculation
from mortgage.word import (
    export_customer_mortgage_calculations_word,
    export_saved_mortgage_calculation_word,
    export_trench_mortgage_word,
)
from property.forms import DeveloperRegistryImportForm
from property.models import (
    ApartmentDecoration,
    ApartmentLayout,
    CompanyGroup,
    Developer,
    Property,
    RealEstateClass,
    RealEstateComplex,
    RealEstateComplexBuilding,
    RealEstateComplexMetroAvailability,
    RealEstateType,
    TransportAccessibilityType,
    WindowView,
)
from property.services.developer_registry_importer import (
    DeveloperRegistryImportError,
)
from property.services.developer_registry_upload import (
    import_developer_registry_uploaded_file,
)
from trench_mortgage.models import TrenchMortgageCalculation
from trench_mortgage.views import _export_trench_excel
from users.forms import UserLoginForm, UserProfileForm, UserRegistrationForm
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
    BankDetailSerializer,
    BankListItemSerializer,
    BankListQuerySerializer,
    BankWriteSerializer,
    CompanyGroupListQuerySerializer,
    CompanyGroupSerializer,
    DeveloperListQuerySerializer,
    DeveloperPublicSerializer,
    DeveloperSerializer,
    DeveloperMortgageProgramListQuerySerializer,
    DeveloperMortgageProgramOptionsQuerySerializer,
    DeveloperMortgageProgramSerializer,
    DeveloperMortgageProgramWriteSerializer,
    CustomerDetailSerializer,
    CustomerCalculationExportRequestSerializer,
    CustomerCalculationLinkCreateSerializer,
    CustomerCalculationListQuerySerializer,
    CustomerFormOptionsQuerySerializer,
    CustomerListItemSerializer,
    CustomerListQuerySerializer,
    CustomerWriteSerializer,
    LoginRequestSerializer,
    LocationDictionaryEntrySerializer,
    LocationDictionaryListQuerySerializer,
    LocationDictionaryOptionsQuerySerializer,
    LocationDictionaryWriteSerializer,
    KeyRateListQuerySerializer,
    KeyRateSerializer,
    MortgageCalculationRequestSerializer,
    MortgageProgramDetailSerializer,
    MortgageProgramListItemSerializer,
    MortgageProgramListQuerySerializer,
    MortgageProgramWriteSerializer,
    PropertyDictionaryEntrySerializer,
    PropertyDictionaryListQuerySerializer,
    PropertyDictionaryWriteSerializer,
    RealEstateComplexDetailSerializer,
    RealEstateComplexListItemSerializer,
    RealEstateComplexListQuerySerializer,
    RealEstateComplexOptionsQuerySerializer,
    RealEstateComplexWriteSerializer,
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


class CanSyncExternalData(BasePermission):
    """Allow external synchronization only to application administrators."""

    def has_permission(self, request, view):
        """Return whether the current user may synchronize external data."""
        return can_sync_external_data(request.user)


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


ACCOUNT_FORM_FIELD_NAMES = {
    '__all__': 'nonFieldErrors',
    'first_name': 'firstName',
    'last_name': 'lastName',
    'email': 'email',
    'phone_number': 'phoneNumber',
    'is_real_estate_agent': 'isRealEstateAgent',
    'agency_name': 'agencyName',
    'password1': 'password1',
    'password2': 'password2',
}


def serialize_account_form_errors(account_form):
    """Return Django account form errors using the React field names."""
    return {
        ACCOUNT_FORM_FIELD_NAMES.get(field_name, field_name): [
            str(message) for message in messages
        ]
        for field_name, messages in account_form.errors.items()
    }


def build_account_form_data(request_data, include_passwords=False):
    """Whitelist and translate account fields from the JSON API payload."""
    form_data = {
        'first_name': request_data.get('firstName', ''),
        'last_name': request_data.get('lastName', ''),
        'email': request_data.get('email', ''),
        'phone_number': request_data.get('phoneNumber', ''),
        'is_real_estate_agent': request_data.get(
            'isRealEstateAgent',
            False,
        ),
        'agency_name': request_data.get('agencyName', ''),
    }
    if include_passwords:
        form_data.update(
            {
                'password1': request_data.get('password1', ''),
                'password2': request_data.get('password2', ''),
            }
        )
    return form_data


def build_profile_payload(user):
    """Return the editable profile fields for the current user."""
    return {
        'firstName': user.first_name,
        'lastName': user.last_name,
        'email': user.email,
        'phoneNumber': user.phone_number,
        'isRealEstateAgent': user.is_real_estate_agent,
        'agencyName': user.agency_name,
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


@method_decorator(csrf_protect, name='dispatch')
class RegistrationAPIView(APIView):
    """Create users through the established Django registration form."""

    permission_classes = (AllowAny,)

    def post(self, request):
        """Validate and create an account without starting a session."""
        if request.user.is_authenticated:
            return Response(
                {'detail': 'Вы уже вошли в приложение.'},
                status=status.HTTP_409_CONFLICT,
            )

        registration_form = UserRegistrationForm(
            data=build_account_form_data(
                request.data,
                include_passwords=True,
            )
        )
        if not registration_form.is_valid():
            return Response(
                {'errors': serialize_account_form_errors(registration_form)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        registration_form.save()
        return Response(
            {'registered': True},
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class ProfileAPIView(APIView):
    """Read and update only the authenticated user's profile."""

    permission_classes = (IsAuthenticated,)

    def get(self, request):
        """Return editable fields for the current user."""
        return Response(build_profile_payload(request.user))

    def patch(self, request):
        """Validate and save the current user's complete profile payload."""
        profile_form = UserProfileForm(
            data=build_account_form_data(request.data),
            instance=request.user,
        )
        if not profile_form.is_valid():
            return Response(
                {'errors': serialize_account_form_errors(profile_form)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        updated_user = profile_form.save()
        return Response(build_profile_payload(updated_user))


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


PROPERTY_DICTIONARY_CONFIGURATIONS = {
    'real-estate-types': {
        'model': RealEstateType,
        'legacy_key': 'real_estate_type',
        'has_weight': False,
        'usage_relation': 'realestatecomplex',
        'default_ordering': ('name', 'pk'),
    },
    'real-estate-classes': {
        'model': RealEstateClass,
        'legacy_key': 'real_estate_class',
        'has_weight': True,
        'usage_relation': 'realestatecomplex',
        'default_ordering': ('weight', 'name', 'pk'),
    },
    'apartment-layouts': {
        'model': ApartmentLayout,
        'legacy_key': 'apartment_layout',
        'has_weight': False,
        'usage_relation': 'property',
        'default_ordering': ('name', 'pk'),
    },
    'apartment-decorations': {
        'model': ApartmentDecoration,
        'legacy_key': 'apartment_decoration',
        'has_weight': False,
        'usage_relation': 'property',
        'default_ordering': ('name', 'pk'),
    },
    'window-views': {
        'model': WindowView,
        'legacy_key': 'window_view',
        'has_weight': False,
        'usage_relation': 'properties',
        'default_ordering': ('name', 'pk'),
    },
    'transport-accessibility-types': {
        'model': TransportAccessibilityType,
        'legacy_key': 'transport_accessibility_type',
        'has_weight': False,
        'usage_relation': 'realestatecomplexmetroavailability',
        'default_ordering': ('id',),
    },
}


class PropertyDictionaryAPIViewMixin:
    """Resolve and serialize only explicitly supported property dictionaries."""

    def get_dictionary_configuration(self):
        """Return the URL-selected whitelist entry or a safe 404 response."""
        dictionary_key = self.kwargs['dictionary_key']
        try:
            return PROPERTY_DICTIONARY_CONFIGURATIONS[dictionary_key]
        except KeyError as error:
            raise NotFound('Справочник не найден.') from error

    def get_base_queryset(self):
        """Return entries annotated with a dependency count for safe deletion."""
        configuration = self.get_dictionary_configuration()
        return configuration['model'].objects.annotate(
            usage_count=Count(
                configuration['usage_relation'],
                distinct=True,
            )
        )

    def get_serializer_context(self):
        """Expose the resolved whitelist entry to dictionary serializers."""
        context = super().get_serializer_context()
        context['dictionary_configuration'] = (
            self.get_dictionary_configuration()
        )
        return context

    def get_permissions(self):
        """Keep reads public and protect all shared dictionary mutations."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def get_serializer_class(self):
        """Use separate read and authoritative write contracts."""
        if self.request.method == 'GET':
            return PropertyDictionaryEntrySerializer
        return PropertyDictionaryWriteSerializer

    def get_response_serializer(self, dictionary_entry):
        """Serialize an annotated entry after a successful mutation."""
        refreshed_entry = self.get_base_queryset().get(pk=dictionary_entry.pk)
        return PropertyDictionaryEntrySerializer(
            refreshed_entry,
            context=self.get_serializer_context(),
        )


@method_decorator(csrf_protect, name='dispatch')
class PropertyDictionaryListCreateAPIView(
    PropertyDictionaryAPIViewMixin,
    ListCreateAPIView,
):
    """List a public property dictionary and allow moderator creation."""

    pagination_class = ApplicationPageNumberPagination
    ordering_fields = {
        'name': 'name',
        'updatedAt': 'updated_at',
        'status': 'is_active',
        'weight': 'weight',
    }

    def get_queryset(self):
        """Apply bounded search, status, pagination, and safe ordering."""
        query_serializer = PropertyDictionaryListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        configuration = self.get_dictionary_configuration()
        queryset = self.get_base_queryset()

        search = filters.get('q', '')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(description__icontains=search)
            )
        if filters['status'] != 'all':
            queryset = queryset.filter(
                is_active=filters['status'] == 'active'
            )

        ordering = filters['ordering']
        if ordering == 'default':
            return queryset.order_by(*configuration['default_ordering'])
        ordering_name = ordering.removeprefix('-')
        if ordering_name == 'weight' and not configuration['has_weight']:
            raise ValidationError(
                {'ordering': 'Сортировка по коэффициенту здесь недоступна.'}
            )
        ordering_prefix = '-' if ordering.startswith('-') else ''
        ordering_field = self.ordering_fields[ordering_name]
        return queryset.order_by(
            f'{ordering_prefix}{ordering_field}',
            'name',
            'pk',
        )

    def create(self, request, *args, **kwargs):
        """Create an entry and return its normalized public representation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dictionary_entry = serializer.save()
        response_serializer = self.get_response_serializer(dictionary_entry)
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class PropertyDictionaryDetailAPIView(
    PropertyDictionaryAPIViewMixin,
    RetrieveUpdateDestroyAPIView,
):
    """Retrieve a property dictionary entry and protect its mutations."""

    def get_queryset(self):
        """Return annotated entries from only the URL-selected dictionary."""
        return self.get_base_queryset()

    def update(self, request, *args, **kwargs):
        """Update an entry and return its normalized public representation."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        dictionary_entry = serializer.save()
        return Response(
            self.get_response_serializer(dictionary_entry).data
        )

    def destroy(self, request, *args, **kwargs):
        """Delete an unused entry or explain its protected dependency."""
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    'detail': (
                        'Запись нельзя удалить, пока она используется '
                        'в других разделах.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


LOCATION_DICTIONARY_CONFIGURATIONS = {
    'regions': {
        'key': 'regions',
        'model': Region,
        'legacy_key': 'region',
        'name_field': 'name',
        'parent_model_field': None,
        'select_related': (),
        'search_fields': ('name', 'code'),
        'filter_fields': {},
        'usage_relations': (
            'city',
            'developers',
            'developer_links',
            'mortgage_program_credit_limits',
        ),
        'default_ordering': ('name', 'pk'),
    },
    'cities': {
        'key': 'cities',
        'model': City,
        'legacy_key': 'city',
        'name_field': 'name',
        'parent_model_field': 'region',
        'select_related': ('region',),
        'search_fields': ('name', 'region__name'),
        'filter_fields': {'regionId': 'region_id'},
        'usage_relations': (
            'district',
            'metroline',
            'residence_customers',
            'desired_city_customers',
        ),
        'default_ordering': ('name', 'pk'),
    },
    'districts': {
        'key': 'districts',
        'model': District,
        'legacy_key': 'district',
        'name_field': 'name',
        'parent_model_field': 'city',
        'select_related': ('city__region',),
        'search_fields': ('name', 'city__name', 'city__region__name'),
        'filter_fields': {
            'regionId': 'city__region_id',
            'cityId': 'city_id',
        },
        'usage_relations': (
            'realestatecomplex',
            'desired_district_customers',
        ),
        'default_ordering': ('name', 'pk'),
    },
    'metro': {
        'key': 'metro',
        'model': Metro,
        'legacy_key': 'metro',
        'name_field': 'station',
        'parent_model_field': 'metro_line',
        'select_related': ('metro_line__city__region',),
        'search_fields': (
            'station',
            'metro_line__line',
            'metro_line__city__name',
        ),
        'filter_fields': {
            'regionId': 'metro_line__city__region_id',
            'cityId': 'metro_line__city_id',
            'metroLineId': 'metro_line_id',
        },
        'usage_relations': ('realestatecomplexmetroavailability',),
        'default_ordering': (
            'metro_line__city__name',
            'metro_line__line',
            'station',
            'pk',
        ),
    },
}


class LocationDictionaryAPIViewMixin:
    """Resolve and serialize only supported location dictionaries."""

    def get_dictionary_configuration(self):
        """Return the URL-selected whitelist entry or a safe 404 response."""
        dictionary_key = self.kwargs['dictionary_key']
        try:
            return LOCATION_DICTIONARY_CONFIGURATIONS[dictionary_key]
        except KeyError as error:
            raise NotFound('Справочник локаций не найден.') from error

    def get_base_queryset(self):
        """Return a relation-efficient queryset with dependency counts."""
        configuration = self.get_dictionary_configuration()
        queryset = configuration['model'].objects.all()
        if configuration['select_related']:
            queryset = queryset.select_related(
                *configuration['select_related']
            )

        usage_expression = None
        for relation_name in configuration['usage_relations']:
            relation_count = Count(relation_name, distinct=True)
            usage_expression = (
                relation_count
                if usage_expression is None
                else usage_expression + relation_count
            )
        return queryset.annotate(usage_count=usage_expression)

    def get_serializer_context(self):
        """Expose the resolved whitelist entry to location serializers."""
        context = super().get_serializer_context()
        context['dictionary_configuration'] = (
            self.get_dictionary_configuration()
        )
        return context

    def get_permissions(self):
        """Keep reads public and protect shared location mutations."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def get_serializer_class(self):
        """Use separate read and authoritative write contracts."""
        if self.request.method == 'GET':
            return LocationDictionaryEntrySerializer
        return LocationDictionaryWriteSerializer

    def get_response_serializer(self, dictionary_entry):
        """Serialize an annotated entry after a successful mutation."""
        refreshed_entry = self.get_base_queryset().get(pk=dictionary_entry.pk)
        return LocationDictionaryEntrySerializer(
            refreshed_entry,
            context=self.get_serializer_context(),
        )


@method_decorator(csrf_protect, name='dispatch')
class LocationDictionaryListCreateAPIView(
    LocationDictionaryAPIViewMixin,
    ListCreateAPIView,
):
    """List a public location dictionary and allow moderator creation."""

    pagination_class = ApplicationPageNumberPagination

    def get_queryset(self):
        """Apply bounded search, hierarchy filters, status, and ordering."""
        query_serializer = LocationDictionaryListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        configuration = self.get_dictionary_configuration()
        queryset = self.get_base_queryset()

        search = filters.get('q', '')
        if search:
            search_query = Q()
            for field_name in configuration['search_fields']:
                search_query |= Q(**{f'{field_name}__icontains': search})
            queryset = queryset.filter(search_query)
        if filters['status'] != 'all':
            queryset = queryset.filter(
                is_active=filters['status'] == 'active'
            )
        for api_field, model_field in configuration[
            'filter_fields'
        ].items():
            if filters.get(api_field):
                queryset = queryset.filter(
                    **{model_field: filters[api_field]}
                )

        ordering = filters['ordering']
        if ordering == 'default':
            return queryset.order_by(*configuration['default_ordering'])
        ordering_prefix = '-' if ordering.startswith('-') else ''
        ordering_name = ordering.removeprefix('-')
        ordering_field = {
            'name': configuration['name_field'],
            'updatedAt': 'updated_at',
            'status': 'is_active',
        }[ordering_name]
        return queryset.order_by(
            f'{ordering_prefix}{ordering_field}',
            configuration['name_field'],
            'pk',
        )

    def create(self, request, *args, **kwargs):
        """Create an entry and return its normalized public representation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dictionary_entry = serializer.save()
        return Response(
            self.get_response_serializer(dictionary_entry).data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class LocationDictionaryDetailAPIView(
    LocationDictionaryAPIViewMixin,
    RetrieveUpdateDestroyAPIView,
):
    """Retrieve a location entry and protect its mutations."""

    def get_queryset(self):
        """Return annotated entries from the URL-selected dictionary."""
        return self.get_base_queryset()

    def update(self, request, *args, **kwargs):
        """Update an entry and return its normalized public representation."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        dictionary_entry = serializer.save()
        return Response(
            self.get_response_serializer(dictionary_entry).data
        )

    def destroy(self, request, *args, **kwargs):
        """Delete an unused entry or explain its protected dependency."""
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    'detail': (
                        'Локацию нельзя удалить, пока она используется '
                        'в других разделах.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class LocationDictionaryOptionsAPIView(APIView):
    """Return bounded dependent selector options for location forms."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Return regions, region cities, and city metro lines."""
        query_serializer = LocationDictionaryOptionsQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        maximum_results = settings.PUBLIC_CATALOG_API_MAX_RESULTS

        regions, regions_truncated = _build_bounded_option_rows(
            Region.objects.order_by('name', 'pk'),
            maximum_results,
        )

        city_rows = []
        cities_truncated = False
        if filters.get('regionId'):
            cities = list(
                City.objects.filter(region_id=filters['regionId'])
                .order_by('name', 'pk')
                .values('id', 'name', 'region_id')[:maximum_results + 1]
            )
            cities_truncated = len(cities) > maximum_results
            city_rows = [
                {
                    'id': city['id'],
                    'name': city['name'],
                    'regionId': city['region_id'],
                }
                for city in cities[:maximum_results]
            ]

        metro_line_rows = []
        metro_lines_truncated = False
        if filters.get('cityId'):
            metro_lines = list(
                MetroLine.objects.filter(city_id=filters['cityId'])
                .order_by('line', 'pk')
                .values(
                    'id',
                    'line',
                    'line_color',
                    'city_id',
                )[:maximum_results + 1]
            )
            metro_lines_truncated = len(metro_lines) > maximum_results
            metro_line_rows = [
                {
                    'id': metro_line['id'],
                    'name': metro_line['line'],
                    'color': metro_line['line_color'],
                    'cityId': metro_line['city_id'],
                }
                for metro_line in metro_lines[:maximum_results]
            ]

        return Response(
            {
                'regions': regions,
                'cities': city_rows,
                'metroLines': metro_line_rows,
                'truncated': {
                    'regions': regions_truncated,
                    'cities': cities_truncated,
                    'metroLines': metro_lines_truncated,
                },
            }
        )


def _bank_list_queryset():
    """Return banks with aggregate program data for the public list."""
    return Bank.objects.annotate(
        program_count=Count('bankprogram', distinct=True),
        minimum_interest_rate=Min('bankprogram__interest_rate'),
    )


def _bank_detail_queryset():
    """Return banks with all program rows prefetched in display order."""
    programs = BankProgram.objects.select_related(
        'mortgage_program'
    ).order_by('mortgage_program__name', 'pk')
    return Bank.objects.prefetch_related(
        Prefetch(
            'bankprogram_set',
            queryset=programs,
            to_attr='api_programs',
        )
    )


class BankAPIViewMixin:
    """Share bank permissions and normalized mutation responses."""

    def get_permissions(self):
        """Keep bank reads public and protect shared catalog mutations."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def get_response_serializer(self, bank):
        """Serialize a refreshed bank after a successful mutation."""
        refreshed_bank = _bank_detail_queryset().get(pk=bank.pk)
        return BankDetailSerializer(
            refreshed_bank,
            context=self.get_serializer_context(),
        )


@method_decorator(csrf_protect, name='dispatch')
class BankListCreateAPIView(BankAPIViewMixin, ListCreateAPIView):
    """List public banks and allow moderators to create complete cards."""

    pagination_class = ApplicationPageNumberPagination

    def get_serializer_class(self):
        """Use compact list rows for reads and authoritative writes."""
        if self.request.method == 'GET':
            return BankListItemSerializer
        return BankWriteSerializer

    def get_queryset(self):
        """Apply bounded search, scope, status, and aggregate ordering."""
        query_serializer = BankListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        queryset = _bank_list_queryset()

        search = filters.get('q', '')
        if search:
            queryset = queryset.filter(name__icontains=search)
        if filters['scope'] == 'withPrograms':
            queryset = queryset.filter(program_count__gt=0)
        elif filters['scope'] == 'withoutPrograms':
            queryset = queryset.filter(program_count=0)
        if filters['status'] != 'all':
            queryset = queryset.filter(
                is_active=filters['status'] == 'active'
            )

        ordering = filters['ordering']
        ordering_prefix = '-' if ordering.startswith('-') else ''
        ordering_name = ordering.removeprefix('-')
        ordering_field = {
            'name': 'name',
            'minimumInterestRate': 'minimum_interest_rate',
            'updatedAt': 'updated_at',
        }[ordering_name]
        return queryset.order_by(
            f'{ordering_prefix}{ordering_field}',
            'name',
            'pk',
        )

    def create(self, request, *args, **kwargs):
        """Create a bank with programs and return the complete card."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        bank = serializer.save()
        return Response(
            self.get_response_serializer(bank).data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class BankDetailAPIView(BankAPIViewMixin, RetrieveUpdateDestroyAPIView):
    """Retrieve a public bank card and protect all mutations."""

    def get_serializer_class(self):
        """Use the detail contract for reads and write contract otherwise."""
        if self.request.method == 'GET':
            return BankDetailSerializer
        return BankWriteSerializer

    def get_queryset(self):
        """Return the relation-efficient bank detail queryset."""
        return _bank_detail_queryset()

    def update(self, request, *args, **kwargs):
        """Update a bank and return its complete normalized card."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        bank = serializer.save()
        return Response(self.get_response_serializer(bank).data)

    def destroy(self, request, *args, **kwargs):
        """Delete a bank or report protected developer-program links."""
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    'detail': (
                        'Банк нельзя удалить, пока он используется '
                        'в программах застройщиков.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class BankOptionsAPIView(APIView):
    """Return bounded canonical mortgage programs for bank forms."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Return mortgage programs with explicit truncation metadata."""
        maximum_results = settings.PUBLIC_CATALOG_API_MAX_RESULTS
        mortgage_programs, programs_truncated = _build_bounded_option_rows(
            MortgageProgram.objects.order_by('name', 'pk'),
            maximum_results,
        )
        return Response(
            {
                'mortgagePrograms': mortgage_programs,
                'truncated': programs_truncated,
            }
        )


def _mortgage_program_list_queryset():
    """Return canonical programs with aggregate relation usage counts."""
    return MortgageProgram.objects.annotate(
        bank_count=Count('banks', distinct=True),
        developer_program_count=Count(
            'developer_mortgage_programs',
            distinct=True,
        ),
        regional_limit_count=Count('regional_credit_limits', distinct=True),
        alias_count=Count('aliases', distinct=True),
    )


def _mortgage_program_detail_queryset():
    """Return canonical programs with bounded nested data prefetched."""
    regional_limits = MortgageProgramRegionalCreditLimit.objects.select_related(
        'region'
    ).order_by('region__name', 'pk')
    aliases = MortgageProgramAlias.objects.order_by('source_name', 'pk')
    return _mortgage_program_list_queryset().prefetch_related(
        Prefetch(
            'regional_credit_limits',
            queryset=regional_limits,
            to_attr='api_regional_credit_limits',
        ),
        Prefetch(
            'aliases',
            queryset=aliases,
            to_attr='api_aliases',
        ),
    )


class MortgageProgramAPIViewMixin:
    """Share canonical mortgage-program permissions and responses."""

    def get_permissions(self):
        """Keep reference reads public and protect shared catalog writes."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def get_response_serializer(self, mortgage_program):
        """Serialize a refreshed program after a successful mutation."""
        refreshed_program = _mortgage_program_detail_queryset().get(
            pk=mortgage_program.pk
        )
        return MortgageProgramDetailSerializer(
            refreshed_program,
            context=self.get_serializer_context(),
        )


@method_decorator(csrf_protect, name='dispatch')
class MortgageProgramListCreateAPIView(
    MortgageProgramAPIViewMixin,
    ListCreateAPIView,
):
    """List public canonical programs and allow moderator creation."""

    pagination_class = ApplicationPageNumberPagination

    def get_serializer_class(self):
        """Use compact rows for reads and the nested write contract."""
        if self.request.method == 'GET':
            return MortgageProgramListItemSerializer
        return MortgageProgramWriteSerializer

    def get_queryset(self):
        """Apply validated search, type, status, and ordering filters."""
        query_serializer = MortgageProgramListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        queryset = _mortgage_program_list_queryset()

        search = filters.get('q', '')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(condition__icontains=search)
                | Q(aliases__source_name__icontains=search)
            ).distinct()
        if filters['programType'] != 'all':
            queryset = queryset.filter(
                is_preferential=filters['programType'] == 'preferential'
            )
        if filters['status'] != 'all':
            queryset = queryset.filter(
                is_active=filters['status'] == 'active'
            )

        ordering = filters['ordering']
        ordering_prefix = '-' if ordering.startswith('-') else ''
        ordering_name = ordering.removeprefix('-')
        ordering_field = {
            'name': 'name',
            'creditLimit': 'credit_limit',
            'updatedAt': 'updated_at',
        }[ordering_name]
        return queryset.order_by(
            f'{ordering_prefix}{ordering_field}',
            'name',
            'pk',
        )

    def create(self, request, *args, **kwargs):
        """Create a complete program and return its normalized card."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        mortgage_program = serializer.save()
        return Response(
            self.get_response_serializer(mortgage_program).data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class MortgageProgramDetailAPIView(
    MortgageProgramAPIViewMixin,
    RetrieveUpdateDestroyAPIView,
):
    """Retrieve a canonical program and protect all mutations."""

    def get_serializer_class(self):
        """Use detail serialization for reads and validation for writes."""
        if self.request.method == 'GET':
            return MortgageProgramDetailSerializer
        return MortgageProgramWriteSerializer

    def get_queryset(self):
        """Return the relation-efficient canonical program queryset."""
        return _mortgage_program_detail_queryset()

    def update(self, request, *args, **kwargs):
        """Update a complete program and return its normalized card."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        mortgage_program = serializer.save()
        return Response(self.get_response_serializer(mortgage_program).data)

    def destroy(self, request, *args, **kwargs):
        """Delete unused programs or report protected financial links."""
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    'detail': (
                        'Ипотечную программу нельзя удалить, пока она '
                        'используется банком или программой застройщика.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class MortgageProgramOptionsAPIView(APIView):
    """Return bounded region choices for canonical program forms."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Return public region options with truncation metadata."""
        maximum_results = settings.PUBLIC_CATALOG_API_MAX_RESULTS
        regions, regions_truncated = _build_bounded_option_rows(
            Region.objects.order_by('name', 'pk'),
            maximum_results,
        )
        return Response(
            {
                'regions': regions,
                'truncated': regions_truncated,
            }
        )


def _developer_mortgage_program_queryset():
    """Return developer programs with all public references preloaded."""
    return DeveloperMortgageProgram.objects.select_related(
        'company_group',
        'real_estate_complex__developer',
        'bank',
        'mortgage_program',
    )


class DeveloperMortgageProgramAPIViewMixin:
    """Share public read and catalog-manager mutation behavior."""

    def get_permissions(self):
        """Allow public reads and require catalog permissions for writes."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def serialize_response(self, developer_program):
        """Return a refreshed, relation-complete program representation."""
        refreshed_program = _developer_mortgage_program_queryset().get(
            pk=developer_program.pk
        )
        return DeveloperMortgageProgramSerializer(
            refreshed_program,
            context=self.get_serializer_context(),
        )


@method_decorator(csrf_protect, name='dispatch')
class DeveloperMortgageProgramListCreateAPIView(
    DeveloperMortgageProgramAPIViewMixin,
    ListCreateAPIView,
):
    """List public developer programs and allow manager creation."""

    pagination_class = ApplicationPageNumberPagination

    def get_serializer_class(self):
        """Use the public contract for reads and validated fields for writes."""
        if self.request.method == 'GET':
            return DeveloperMortgageProgramSerializer
        return DeveloperMortgageProgramWriteSerializer

    def get_queryset(self):
        """Apply validated search, reference, status, and ordering filters."""
        query_serializer = DeveloperMortgageProgramListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        queryset = _developer_mortgage_program_queryset()

        search = filters.get('q', '')
        if search:
            queryset = queryset.filter(
                Q(company_group__name__icontains=search)
                | Q(real_estate_complex__name__icontains=search)
                | Q(real_estate_complex__developer__name__icontains=search)
                | Q(bank__name__icontains=search)
                | Q(mortgage_program__name__icontains=search)
            )
        reference_filters = {
            'companyGroupId': 'company_group_id',
            'realEstateComplexId': 'real_estate_complex_id',
            'bankId': 'bank_id',
            'mortgageProgramId': 'mortgage_program_id',
        }
        for query_name, model_field in reference_filters.items():
            if filters.get(query_name):
                queryset = queryset.filter(
                    **{model_field: filters[query_name]}
                )
        if filters['status'] != 'all':
            queryset = queryset.filter(
                is_active=filters['status'] == 'active'
            )

        ordering = filters['ordering']
        ordering_prefix = '-' if ordering.startswith('-') else ''
        ordering_name = ordering.removeprefix('-')
        ordering_field = {
            'companyGroup': 'company_group__name',
            'realEstateComplex': 'real_estate_complex__name',
            'bank': 'bank__name',
            'mortgageProgram': 'mortgage_program__name',
            'interestRate': 'interest_rate',
            'updatedAt': 'updated_at',
        }[ordering_name]
        return queryset.order_by(
            f'{ordering_prefix}{ordering_field}',
            'company_group__name',
            'pk',
        )

    def create(self, request, *args, **kwargs):
        """Create one developer program and return its public card."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        developer_program = serializer.save()
        return Response(
            self.serialize_response(developer_program).data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class DeveloperMortgageProgramDetailAPIView(
    DeveloperMortgageProgramAPIViewMixin,
    RetrieveUpdateDestroyAPIView,
):
    """Retrieve public conditions and protect program mutations."""

    queryset = _developer_mortgage_program_queryset()

    def get_serializer_class(self):
        """Use separate read and write contracts."""
        if self.request.method == 'GET':
            return DeveloperMortgageProgramSerializer
        return DeveloperMortgageProgramWriteSerializer

    def update(self, request, *args, **kwargs):
        """Update editable conditions and return the refreshed card."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        developer_program = serializer.save()
        return Response(self.serialize_response(developer_program).data)


class DeveloperMortgageProgramOptionsAPIView(APIView):
    """Return bounded public choices for filters and manager forms."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Return primary choices and group-scoped residential complexes."""
        query_serializer = DeveloperMortgageProgramOptionsQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        company_group_id = query_serializer.validated_data.get(
            'companyGroupId'
        )
        maximum_results = settings.PUBLIC_CATALOG_API_MAX_RESULTS
        company_groups, company_groups_truncated = _build_bounded_option_rows(
            CompanyGroup.objects.order_by('name', 'pk'),
            maximum_results,
        )
        banks, banks_truncated = _build_bounded_option_rows(
            Bank.objects.order_by('name', 'pk'),
            maximum_results,
        )
        mortgage_programs, mortgage_programs_truncated = (
            _build_bounded_option_rows(
                MortgageProgram.objects.order_by('name', 'pk'),
                maximum_results,
            )
        )

        complex_objects = []
        if company_group_id:
            complex_objects = list(
                RealEstateComplex.objects.select_related('developer')
                .filter(developer__company_group_id=company_group_id)
                .order_by('name', 'developer__name', 'pk')
                [:maximum_results + 1]
            )
        real_estate_complexes = [
            {
                'id': real_estate_complex.pk,
                'name': (
                    f'{real_estate_complex.name} '
                    f'({real_estate_complex.developer.name})'
                ),
            }
            for real_estate_complex in complex_objects[:maximum_results]
        ]
        complexes_truncated = len(complex_objects) > maximum_results

        return Response(
            {
                'companyGroups': company_groups,
                'realEstateComplexes': real_estate_complexes,
                'banks': banks,
                'mortgagePrograms': mortgage_programs,
                'truncated': {
                    'companyGroups': company_groups_truncated,
                    'realEstateComplexes': complexes_truncated,
                    'banks': banks_truncated,
                    'mortgagePrograms': mortgage_programs_truncated,
                },
            }
        )


def _serialize_developer_program_import_result(import_result):
    """Return a stable camel-case summary for one completed import."""
    return {
        'totalRows': import_result.total_rows,
        'parsedRows': import_result.parsed_rows,
        'created': import_result.created,
        'updated': import_result.updated,
        'unchanged': import_result.unchanged,
        'skipped': import_result.skipped,
        'duplicateRows': import_result.duplicate_rows,
        'sourceWarningRows': import_result.source_warning_rows,
        'inactiveRows': import_result.inactive_rows,
        'issueMessages': list(import_result.issue_messages),
    }


@method_decorator(csrf_protect, name='dispatch')
class DeveloperMortgageProgramImportAPIView(APIView):
    """Import normalized developer programs from an uploaded XLSX file."""

    permission_classes = (IsAuthenticated, CanManageCatalogs)
    parser_classes = (MultiPartParser,)

    def post(self, request):
        """Validate the upload and return the transactional import summary."""
        import_form = DeveloperMortgageProgramImportForm(
            data=request.data,
            files=request.FILES,
        )
        if not import_form.is_valid():
            return Response(
                {
                    'workbookFile': [
                        str(error)
                        for error in import_form.errors.get(
                            'workbook_file',
                            (),
                        )
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            import_result = import_developer_mortgage_programs(
                import_form.cleaned_data['workbook_file']
            )
        except DeveloperMortgageProgramImportError as error:
            return Response(
                {'detail': str(error)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            _serialize_developer_program_import_result(import_result)
        )


def _build_current_key_rate_payload():
    """Return the latest active key rate used by financial calculations."""
    current_key_rate = (
        KeyRate.objects.filter(is_active=True)
        .order_by('-meeting_date', '-pk')
        .first()
    )
    if current_key_rate is None:
        return None
    return {
        'meetingDate': current_key_rate.meeting_date,
        'keyRate': str(current_key_rate.key_rate),
    }


class KeyRateListAPIView(ListAPIView):
    """Return the public, paginated Central Bank key-rate history."""

    serializer_class = KeyRateSerializer
    pagination_class = ApplicationPageNumberPagination
    permission_classes = (AllowAny,)

    def get_queryset(self):
        """Validate pagination and annotate chronological rate changes."""
        query_serializer = KeyRateListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        return (
            KeyRate.objects.annotate(
                previous_rate=Window(
                    expression=Lead('key_rate'),
                    order_by=F('meeting_date').desc(),
                ),
            )
            .annotate(
                rate_change=ExpressionWrapper(
                    F('key_rate') - F('previous_rate'),
                    output_field=DecimalField(
                        max_digits=5,
                        decimal_places=2,
                    ),
                ),
            )
            .order_by('-meeting_date', '-pk')
        )

    def list(self, request, *args, **kwargs):
        """Add current-rate and source freshness metadata to the page."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        serializer = self.get_serializer(page, many=True)
        response = self.get_paginated_response(serializer.data)
        response.data.update(
            {
                'currentRate': _build_current_key_rate_payload(),
                'lastSyncedAt': (
                    KeyRate.objects.order_by('-updated_at')
                    .values_list('updated_at', flat=True)
                    .first()
                ),
                'legacyUrl': '/bank/key-rate/',
            }
        )
        return response


@method_decorator(csrf_protect, name='dispatch')
class KeyRateSyncAPIView(APIView):
    """Synchronize key-rate history with the Central Bank source."""

    permission_classes = (IsAuthenticated, CanSyncExternalData)

    def post(self, request):
        """Run synchronization and return a compact operation summary."""
        try:
            result = sync_key_rates()
        except KeyRateSyncError as error:
            return Response(
                {
                    'detail': (
                        'Не удалось обновить данные ключевой ставки: '
                        f'{error}'
                    )
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )
        return Response(
            {
                'created': result['created'],
                'updated': result['updated'],
                'processed': result['processed'],
                'currentRate': _build_current_key_rate_payload(),
                'synchronizedAt': timezone.now(),
            }
        )


def _developer_queryset():
    """Return developers with all data needed by their API representation."""
    return (
        Developer.objects.select_related('company_group')
        .prefetch_related('regions')
        .annotate(
            complex_count=Count('realestatecomplex', distinct=True)
        )
    )


def _serialize_developer_registry_import_summary(import_summary):
    """Return a stable camel-case summary for a developer registry import."""
    return {
        'sourceRecords': import_summary.source_records,
        'normalizedRecords': import_summary.normalized_records,
        'createdDevelopers': import_summary.created_developers,
        'updatedDevelopers': import_summary.updated_developers,
        'unchangedDevelopers': import_summary.unchanged_developers,
        'createdCompanyGroups': import_summary.created_company_groups,
        'createdDeveloperRegionLinks': (
            import_summary.created_developer_region_links
        ),
        'skippedRecords': import_summary.skipped_records,
        'errors': list(import_summary.errors),
        'dryRun': import_summary.dry_run,
    }


@method_decorator(csrf_protect, name='dispatch')
class DeveloperRegistryImportAPIView(APIView):
    """Import developers from an uploaded ERZ registry source file."""

    permission_classes = (IsAuthenticated, CanSyncExternalData)
    parser_classes = (MultiPartParser,)

    def post(self, request):
        """Validate a registry upload and return its import summary."""
        import_form = DeveloperRegistryImportForm(
            data=request.data,
            files=request.FILES,
        )
        if not import_form.is_valid():
            return Response(
                {
                    'sourceFile': [
                        str(error)
                        for error in import_form.errors.get('source_file', ())
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            import_summary = import_developer_registry_uploaded_file(
                import_form.cleaned_data['source_file']
            )
        except DeveloperRegistryImportError as exception:
            return Response(
                {'detail': str(exception)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return Response(
            _serialize_developer_registry_import_summary(import_summary)
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


def _real_estate_complex_list_queryset():
    """Return complexes with list labels and building counts preloaded."""
    return RealEstateComplex.objects.select_related(
        'developer__company_group',
        'district__city',
        'real_estate_class',
        'real_estate_type',
    ).annotate(
        building_count=Count('realestatecomplexbuilding', distinct=True)
    )


def _real_estate_complex_detail_queryset():
    """Return the query-efficient residential-complex detail queryset."""
    buildings = RealEstateComplexBuilding.objects.annotate(
        property_count=Count('property', distinct=True)
    ).order_by('number', 'pk')
    metro_availability = (
        RealEstateComplexMetroAvailability.objects.select_related(
            'metro__metro_line__city',
            'transport_accessibility_type',
        ).order_by('walking_time_minutes', 'metro__station', 'pk')
    )
    return RealEstateComplex.objects.select_related(
        'developer__company_group',
        'district__city__region',
        'real_estate_class',
        'real_estate_type',
    ).prefetch_related(
        Prefetch(
            'realestatecomplexbuilding_set',
            queryset=buildings,
            to_attr='api_buildings',
        ),
        Prefetch(
            'metro_availability',
            queryset=metro_availability,
            to_attr='api_metro_availability',
        ),
    )


@method_decorator(csrf_protect, name='dispatch')
class RealEstateComplexListCreateAPIView(ListCreateAPIView):
    """List public complexes and let catalog managers create them."""

    pagination_class = ApplicationPageNumberPagination
    ordering_fields = {
        'name': 'name',
        'developer': 'developer__name',
        'city': 'district__city__name',
        'realEstateClass': 'real_estate_class__name',
        'realEstateType': 'real_estate_type__name',
        'buildingCount': 'building_count',
    }

    def get_permissions(self):
        """Keep directory reads public and protect complex creation."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def get_serializer_class(self):
        """Use distinct public read and catalog-manager write contracts."""
        if self.request.method == 'GET':
            return RealEstateComplexListItemSerializer
        return RealEstateComplexWriteSerializer

    def get_queryset(self):
        """Apply validated URL filters and deterministic ordering."""
        query_serializer = RealEstateComplexListQuerySerializer(
            data=self.request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        queryset = _real_estate_complex_list_queryset()

        search = filters.get('search', '')
        if search:
            queryset = queryset.filter(
                Q(name__icontains=search)
                | Q(developer__name__icontains=search)
                | Q(district__city__name__icontains=search)
            )
        filter_fields = {
            'developerId': 'developer_id',
            'cityId': 'district__city_id',
            'realEstateClassId': 'real_estate_class_id',
            'realEstateTypeId': 'real_estate_type_id',
            'buildingCount': 'building_count',
        }
        for query_name, model_field in filter_fields.items():
            value = filters.get(query_name)
            if value is not None:
                queryset = queryset.filter(**{model_field: value})
        if filters['status'] != 'all':
            queryset = queryset.filter(
                is_active=filters['status'] == 'active'
            )

        ordering = filters['ordering']
        ordering_prefix = '-' if ordering.startswith('-') else ''
        ordering_field = self.ordering_fields[ordering.removeprefix('-')]
        return queryset.order_by(
            f'{ordering_prefix}{ordering_field}', 'name', 'pk'
        )

    def create(self, request, *args, **kwargs):
        """Create a complex and return its complete public representation."""
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        real_estate_complex = serializer.save()
        real_estate_complex = _real_estate_complex_detail_queryset().get(
            pk=real_estate_complex.pk
        )
        response_serializer = RealEstateComplexDetailSerializer(
            real_estate_complex,
            context=self.get_serializer_context(),
        )
        return Response(
            response_serializer.data,
            status=status.HTTP_201_CREATED,
        )


@method_decorator(csrf_protect, name='dispatch')
class RealEstateComplexDetailAPIView(RetrieveUpdateDestroyAPIView):
    """Read a complex publicly and protect catalog-manager mutations."""

    queryset = _real_estate_complex_detail_queryset()

    def get_permissions(self):
        """Keep detail reads public and protect update and delete."""
        if self.request.method == 'GET':
            return (AllowAny(),)
        return (IsAuthenticated(), CanManageCatalogs())

    def get_serializer_class(self):
        """Use distinct public read and catalog-manager write contracts."""
        if self.request.method == 'GET':
            return RealEstateComplexDetailSerializer
        return RealEstateComplexWriteSerializer

    def update(self, request, *args, **kwargs):
        """Update a complex and return its refreshed public card."""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)
        real_estate_complex = serializer.save()
        real_estate_complex = _real_estate_complex_detail_queryset().get(
            pk=real_estate_complex.pk
        )
        response_serializer = RealEstateComplexDetailSerializer(
            real_estate_complex,
            context=self.get_serializer_context(),
        )
        return Response(response_serializer.data)

    def destroy(self, request, *args, **kwargs):
        """Delete an unused complex or explain its protected dependency."""
        instance = self.get_object()
        try:
            instance.delete()
        except ProtectedError:
            return Response(
                {
                    'detail': (
                        'ЖК нельзя удалить, пока с его корпусами связаны '
                        'объекты недвижимости.'
                    )
                },
                status=status.HTTP_409_CONFLICT,
            )
        return Response(status=status.HTTP_204_NO_CONTENT)


class RealEstateComplexOptionsAPIView(APIView):
    """Return bounded choices for complex filters and manager forms."""

    permission_classes = (AllowAny,)

    def get(self, request):
        """Return safe choices restricted by selected location parents."""
        query_serializer = RealEstateComplexOptionsQuerySerializer(
            data=request.query_params
        )
        query_serializer.is_valid(raise_exception=True)
        filters = query_serializer.validated_data
        maximum_results = settings.PUBLIC_CATALOG_API_MAX_RESULTS

        regions, regions_truncated = _build_bounded_option_rows(
            Region.objects.order_by('name', 'pk'), maximum_results
        )
        cities_queryset = City.objects.order_by('name', 'pk')
        if filters.get('regionId'):
            cities_queryset = cities_queryset.filter(
                region_id=filters['regionId']
            )
        cities, cities_truncated = _build_bounded_option_rows(
            cities_queryset, maximum_results
        )
        districts_queryset = District.objects.none()
        if filters.get('cityId'):
            districts_queryset = District.objects.filter(
                city_id=filters['cityId']
            ).order_by('name', 'pk')
        districts, districts_truncated = _build_bounded_option_rows(
            districts_queryset, maximum_results
        )

        developer_objects = list(
            Developer.objects.select_related('company_group').order_by(
                'name', 'pk'
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
        real_estate_classes, classes_truncated = _build_bounded_option_rows(
            RealEstateClass.objects.order_by('weight', 'name', 'pk'),
            maximum_results,
        )
        real_estate_types, types_truncated = _build_bounded_option_rows(
            RealEstateType.objects.order_by('name', 'pk'), maximum_results
        )
        accessibility_types, accessibility_types_truncated = (
            _build_bounded_option_rows(
                TransportAccessibilityType.objects.order_by('id'),
                maximum_results,
            )
        )

        metro_stations = []
        metro_stations_truncated = False
        if filters.get('cityId'):
            metro_objects = list(
                Metro.objects.select_related('metro_line').filter(
                    metro_line__city_id=filters['cityId']
                ).order_by('metro_line__line', 'station', 'pk')
                [:maximum_results + 1]
            )
            metro_stations = [
                {
                    'id': metro.pk,
                    'station': metro.station,
                    'line': metro.metro_line.line,
                    'lineColor': metro.metro_line.line_color,
                }
                for metro in metro_objects[:maximum_results]
            ]
            metro_stations_truncated = len(metro_objects) > maximum_results

        return Response(
            {
                'regions': regions,
                'cities': cities,
                'districts': districts,
                'developers': developers,
                'realEstateClasses': real_estate_classes,
                'realEstateTypes': real_estate_types,
                'transportAccessibilityTypes': accessibility_types,
                'metroStations': metro_stations,
                'quarters': [
                    {'value': value, 'label': label}
                    for value, label
                    in RealEstateComplexBuilding.Quarter.choices
                ],
                'truncated': {
                    'regions': regions_truncated,
                    'cities': cities_truncated,
                    'districts': districts_truncated,
                    'developers': developers_truncated,
                    'realEstateClasses': classes_truncated,
                    'realEstateTypes': types_truncated,
                    'transportAccessibilityTypes': (
                        accessibility_types_truncated
                    ),
                    'metroStations': metro_stations_truncated,
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
