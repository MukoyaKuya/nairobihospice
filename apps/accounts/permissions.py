from functools import wraps

from django.contrib.auth.mixins import UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from rest_framework import permissions

from .models import RoleChoices

# Roles that may issue clinical instructions ( prescribing sensu strictu ).
PRESCRIBER_ROLES = {RoleChoices.DOCTOR, RoleChoices.CLINICAL_OFFICER}

# Roles that may create or update medication statements: prescribers plus the
# nurses who administer/document doses in home care and the pharmacists who
# dispense. This is the single policy shared by the web views and the API.
MEDICATION_RECORDER_ROLES = PRESCRIBER_ROLES | {RoleChoices.NURSE, RoleChoices.PHARMACIST}


def _has_role(user, roles):
    if not (user and user.is_authenticated):
        return False
    if user.is_superuser or user.role == RoleChoices.ADMINISTRATOR:
        return True
    return user.role in roles


def can_prescribe(user) -> bool:
    """Doctors and Clinical Officers may issue prescriptions."""
    return _has_role(user, PRESCRIBER_ROLES)


def can_record_medications(user) -> bool:
    """Prescribers, nurses, and pharmacists may record or update medication statements."""
    return _has_role(user, MEDICATION_RECORDER_ROLES)


def role_required(*allowed_roles):
    """
    Decorator for views requiring one of the allowed roles.
    Superusers and Managers always have administrative bypass.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.is_superuser or request.user.role == RoleChoices.ADMINISTRATOR:
                return view_func(request, *args, **kwargs)
            if request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have permission to perform this clinical or administrative action.")
        return _wrapped_view
    return decorator


class RoleRequiredMixin(UserPassesTestMixin):
    """
    CBV mixin to restrict access based on user role.
    """
    allowed_roles = []

    def test_func(self):
        user = self.request.user
        if not user.is_authenticated:
            return False
        if user.is_superuser or user.role == RoleChoices.ADMINISTRATOR:
            return True
        return user.role in self.allowed_roles


class ClinicalStaffRequiredMixin(RoleRequiredMixin):
    allowed_roles = [
        RoleChoices.DOCTOR,
        RoleChoices.NURSE,
        RoleChoices.CLINICAL_OFFICER,
        RoleChoices.SOCIAL_WORKER,
        RoleChoices.COUNSELLOR,
    ]


class DoctorRequiredMixin(RoleRequiredMixin):
    allowed_roles = [RoleChoices.DOCTOR]


class NurseRequiredMixin(RoleRequiredMixin):
    allowed_roles = [RoleChoices.NURSE, RoleChoices.DOCTOR, RoleChoices.CLINICAL_OFFICER]


class ManagerRequiredMixin(RoleRequiredMixin):
    allowed_roles = [RoleChoices.MANAGER, RoleChoices.ADMINISTRATOR]


# DRF Permissions
class IsClinicalStaffPermission(permissions.BasePermission):
    """Restricts access to clinical staff members (Doctor, Nurse, CO, Social Worker, Counsellor)."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_clinical or request.user.is_superuser))


class IsClinicalOrManagerPermission(permissions.BasePermission):
    """Allows clinical and management staff to access referral clinical data."""

    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and (user.is_clinical or user.is_manager or user.is_superuser)
        )


class IsPharmacistOrClinicalPermission(permissions.BasePermission):
    """Medication reads for clinical staff and pharmacists; writes follow the shared medication-recording policy."""
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        if request.method in permissions.SAFE_METHODS:
            return bool(request.user.is_clinical or getattr(request.user, 'is_pharmacist', False) or request.user.is_superuser)
        return can_record_medications(request.user)


class IsManagerOrAdminPermission(permissions.BasePermission):
    """Restricts management / export access to Managers and System Administrators."""
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and (request.user.is_manager or request.user.is_superuser))


class IsAuthenticatedApiPermission(permissions.BasePermission):
    """Allow reads to authenticated staff and limit API writes to explicit roles."""

    write_roles = {
        RoleChoices.DOCTOR,
        RoleChoices.NURSE,
        RoleChoices.CLINICAL_OFFICER,
        RoleChoices.SOCIAL_WORKER,
        RoleChoices.COUNSELLOR,
        RoleChoices.MANAGER,
        RoleChoices.ADMINISTRATOR,
    }

    def has_permission(self, request, view):
        user = request.user
        if not user or not user.is_authenticated:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        if user.is_superuser or user.role == RoleChoices.ADMINISTRATOR:
            return True
        if request.method == 'DELETE':
            return user.role == RoleChoices.MANAGER
        return user.role in self.write_roles


class IsAppointmentApiPermission(IsAuthenticatedApiPermission):
    """Allow appointment reads broadly, but reserve API writes for scheduling roles."""

    scheduling_roles = {RoleChoices.RECEPTIONIST, RoleChoices.MANAGER, RoleChoices.ADMINISTRATOR}

    def has_permission(self, request, view):
        if not super().has_permission(request, view):
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user.is_superuser or request.user.role in self.scheduling_roles)
