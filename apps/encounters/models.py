import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.care.models import EpisodeOfCare
from apps.patients.models import Patient


class EncounterTypeChoices(models.TextChoices):
    CLINIC_VISIT = 'CLINIC_VISIT', _('Hospice Clinic Consultation')
    HOME_VISIT = 'HOME_VISIT', _('Home Care Visit')
    TELEPHONE = 'TELEPHONE', _('Telephone Follow-up / Teleconsultation')
    COMMUNITY_VISIT = 'COMMUNITY_VISIT', _('Community / Outreach Visit')
    COUNSELLING = 'COUNSELLING', _('Psychosocial / Bereavement Session')
    MDT_REVIEW = 'MDT_REVIEW', _('Multidisciplinary Team Case Review')
    DAY_CARE = 'DAY_CARE', _('Hospice Day Care Activity')
    OTHER = 'OTHER', _('Other Encounter')


class Encounter(models.Model):
    """
    Direct clinical interaction with a patient or their family caregiver.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='encounters')
    episode = models.ForeignKey(EpisodeOfCare, on_delete=models.SET_NULL, null=True, blank=True, related_name='encounters')

    encounter_type = models.CharField(
        max_length=30,
        choices=EncounterTypeChoices.choices,
        default=EncounterTypeChoices.CLINIC_VISIT,
        db_index=True
    )
    encounter_date = models.DateField(default=timezone.now, db_index=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    location = models.CharField(max_length=255, default='Nairobi Hospice Clinic')
    reason = models.CharField(max_length=255, help_text=_('Reason for encounter, e.g. Severe pain exacerbation, routine home check'))

    # Clinical Documentation
    clinical_notes = models.TextField(help_text=_('Clinical summary / Progress notes (SOAP / Narrative)'))
    interventions_performed = models.TextField(blank=True, help_text=_('Procedures, med administration, wound dressing, education, counseling'))

    # Follow-up
    next_followup_date = models.DateField(null=True, blank=True)
    next_followup_plan = models.TextField(blank=True)

    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_encounters'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Encounter')
        verbose_name_plural = _('Encounters')
        ordering = ['-encounter_date', '-created_at']
        indexes = [models.Index(fields=['patient', 'encounter_date'], name='encounter_patient_date_idx')]

    def __str__(self):
        return f"{self.get_encounter_type_display()} - {self.patient.full_name} ({self.encounter_date.strftime('%d %b %Y')})"
