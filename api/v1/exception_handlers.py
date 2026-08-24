import logging

from django.http import JsonResponse
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def api_exception_handler(exc, context):
    """Return consistent API errors with a request correlation identifier."""
    response = exception_handler(exc, context)
    request = context.get('request')
    request_id = getattr(request, 'request_id', None)

    if response is None:
        # Non-DRF exceptions (KeyError, IntegrityError, ...) would otherwise
        # surface as an HTML 500 page with no correlation id. Log with the
        # request id and return a consistent JSON 500 instead.
        logger.exception('Unhandled API exception request_id=%s path=%s', request_id, getattr(request, 'path', '?'))
        return JsonResponse({'detail': 'Internal server error.', 'request_id': request_id}, status=500)

    if isinstance(response.data, dict):
        response.data.setdefault('request_id', request_id)
    else:
        response.data = {'detail': response.data, 'request_id': request_id}
    return response
