from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.accounts.models import RoleChoices
from apps.patients.access import authorized_patient_queryset, can_manage_all_patients

from .models import Referral


def referral_queryset_for_user(user):
    """Scope referral records while preserving safe front-desk intake visibility."""
    if can_manage_all_patients(user):
        return Referral.objects.all()
    if not user or not user.is_authenticated:
        return Referral.objects.none()
    if user.is_receptionist:
        return Referral.objects.all()
    if user.is_clinical:
        return Referral.objects.filter(
            Q(created_by=user)
            | Q(assigned_reviewer=user)
            | Q(converted_patient__in=authorized_patient_queryset(user))
        ).distinct()
    return Referral.objects.none()


def can_review_referrals(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.role in [RoleChoices.ADMINISTRATOR, RoleChoices.MANAGER] or user.is_clinical)
    )


def get_referral_or_404(user, referral_id):
    return get_object_or_404(referral_queryset_for_user(user), pk=referral_id)
