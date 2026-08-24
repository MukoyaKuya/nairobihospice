from django.conf import settings

from .middleware import get_current_request
from .models import AuditAction, AuditEvent


def get_client_ip(request):
    if not request:
        return None
    if getattr(settings, 'TRUST_PROXY_HEADERS', False):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            # Use the rightmost entry: it was appended by our own trusted
            # reverse proxy. Leftmost values are client-controlled and spoofable.
            return x_forwarded_for.split(',')[-1].strip()
    return request.META.get('REMOTE_ADDR')


def log_audit_event(*, action: AuditAction, resource_type: str, resource_id: str = '', summary: str, user=None, metadata: dict = None, request=None) -> AuditEvent:
    """
    Records an immutable audit event for security monitoring and clinical record compliance.
    """
    req = request or get_current_request()

    current_user = user
    if current_user is None and req and hasattr(req, 'user') and req.user.is_authenticated:
        current_user = req.user

    user_email = ''
    user_role = ''
    if current_user and getattr(current_user, 'is_authenticated', False):
        user_email = getattr(current_user, 'email', '')
        user_role = getattr(current_user, 'role', '') or ''

    ip_address = get_client_ip(req)
    user_agent = req.META.get('HTTP_USER_AGENT', '') if req else ''

    return AuditEvent.objects.create(
        user=current_user if (current_user and getattr(current_user, 'is_authenticated', False)) else None,
        user_email=user_email,
        user_role=user_role,
        action=action,
        resource_type=resource_type,
        resource_id=str(resource_id),
        summary=summary,
        ip_address=ip_address,
        user_agent=user_agent[:500] if user_agent else '',
        metadata=metadata or {},
    )
