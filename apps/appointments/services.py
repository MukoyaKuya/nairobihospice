from datetime import date, time

from django.db import transaction

from apps.accounts.models import StaffProfile
from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.notifications.services import notify_staff_of_new_appointment
from apps.patients.models import Patient

from .models import Appointment, AppointmentStatusChoices, AppointmentTypeChoices


@transaction.atomic
def schedule_appointment(
    *,
    patient: Patient,
    staff_member: StaffProfile,
    appointment_type: AppointmentTypeChoices,
    scheduled_date: date,
    scheduled_time: time = time(9, 0),
    duration_minutes: int = 45,
    location: str = '',
    reason: str = '',
    notes: str = '',
    user=None,
) -> Appointment:
    appt = Appointment.objects.create(
        patient=patient,
        staff_member=staff_member,
        appointment_type=appointment_type,
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
        duration_minutes=duration_minutes,
        location=location or ('Nairobi Hospice' if appointment_type == AppointmentTypeChoices.CLINIC_VISIT else patient.address or 'Home'),
        reason=reason,
        notes=notes,
        status=AppointmentStatusChoices.SCHEDULED,
        created_by=user,
    )
    log_audit_event(
        action=AuditAction.CREATE,
        resource_type='Appointment',
        resource_id=str(appt.id),
        summary=f"Scheduled {appt.get_appointment_type_display()} for {patient.full_name} on {scheduled_date} at {scheduled_time}",
        user=user,
    )
    transaction.on_commit(
        lambda: notify_staff_of_new_appointment(appointment=appt, scheduled_by=user)
    )
    return appt


@transaction.atomic
def update_appointment_status(*, appointment: Appointment, status: AppointmentStatusChoices, outcome_notes: str = '', user=None) -> Appointment:
    from django.core.exceptions import ValidationError
    from django.utils import timezone
    if status == AppointmentStatusChoices.COMPLETED and appointment.scheduled_date > timezone.now().date():
        raise ValidationError("A future appointment cannot be marked as completed until the visit date.")

    appointment.status = status
    if outcome_notes:
        appointment.outcome_notes = outcome_notes
    appointment.save()

    log_audit_event(
        action=AuditAction.UPDATE,
        resource_type='Appointment',
        resource_id=str(appointment.id),
        summary=f"Updated appointment for {appointment.patient.full_name} to {appointment.get_status_display()}",
        user=user,
    )
    return appointment
