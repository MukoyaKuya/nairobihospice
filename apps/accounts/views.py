from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import (
    LoginView as DjangoLoginView,
)
from django.contrib.auth.views import (
    PasswordResetCompleteView,
    PasswordResetConfirmView,
    PasswordResetDoneView,
    PasswordResetView,
)
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import ListView

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event

from .forms import LoginForm, MFAEnrollmentForm, MFAVerifyForm, ProfileUpdateForm
from .mfa import (
    consume_recovery_code,
    generate_recovery_codes,
    generate_secret,
    privileged_user_requires_mfa,
    provisioning_uri,
    verify_totp,
    verify_totp_for_user,
)
from .models import StaffProfile, User
from .permissions import ManagerRequiredMixin
from .security import (
    clear_login_attempts,
    clear_mfa_attempts,
    is_login_rate_limited,
    is_mfa_rate_limited,
    record_failed_login,
    record_failed_mfa,
)


def _role_redirect(user):
    if user.is_administrator or user.is_superuser:
        return 'admin:index'
    if user.is_manager:
        return 'reporting:management_dashboard'
    return 'reporting:clinical_dashboard'


def _abort_mfa_to_login(request, message):
    """Too many failed challenges: drop the pending-MFA session and force a full re-auth."""
    for key in ['mfa_pending_user_id', 'mfa_next_url', 'mfa_enrollment_secret', 'mfa_recovery_codes_plain', 'mfa_recovery_codes_hashes']:
        request.session.pop(key, None)
    messages.error(request, message)
    return redirect('accounts:login')


def _pending_mfa_user(request):
    if request.user.is_authenticated:
        return request.user
    user_id = request.session.get('mfa_pending_user_id')
    if not user_id:
        return None
    return get_object_or_404(User, pk=user_id, is_active=True)


def _complete_mfa_login(request, user):
    if not request.user.is_authenticated:
        login(request, user)
    for key in ['mfa_pending_user_id', 'mfa_next_url', 'mfa_enrollment_secret', 'mfa_recovery_codes_plain']:
        request.session.pop(key, None)
    log_audit_event(
        action=AuditAction.LOGIN,
        resource_type='Authentication',
        resource_id=str(user.pk),
        summary=f'Successful MFA sign-in for {user.email}',
        user=user,
        request=request,
    )
    return redirect(_role_redirect(user))


class PCMSLoginView(DjangoLoginView):
    template_name = 'landing.html'
    form_class = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return reverse_lazy(_role_redirect(self.request.user))

    def dispatch(self, request, *args, **kwargs):
        if request.method == 'POST' and is_login_rate_limited(request):
            form = self.get_form()
            form.add_error(None, 'Too many failed sign-in attempts. Try again in 15 minutes.')
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().dispatch(request, *args, **kwargs)

    def form_invalid(self, form):
        attempts = record_failed_login(self.request)
        log_audit_event(
            action=AuditAction.LOGIN,
            resource_type='Authentication',
            summary='Failed sign-in attempt',
            metadata={'attempts_in_window': attempts},
            request=self.request,
        )
        return super().form_invalid(form)

    def form_valid(self, form):
        user = form.get_user()
        clear_login_attempts(self.request)
        if privileged_user_requires_mfa(user) and not user.is_mfa_enabled:
            self.request.session['mfa_pending_user_id'] = str(user.pk)
            self.request.session['mfa_next_url'] = str(reverse_lazy(_role_redirect(user)))
            return redirect('accounts:mfa_enroll')
        if user.is_mfa_enabled:
            self.request.session['mfa_pending_user_id'] = str(user.pk)
            self.request.session['mfa_next_url'] = str(reverse_lazy(_role_redirect(user)))
            return redirect('accounts:mfa_verify')
        login(self.request, user)
        log_audit_event(
            action=AuditAction.LOGIN,
            resource_type='Authentication',
            resource_id=str(user.pk),
            summary=f'Successful sign-in for {user.email}',
            user=user,
            request=self.request,
        )
        return redirect(self.get_success_url())


def logout_view(request):
    if request.user.is_authenticated:
        log_audit_event(
            action=AuditAction.LOGOUT,
            resource_type='Authentication',
            resource_id=str(request.user.pk),
            summary=f'Signed out {request.user.email}',
            user=request.user,
            request=request,
        )
    logout(request)
    messages.info(request, "You have been securely signed out of Nairobi Hospice PCMS.")
    return redirect('accounts:login')


@login_required
def profile_view(request):
    profile, _ = StaffProfile.objects.get_or_create(user=request.user)
    if request.method == 'POST':
        form = ProfileUpdateForm(request.POST, request.FILES, instance=profile)
        if form.is_valid():
            # Update user fields
            request.user.first_name = form.cleaned_data['first_name']
            request.user.last_name = form.cleaned_data['last_name']
            request.user.phone_number = form.cleaned_data['phone_number']
            request.user.save()

            form.save()
            messages.success(request, "Your staff profile and photograph have been successfully updated.")
            return redirect('accounts:profile')
    else:
        form = ProfileUpdateForm(
            instance=profile,
            initial={
                'first_name': request.user.first_name,
                'last_name': request.user.last_name,
                'phone_number': request.user.phone_number,
            }
        )

    return render(request, 'accounts/profile.html', {
        'user': request.user,
        'profile': profile,
        'form': form,
    })


class MFAEnrollmentView(View):
    template_name = 'accounts/mfa_enroll.html'

    def get(self, request):
        user = _pending_mfa_user(request)
        if not user:
            return redirect('accounts:login')
        secret = request.session.get('mfa_enrollment_secret')
        recovery_codes = request.session.get('mfa_recovery_codes_plain')
        if not secret or not recovery_codes:
            secret = generate_secret()
            recovery_codes, recovery_hashes = generate_recovery_codes()
            request.session['mfa_enrollment_secret'] = secret
            request.session['mfa_recovery_codes_plain'] = recovery_codes
            request.session['mfa_recovery_codes_hashes'] = recovery_hashes
        return render(request, self.template_name, {
            'form': MFAEnrollmentForm(),
            'user': user,
            'secret': secret,
            'provisioning_uri': provisioning_uri(secret, user.email),
            'recovery_codes': recovery_codes,
        })

    def post(self, request):
        user = _pending_mfa_user(request)
        if not user:
            return redirect('accounts:login')
        if is_mfa_rate_limited(str(user.pk)):
            return _abort_mfa_to_login(request, 'Too many verification attempts. Please sign in again.')
        secret = request.session.get('mfa_enrollment_secret')
        form = MFAEnrollmentForm(request.POST)
        if form.is_valid() and verify_totp(secret, form.cleaned_data['token']):
            user.mfa_secret = secret
            user.mfa_recovery_codes = request.session.get('mfa_recovery_codes_hashes', [])
            user.mfa_enrolled_at = timezone.now()
            user.is_mfa_enabled = True
            user.save(update_fields=['mfa_secret', 'mfa_recovery_codes', 'mfa_enrolled_at', 'is_mfa_enabled'])
            clear_mfa_attempts(str(user.pk))
            return _complete_mfa_login(request, user)
        if form.is_valid():
            record_failed_mfa(str(user.pk))
            form.add_error('token', 'That authenticator code is invalid or expired.')
        return render(request, self.template_name, {
            'form': form,
            'user': user,
            'secret': secret,
            'provisioning_uri': provisioning_uri(secret, user.email),
            'recovery_codes': request.session.get('mfa_recovery_codes_plain', []),
        }, status=400)


class MFAVerifyView(View):
    template_name = 'accounts/mfa_verify.html'

    def get(self, request):
        user = _pending_mfa_user(request)
        if not user or not user.mfa_secret:
            return redirect('accounts:login')
        return render(request, self.template_name, {'form': MFAVerifyForm(), 'user': user})

    def post(self, request):
        user = _pending_mfa_user(request)
        if not user or not user.mfa_secret:
            return redirect('accounts:login')
        if is_mfa_rate_limited(str(user.pk)):
            return _abort_mfa_to_login(request, 'Too many verification attempts. Please sign in again.')
        form = MFAVerifyForm(request.POST)
        valid = False
        if form.is_valid():
            if form.cleaned_data.get('token'):
                valid = verify_totp_for_user(user, form.cleaned_data['token'])
            else:
                valid = consume_recovery_code(user, form.cleaned_data.get('recovery_code'))
        if valid:
            clear_mfa_attempts(str(user.pk))
            return _complete_mfa_login(request, user)
        if form.is_valid():
            record_failed_mfa(str(user.pk))
            form.add_error(None, 'The verification code was invalid or already used.')
        log_audit_event(
            action=AuditAction.LOGIN,
            resource_type='MFAChallenge',
            resource_id=str(user.pk),
            summary=f'Failed MFA verification for {user.email}',
            user=user,
            request=request,
        )
        return render(request, self.template_name, {'form': form, 'user': user}, status=400)


PasswordResetRequestView = PasswordResetView
PasswordResetRequestDoneView = PasswordResetDoneView
PasswordResetRequestCompleteView = PasswordResetCompleteView


class PasswordResetRequestConfirmView(PasswordResetConfirmView):
    post_reset_redirect = reverse_lazy('accounts:password_reset_complete')


class StaffDirectoryView(ManagerRequiredMixin, ListView):
    model = StaffProfile
    template_name = 'accounts/staff_list.html'
    context_object_name = 'staff_members'

    def get_queryset(self):
        return StaffProfile.objects.select_related('user').order_by('role', 'user__first_name')
