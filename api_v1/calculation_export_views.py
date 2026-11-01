from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from mortgage.excel import export_mortgage_excel
from mortgage.word import export_mortgage_word, export_trench_mortgage_word
from trench_mortgage.views import _export_trench_excel

from .calculation_property_service import build_unsaved_property
from .mortgage_service import build_market_mortgage_export_data
from .serializers import (
    MortgageCalculationExportSerializer,
    TrenchMortgageCalculationExportSerializer,
)
from .trench_mortgage_service import (
    TrenchMortgageValidationError, calculate_trench_mortgage,
)


@method_decorator(csrf_protect, name='dispatch')
class UnsavedCalculationExportAPIView(APIView):
    """Export a validated scenario without any catalog or history writes."""

    permission_classes = (AllowAny,)

    def post(self, request, calculation_type, export_format):
        """Generate an established Excel/Word report from current inputs."""
        serializer_class = (
            TrenchMortgageCalculationExportSerializer
            if calculation_type == 'trench'
            else MortgageCalculationExportSerializer
        )
        serializer = serializer_class(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        parameters = data['parameters']
        property_object = (
            data.get('property') or build_unsaved_property(parameters)
        )
        if calculation_type == 'trench':
            try:
                calculation, _ = calculate_trench_mortgage(
                    parameters, property_object
                )
            except TrenchMortgageValidationError as error:
                return Response(
                    {'nonFieldErrors': list(error.messages)}, status=400
                )
            if export_format == 'word':
                return export_trench_mortgage_word(calculation)
            return _export_trench_excel(calculation)
        report = build_market_mortgage_export_data(parameters, property_object)
        if export_format == 'word':
            return export_mortgage_word(report)
        return export_mortgage_excel(report)
