import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import StaffProfile
from apps.patients.models import Patient


class AppointmentTypeChoices(models.TextChoices):
    CLINIC_VISIT = 'CLINIC_VISIT', _('Hospice Clinic Consultation')
    HOME_VISIT = 'HOME_VISIT', _('Home Care Visit')
    TELEPHONE = 'TELEPHONE', _('Telephone Review')
    MDT_MEETING = 'MDT_MEETING', _('Multidisciplinary Team Case Review')
    COUNSELLING = 'COUNSELLING', _('Psychosocial / Bereavement Session')
    DAY_CARE = 'DAY_CARE', _('Day Care Activity')


class AppointmentStatusChoices(models.TextChoices):
    SCHEDULED = 'SCHEDULED', _('Scheduled')
    CONFIRMED = 'CONFIRMED', _('Confirmed')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Cancelled')
    MISSED = 'MISSED', _('Missed / Did Not Attend (DNA)')
    RESCHEDULED = 'RESCHEDULED', _('Rescheduled')


class Appointment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='appointments')
    staff_member = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='appointments')

    appointment_type = models.CharField(
        max_length=30,
        choices=AppointmentTypeChoices.choices,
        default=AppointmentTypeChoices.CLINIC_VISIT
    )
    scheduled_date = models.DateField(db_index=True)
    scheduled_time = models.TimeField(default='09:00')
    duration_minutes = models.PositiveIntegerField(default=45)

    location = models.CharField(max_length=255, default='Nairobi Hospice')
    status = models.CharField(
        max_length=20,
        choices=AppointmentStatusChoices.choices,
        default=AppointmentStatusChoices.SCHEDULED,
        db_index=True
    )

    reason = models.CharField(max_length=255, help_text=_('e.g., Routine monthly review, symptom reassessment, home wound dressing'))
    notes = models.TextField(blank=True)
    outcome_notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='scheduled_appointments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Appointment')
        verbose_name_plural = _('Appointments')
        ordering = ['-scheduled_date', '-scheduled_time']
        indexes = [
            models.Index(fields=['patient', 'scheduled_date'], name='appt_patient_date_idx'),
            models.Index(fields=['staff_member', 'scheduled_date'], name='appt_staff_date_idx'),
        ]

    def __str__(self):
        return f"{self.get_appointment_type_display()} - {self.patient.full_name} with {self.staff_member.user.display_name} on {self.scheduled_date}"
