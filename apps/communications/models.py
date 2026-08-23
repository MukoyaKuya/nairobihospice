import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.patients.models import Patient


class CommunicationTypeChoices(models.TextChoices):
    PHONE_CALL = 'PHONE_CALL', _('Telephone Call')
    SMS = 'SMS', _('SMS Message')
    EMAIL = 'EMAIL', _('Email Communication')
    FAMILY_MEETING = 'FAMILY_MEETING', _('Family Conference / Meeting')
    MDT_COMMUNICATION = 'MDT_COMMUNICATION', _('Internal Multidisciplinary Note')
    EXTERNAL_LIAISON = 'EXTERNAL_LIAISON', _('External Hospital / Clinician Liaison')


class CommunicationRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='communications')
    communication_type = models.CharField(
        max_length=30,
        choices=CommunicationTypeChoices.choices,
        default=CommunicationTypeChoices.PHONE_CALL
    )
    communication_date = models.DateTimeField(default=timezone.now)
    contact_person = models.CharField(max_length=150, help_text=_('Patient, Primary Caregiver, Referring Doctor, etc.'))
    phone_or_email = models.CharField(max_length=100, blank=True)
    summary = models.TextField(help_text=_('Summary of conversation / discussion'))

    followup_required = models.BooleanField(default=False)
    followup_notes = models.TextField(blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='logged_communications'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Communication Record')
        verbose_name_plural = _('Communication Records')
        ordering = ['-communication_date']
        indexes = [models.Index(fields=['patient', 'communication_date'], name='comm_patient_date_idx')]

    def __str__(self):
        return f"{self.get_communication_type_display()} with {self.contact_person} ({self.patient.full_name})"
