import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.patients.models import Patient


class MedicationStatusChoices(models.TextChoices):
    ACTIVE = 'ACTIVE', _('Active Medication')
    HELD = 'HELD', _('Temporarily Held / Paused')
    DISCONTINUED = 'DISCONTINUED', _('Discontinued / Ceased')
    COMPLETED = 'COMPLETED', _('Course Completed')


class RouteChoices(models.TextChoices):
    ORAL = 'ORAL', _('Oral (PO)')
    SUBLINGUAL = 'SUBLINGUAL', _('Sublingual (SL)')
    SUBCUTANEOUS = 'SUBCUTANEOUS', _('Subcutaneous (SC)')
    INTRAVENOUS = 'INTRAVENOUS', _('Intravenous (IV)')
    TRANSDERMAL = 'TRANSDERMAL', _('Transdermal Patch')
    RECTAL = 'RECTAL', _('Rectal (PR)')
    TOPICAL = 'TOPICAL', _('Topical')
    INHALED = 'INHALED', _('Inhalation / Nebulized')


class MedicationStatement(models.Model):
    """
    Patient medication record with dosage, route, frequency, and historical tracking.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='medications')

    medication_name = models.CharField(
        max_length=200,
        help_text=_('Drug name and formulation, e.g. Oral Morphine Solution 5mg/5ml, Paracetamol, Lactulose')
    )
    dosage = models.CharField(max_length=100, help_text=_('e.g. 10 mg (10 ml)'))
    route = models.CharField(max_length=20, choices=RouteChoices.choices, default=RouteChoices.ORAL)
    frequency = models.CharField(max_length=100, help_text=_('e.g. Every 4 hours (q4h) + Breakthrough dose PRN'))
    indication = models.CharField(max_length=200, blank=True, help_text=_('e.g. Severe somatic and visceral cancer pain'))

    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=MedicationStatusChoices.choices,
        default=MedicationStatusChoices.ACTIVE,
        db_index=True
    )

    prescriber = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='prescribed_medications'
    )
    prescriber_name = models.CharField(max_length=150, blank=True)

    instructions_for_caregiver = models.TextField(blank=True, help_text=_('Caregiver instructions in English/Swahili'))
    discontinuation_reason = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Medication Record')
        verbose_name_plural = _('Medication Records')
        ordering = ['-status', '-start_date']
        indexes = [models.Index(fields=['patient', 'status'], name='med_patient_status_idx')]

    def __str__(self):
        return f"{self.medication_name} ({self.dosage} {self.route}) - {self.patient.full_name}"

    @property
    def is_active(self):
        return self.status == MedicationStatusChoices.ACTIVE
