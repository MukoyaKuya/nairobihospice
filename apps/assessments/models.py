import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.encounters.models import Encounter
from apps.patients.models import Patient


class AssessmentTypeChoices(models.TextChoices):
    INITIAL = 'INITIAL', _('Initial Holistic Palliative Assessment')
    PAIN = 'PAIN', _('Comprehensive Pain Assessment (0-10 & Mapping)')
    FUNCTIONAL = 'FUNCTIONAL', _('Functional Assessment (PPS & ECOG)')
    PSYCHOSOCIAL = 'PSYCHOSOCIAL', _('Psychosocial & Family Assessment')
    SPIRITUAL = 'SPIRITUAL', _('Spiritual & Existential Assessment')
    NUTRITIONAL = 'NUTRITIONAL', _('Nutritional & Intake Assessment')
    CAREGIVER = 'CAREGIVER', _('Caregiver Burden & Needs Assessment')
    FOLLOWUP = 'FOLLOWUP', _('Routine Clinical Follow-up Assessment')


class Assessment(models.Model):
    """
    Structured clinical assessment. Preserves clinical history.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='assessments')
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, null=True, blank=True, related_name='assessments')

    assessment_type = models.CharField(
        max_length=30,
        choices=AssessmentTypeChoices.choices,
        default=AssessmentTypeChoices.INITIAL,
        db_index=True
    )
    assessment_date = models.DateField(default=timezone.now, db_index=True)

    # Specific common clinical scores
    pain_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text=_('Numeric Rating Scale 0-10'),
    )
    pps_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_('Palliative Performance Scale % (0-100)'),
    )
    ecog_score = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(0), MaxValueValidator(4)],
        help_text=_('ECOG Performance Status (0-4)'),
    )

    # Structured Clinical Payload
    structured_data = models.JSONField(default=dict, blank=True, help_text=_('Structured tool-specific observations'))
    clinical_summary = models.TextField(help_text=_('Clinician impressions, diagnosis synthesis, management plan'))

    next_review_date = models.DateField(null=True, blank=True)

    assessor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conducted_assessments'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Clinical Assessment')
        verbose_name_plural = _('Clinical Assessments')
        ordering = ['-assessment_date', '-created_at']
        indexes = [models.Index(fields=['patient', 'assessment_date'], name='assessment_patient_date_idx')]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(pain_score__isnull=True) | models.Q(pain_score__gte=0, pain_score__lte=10),
                name='assessment_pain_score_range',
            ),
            models.CheckConstraint(
                condition=models.Q(pps_score__isnull=True) | models.Q(pps_score__gte=0, pps_score__lte=100),
                name='assessment_pps_score_range',
            ),
            models.CheckConstraint(
                condition=models.Q(ecog_score__isnull=True) | models.Q(ecog_score__gte=0, ecog_score__lte=4),
                name='assessment_ecog_score_range',
            ),
        ]

    def __str__(self):
        return f"{self.get_assessment_type_display()} - {self.patient.full_name} ({self.assessment_date.strftime('%d %b %Y')})"


class AssessmentAmendment(models.Model):
    """
    Immutable audit record for clinical corrections to assessments.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    assessment = models.ForeignKey(Assessment, on_delete=models.CASCADE, related_name='amendments')
    amended_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    amended_at = models.DateTimeField(auto_now_add=True)
    reason_for_amendment = models.TextField()
    previous_content = models.TextField()
    amended_notes = models.TextField()

    class Meta:
        verbose_name = _('Assessment Amendment')
        verbose_name_plural = _('Assessment Amendments')
        ordering = ['-amended_at']
        indexes = [models.Index(fields=['assessment', 'amended_at'], name='amendment_assessment_date_idx')]

    def __str__(self):
        return f"Amendment to {self.assessment} by {self.amended_by} on {self.amended_at.strftime('%d %b %Y')}"
