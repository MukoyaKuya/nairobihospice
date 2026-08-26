from datetime import date, timedelta
from typing import Optional

from django.db.models import Q, QuerySet
from django.utils import timezone

from apps.patients.models import Patient

from .models import Appointment, AppointmentStatusChoices, AppointmentTypeChoices


def get_daily_appointments(target_date: Optional[date] = None) -> QuerySet[Appointment]:
    d = target_date or timezone.localdate()
    return Appointment.objects.filter(scheduled_date=d).select_related('patient', 'staff_member__user').order_by('scheduled_time')


def get_upcoming_appointments(
    start_date: Optional[date] = None,
    limit: int = 50,
    queryset: Optional[QuerySet[Appointment]] = None,
) -> QuerySet[Appointment]:
    s = start_date or timezone.localdate()
    base_queryset = queryset if queryset is not None else Appointment.objects.all()
    return base_queryset.filter(
        scheduled_date__gte=s
    ).select_related('patient', 'staff_member__user').order_by('scheduled_date', 'scheduled_time')[:limit]


def get_weekly_appointments(start_date: Optional[date] = None) -> QuerySet[Appointment]:
    s = start_date or timezone.localdate()
    e = s + timedelta(days=7)
    return Appointment.objects.filter(
        scheduled_date__gte=s, scheduled_date__lte=e
    ).select_related('patient', 'staff_member__user').order_by('scheduled_date', 'scheduled_time')


def search_appointments(
    *,
    query: Optional[str] = None,
    status: Optional[str] = None,
    staff_id: Optional[str] = None,
    appointment_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    is_clinical: bool = True,
) -> QuerySet[Appointment]:
    qs = Appointment.objects.select_related('patient', 'staff_member__user').order_by('-scheduled_date', '-scheduled_time')

    if query:
        q_clean = query.strip()
        q_filter = (
            Q(patient__first_name__icontains=q_clean) |
            Q(patient__last_name__icontains=q_clean) |
            Q(patient__hospice_number__icontains=q_clean) |
            Q(location__icontains=q_clean)
        )
        if is_clinical:
            q_filter |= Q(reason__icontains=q_clean)
        qs = qs.filter(q_filter)

    if status and status in AppointmentStatusChoices.values:
        qs = qs.filter(status=status)

    if staff_id:
        qs = qs.filter(staff_member__id=staff_id)

    if appointment_type and appointment_type in AppointmentTypeChoices.values:
        qs = qs.filter(appointment_type=appointment_type)

    if date_from:
        qs = qs.filter(scheduled_date__gte=date_from)

    if date_to:
        qs = qs.filter(scheduled_date__lte=date_to)

    return qs


def get_patient_appointments(patient: Patient) -> QuerySet[Appointment]:
    return Appointment.objects.filter(patient=patient).select_related('staff_member__user').order_by('-scheduled_date', '-scheduled_time')
