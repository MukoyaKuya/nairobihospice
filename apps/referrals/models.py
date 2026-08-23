import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.patients.models import Patient, SexChoices


class ReferralSourceChoices(models.TextChoices):
    HOSPITAL = 'HOSPITAL', _('Public / Private Hospital')
    HEALTH_CENTRE = 'HEALTH_CENTRE', _('Health Centre / Clinic')
    COMMUNITY_WORKER = 'COMMUNITY_WORKER', _('Community Health Promoter')
    SELF_FAMILY = 'SELF_FAMILY', _('Self / Family Referral')
    OTHER_HOSPICE = 'OTHER_HOSPICE', _('Other Hospice / Palliative Unit')
    RELIGIOUS_GROUP = 'RELIGIOUS_GROUP', _('Faith-Based / Community Group')
    OTHER = 'OTHER', _('Other Source')


class ReferralPriorityChoices(models.TextChoices):
    ROUTINE = 'ROUTINE', _('Routine (Review within 5 days)')
    URGENT = 'URGENT', _('Urgent (Review within 48 hours)')
    EMERGENCY = 'EMERGENCY', _('Emergency / Severe Distress (Review within 24 hours)')


class ReferralStatusChoices(models.TextChoices):
    RECEIVED = 'RECEIVED', _('Received')
    UNDER_REVIEW = 'UNDER_REVIEW', _('Under Review')
    ACCEPTED = 'ACCEPTED', _('Accepted')
    REJECTED = 'REJECTED', _('Rejected')
    CONVERTED = 'CONVERTED', _('Converted to Patient')
    CLOSED = 'CLOSED', _('Closed')


class Referral(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    referral_number = models.CharField(max_length=30, unique=True, db_index=True)

    # Patient Demographics at Referral
    patient_name = models.CharField(max_length=200)
    date_of_birth = models.DateField(null=True, blank=True)
    approximate_age = models.PositiveIntegerField(null=True, blank=True)
    sex = models.CharField(max_length=2, choices=SexChoices.choices, default=SexChoices.FEMALE)
    phone_number = models.CharField(max_length=30, blank=True)
    alternative_phone = models.CharField(max_length=30, blank=True)

    address = models.CharField(max_length=255, blank=True)
    county = models.CharField(max_length=100, default='Nairobi')
    sub_county = models.CharField(max_length=100, blank=True)
    landmark = models.CharField(max_length=255, blank=True)

    # Source Info
    referral_source = models.CharField(
        max_length=30,
        choices=ReferralSourceChoices.choices,
        default=ReferralSourceChoices.HOSPITAL
    )
    referring_facility = models.CharField(max_length=200, help_text=_('e.g. Kenyatta National Hospital, Texas Cancer Centre'))
    referring_clinician_name = models.CharField(max_length=150, blank=True)
    referring_clinician_phone = models.CharField(max_length=30, blank=True)
    referring_clinician_email = models.EmailField(blank=True)

    referral_date = models.DateField(default=timezone.now)
    priority = models.CharField(
        max_length=20,
        choices=ReferralPriorityChoices.choices,
        default=ReferralPriorityChoices.ROUTINE,
        db_index=True
    )
    status = models.CharField(
        max_length=20,
        choices=ReferralStatusChoices.choices,
        default=ReferralStatusChoices.RECEIVED,
        db_index=True
    )

    # Clinical Information
    primary_diagnosis = models.CharField(max_length=255, help_text=_('e.g. Ca Breast Stage IV with bone metastases'))
    reason_for_referral = models.TextField(help_text=_('Pain management, severe dyspnea, family counseling, end-of-life care'))
    clinical_summary = models.TextField(blank=True, help_text=_('History of current illness, treatments received, ECOG performance'))
    current_medications = models.TextField(blank=True)

    # Review & Triage
    assigned_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_referrals'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    rejection_reason = models.TextField(blank=True)

    # Link to converted patient
    converted_patient = models.ForeignKey(
        Patient,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='originating_referrals'
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_referrals'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Referral')
        verbose_name_plural = _('Referrals')
        ordering = ['-referral_date', '-created_at']

    def __str__(self):
        return f"{self.referral_number} - {self.patient_name} ({self.get_status_display()})"
