from django.http import JsonResponse


def health_check(request):
    """Return a lightweight success response for container health checks."""
    return JsonResponse({'status': 'ok'})
