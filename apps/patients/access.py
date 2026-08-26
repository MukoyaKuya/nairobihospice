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


def is_operations_manager(user) -> bool:
    """True specifically for non-superuser Operations Managers without clinical role."""
    return bool(
        user
        and user.is_authenticated
        and getattr(user, 'role', '') == RoleChoices.MANAGER
        and not user.is_superuser
        and getattr(user, 'role', '') != RoleChoices.ADMINISTRATOR
    )


def can_access_clinical_phi(user) -> bool:
    """
    Returns True for clinical staff (Doctors, Nurses, Clinical Officers, etc.) and System Administrators.
    Operations Managers and Receptionists are non-clinical and must NOT view sensitive clinical diagnoses.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', '') == RoleChoices.ADMINISTRATOR:
        return True
    if getattr(user, 'is_receptionist', False) or getattr(user, 'role', '') == RoleChoices.MANAGER or getattr(user, 'role', '') == RoleChoices.PHARMACIST:
        return False
    return bool(getattr(user, 'is_clinical', False))


def can_schedule_appointments(user) -> bool:
    """
    Returns True for Receptionists, Clinical Staff, and Administrators.
    Operations Managers cannot book appointments.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', '') == RoleChoices.ADMINISTRATOR:
        return True
    if getattr(user, 'role', '') == RoleChoices.MANAGER or getattr(user, 'role', '') == RoleChoices.PHARMACIST:
        return False
    return bool(getattr(user, 'is_receptionist', False) or getattr(user, 'is_clinical', False))


def can_register_patients(user) -> bool:
    """
    Returns True for Front Desk Receptionists and System Administrators.
    Operations Managers cannot register patients.
    """
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser or getattr(user, 'role', '') == RoleChoices.ADMINISTRATOR:
        return True
    if getattr(user, 'role', '') == RoleChoices.MANAGER or getattr(user, 'role', '') == RoleChoices.PHARMACIST:
        return False
    return bool(getattr(user, 'is_receptionist', False))


def can_conduct_clinical_encounters(user) -> bool:
    """
    Returns True for clinical practitioners.
    Operations Managers and Receptionists cannot conduct clinical encounters.
    """
    if not user or not user.is_authenticated:
        return False
    if getattr(user, 'role', '') == RoleChoices.MANAGER or getattr(user, 'is_receptionist', False) or getattr(user, 'role', '') == RoleChoices.PHARMACIST:
        return False
    return bool(getattr(user, 'is_clinical', False) or user.is_superuser or getattr(user, 'role', '') == RoleChoices.ADMINISTRATOR)



import datetime


def authorized_patient_queryset(user):
    """Return patients whose clinical records this user is allowed to access."""
    if not user or not user.is_authenticated:
        return Patient.objects.none()
    if can_manage_all_patients(user):
        return Patient.objects.all()
    if user.role == RoleChoices.PHARMACIST:
        return Patient.objects.filter(stock_movements__recorded_by=user, status='ACTIVE').distinct()
    if not user.is_clinical:
        return Patient.objects.none()

    today = timezone.localdate()
    appt_min_date = today - datetime.timedelta(days=7)
    appt_max_date = today + datetime.timedelta(days=14)

    return Patient.objects.filter(
        (
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
        | Q(
            appointments__scheduled_date__gte=appt_min_date,
            appointments__scheduled_date__lte=appt_max_date,
            appointments__status__in=['SCHEDULED', 'CONFIRMED'],
            appointments__staff_member__user=user,
        ),
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
