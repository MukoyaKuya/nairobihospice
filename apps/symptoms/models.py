import uuid

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.encounters.models import Encounter
from apps.patients.models import Patient


class SymptomTypeChoices(models.TextChoices):
    PAIN = 'PAIN', _('Pain')
    TIREDNESS = 'TIREDNESS', _('Tiredness / Fatigue')
    DROWSINESS = 'DROWSINESS', _('Drowsiness')
    NAUSEA = 'NAUSEA', _('Nausea')
    LACK_OF_APPETITE = 'LACK_OF_APPETITE', _('Lack of Appetite')
    SHORTNESS_OF_BREATH = 'SHORTNESS_OF_BREATH', _('Shortness of Breath / Dyspnea')
    DEPRESSION = 'DEPRESSION', _('Depression / Sadness')
    ANXIETY = 'ANXIETY', _('Anxiety / Nervousness')
    WELLBEING = 'WELLBEING', _('Overall Wellbeing')
    CONSTIPATION = 'CONSTIPATION', _('Constipation')
    INSOMNIA = 'INSOMNIA', _('Insomnia / Sleep Difficulty')
    OTHER = 'OTHER', _('Other Symptom')


class SymptomAssessmentRecord(models.Model):
    """
    Container for an Edmonton Symptom Assessment System (ESAS) evaluation point.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='symptom_records')
    encounter = models.ForeignKey(Encounter, on_delete=models.SET_NULL, null=True, blank=True, related_name='symptom_records')
    recorded_at = models.DateTimeField(default=timezone.now, db_index=True)
    total_distress_score = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text=_('Cumulative ESAS distress score sum (0-100)'),
    )
    clinical_notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='recorded_symptom_assessments'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Symptom Assessment Record')
        verbose_name_plural = _('Symptom Assessment Records')
        ordering = ['-recorded_at']
        indexes = [models.Index(fields=['patient', 'recorded_at'], name='symptom_patient_date_idx')]
        constraints = [
            models.CheckConstraint(
                condition=models.Q(total_distress_score__gte=0, total_distress_score__lte=100),
                name='symptom_total_distress_range',
            ),
        ]

    def __str__(self):
        return f"ESAS for {self.patient.full_name} on {self.recorded_at.strftime('%d %b %Y')} (Distress: {self.total_distress_score})"

    @property
    def pain_score_val(self):
        item = self.scores.filter(symptom_type=SymptomTypeChoices.PAIN).first()
        return item.score if item else None


class SymptomScore(models.Model):
    """
    Individual symptom score on a validated 0-10 numeric scale.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    record = models.ForeignKey(SymptomAssessmentRecord, on_delete=models.CASCADE, related_name='scores')
    symptom_type = models.CharField(max_length=30, choices=SymptomTypeChoices.choices)
    custom_symptom_name = models.CharField(max_length=100, blank=True)
    score = models.IntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        help_text=_('0 (None) to 10 (Worst Possible)')
    )
    notes = models.CharField(max_length=255, blank=True)

    class Meta:
        verbose_name = _('Symptom Score')
        verbose_name_plural = _('Symptom Scores')
        ordering = ['record', 'symptom_type']
        constraints = [models.UniqueConstraint(fields=['record', 'symptom_type'], name='unique_symptom_per_record')]

    def __str__(self):
        name = self.custom_symptom_name if self.symptom_type == SymptomTypeChoices.OTHER else self.get_symptom_type_display()
        return f"{name}: {self.score}/10"
