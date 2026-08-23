from rest_framework.views import exception_handler


def api_exception_handler(exc, context):
    """Return consistent API errors with a request correlation identifier."""
    response = exception_handler(exc, context)
    if response is None:
        return response

    request = context.get('request')
    request_id = getattr(request, 'request_id', None)
    if isinstance(response.data, dict):
        response.data.setdefault('request_id', request_id)
    else:
        response.data = {'detail': response.data, 'request_id': request_id}
    return response
