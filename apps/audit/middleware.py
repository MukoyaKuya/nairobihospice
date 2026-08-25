import logging
import threading
import uuid

from django.conf import settings

_thread_locals = threading.local()
logger = logging.getLogger(__name__)


def get_current_request():
    return getattr(_thread_locals, 'request', None)


class AuditMiddleware:
    """
    Middleware that captures the current HTTP request in thread-local storage
    for downstream audit logging and context enrichment.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        import base64
        import os
        request.request_id = uuid.uuid4().hex
        request.csp_nonce = base64.b64encode(os.urandom(16)).decode('ascii')
        _thread_locals.request = request
        try:
            response = self.get_response(request)
            response['X-Request-ID'] = request.request_id
            content_security_policy = getattr(settings, 'CONTENT_SECURITY_POLICY', None)
            if content_security_policy:
                if '{csp_nonce}' in content_security_policy:
                    response['Content-Security-Policy'] = content_security_policy.format(csp_nonce=request.csp_nonce)
                else:
                    response['Content-Security-Policy'] = content_security_policy
            if response.status_code == 429:
                logger.warning(
                    'Rate limit response path=%s method=%s user=%s',
                    request.path,
                    request.method,
                    getattr(request.user, 'email', 'anonymous'),
                )
            return response
        finally:
            _thread_locals.request = None


class BrandedErrorMiddleware:
    """
    Ensures that 404 Not Found errors always render the custom branded 404 page
    and never expose internal URL routes, endpoints, or file structures.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.http import Http404
        from django.views.defaults import page_not_found

        response = self.get_response(request)
        if response.status_code == 404:
            if not request.path.startswith('/api/'):
                content = getattr(response, 'content', b'')
                if b'Page Not Found | Nairobi Hospice PCMS' not in content:
                    return page_not_found(request, exception=Http404("Page not found"))
        return response

    def process_exception(self, request, exception):
        from django.http import Http404
        from django.views.defaults import page_not_found

        if isinstance(exception, Http404):
            return page_not_found(request, exception=exception)
        return None


class HtmxAuthRedirectMiddleware:
    """
    Prevents HTMX from swapping the entire Login Page HTML into small partials/widgets
    (like the notification bell) when a session expires or an unauthenticated HTMX request occurs.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        is_htmx = request.headers.get('HX-Request') == 'true' or getattr(request, 'htmx', False)
        if is_htmx:
            if response.status_code in [301, 302] and '/accounts/login/' in response.get('Location', ''):
                from django.http import HttpResponse
                htmx_response = HttpResponse(status=204)
                htmx_response['HX-Redirect'] = response['Location']
                return htmx_response
            elif response.status_code in [401, 403] and not request.user.is_authenticated:
                from django.http import HttpResponse
                htmx_response = HttpResponse(status=204)
                htmx_response['HX-Redirect'] = '/accounts/login/'
                return htmx_response
        return response
