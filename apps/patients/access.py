from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone

from apps.accounts.models import RoleChoices

from .models import Patient


def can_manage_all_patients(user):
    return bool(
        user
        and user.is_authenticated
        and (user.is_superuser or user.role in [RoleChoices.ADMINISTRATOR, RoleChoices.MANAGER])
    )


def authorized_patient_queryset(user):
    """Return patients whose clinical records this user is allowed to access."""
    if not user or not user.is_authenticated:
        return Patient.objects.none()
    if can_manage_all_patients(user) or user.role == RoleChoices.PHARMACIST:
        return Patient.objects.all()
    if not user.is_clinical:
        return Patient.objects.none()

    today = timezone.localdate()
    return Patient.objects.filter(
        Q(created_by=user)
        | (
            Q(
                episodes__status='ACTIVE',
                episodes__team_members__staff_member__user=user,
                episodes__team_members__start_date__lte=today,
            )
            & Q(
                Q(episodes__team_members__end_date__isnull=True)
                | Q(episodes__team_members__end_date__gte=today)
            )
        )
        | Q(appointments__staff_member__user=user),
    ).distinct()


def get_authorized_patient_or_404(user, patient_id):
    return get_object_or_404(authorized_patient_queryset(user), pk=patient_id)


def get_operational_patient_or_404(user, patient_id):
    """Allow front-desk workflows to identify patients without exposing clinical records."""
    if user and (user.is_receptionist or can_manage_all_patients(user)):
        return get_object_or_404(Patient, pk=patient_id)
    return get_authorized_patient_or_404(user, patient_id)


def user_can_access_patient(user, patient_id):
    return authorized_patient_queryset(user).filter(pk=patient_id).exists()


def authorized_appointment_queryset(user):
    """Return appointments visible to a user without exposing unrelated care."""
    from apps.appointments.models import Appointment

    if can_manage_all_patients(user) or (user and user.is_authenticated and user.is_receptionist):
        return Appointment.objects.all()
    return Appointment.objects.filter(patient__in=authorized_patient_queryset(user))
