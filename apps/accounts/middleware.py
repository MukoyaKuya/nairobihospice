from django.conf import settings
from django.shortcuts import redirect

from .mfa import privileged_user_requires_mfa


class PrivilegedMfaEnforcementMiddleware:
    """
    Ensures privileged accounts (Superusers, System Administrators, Program/Operations Managers)
    must complete MFA before accessing protected application endpoints.
    Fails closed if the session lacks verified MFA credentials.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if not getattr(settings, 'MFA_ENFORCEMENT_MIDDLEWARE_ENABLED', True):
            return self.get_response(request)

        user = getattr(request, 'user', None)
        if user and user.is_authenticated and privileged_user_requires_mfa(user):
            is_mfa_verified = (
                request.session.get('mfa_verified') is True
                and str(request.session.get('mfa_verified_user_id')) == str(user.pk)
            )
            if not is_mfa_verified:
                path = request.path
                exempt_prefixes = [
                    '/accounts/logout/',
                    '/accounts/mfa/enroll/',
                    '/accounts/mfa/verify/',
                    '/static/',
                    '/media/',
                ]
                if not any(path.startswith(prefix) for prefix in exempt_prefixes):
                    request.session['mfa_pending_user_id'] = str(user.pk)
                    if user.is_mfa_enabled and user.mfa_secret:
                        return redirect('accounts:mfa_verify')
                    else:
                        return redirect('accounts:mfa_enroll')

        return self.get_response(request)
