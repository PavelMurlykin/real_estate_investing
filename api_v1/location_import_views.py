"""Administrator endpoints for durable national location imports."""

from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect
from rest_framework import status
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from location.jobs import serialize_import_job, start_import_job
from location.models import LocationImportJob

from .views import CanSyncExternalData


@method_decorator(never_cache, name='dispatch')
@method_decorator(csrf_protect, name='dispatch')
class LocationImportJobAPIView(APIView):
    """Start, resume and inspect one national import with the same role rules."""

    permission_classes = (IsAuthenticated, CanSyncExternalData)

    def get(self, request):
        """Return durable progress after navigation or browser reload."""
        return Response({'job': serialize_import_job(LocationImportJob.objects.first())})

    def post(self, request):
        """Queue or resume the Russian catalog without client-controlled sources."""
        if not isinstance(request.data, dict) or request.data:
            raise ValidationError({'detail': 'Для импорта всей России параметры не нужны.'})
        return Response(
            {'job': serialize_import_job(start_import_job())},
            status=status.HTTP_202_ACCEPTED,
        )
