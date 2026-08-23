from django.core.exceptions import ValidationError
from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.patients.models import Patient

from .models import SymptomAssessmentRecord, SymptomScore


@transaction.atomic
def record_esas_assessment(*, patient: Patient, symptom_scores: dict, clinical_notes: str = '', encounter=None, user=None) -> SymptomAssessmentRecord:
    """
    Records an ESAS evaluation and calculates aggregate distress score.
    symptom_scores is a dict mapping SymptomTypeChoices to int scores (0-10).
    """
    for symptom_key, score_val in symptom_scores.items():
        if score_val is not None:
            try:
                num_score = int(score_val)
                if not (0 <= num_score <= 10):
                    raise ValidationError(f"ESAS symptom score for {symptom_key} must be between 0 and 10.")
            except (ValueError, TypeError) as err:
                raise ValidationError(f"Invalid symptom score for {symptom_key}: {score_val}") from err

    total_distress = sum([int(v) for k, v in symptom_scores.items() if isinstance(v, (int, str)) and str(v).isdigit()])

    record = SymptomAssessmentRecord.objects.create(
        patient=patient,
        encounter=encounter,
        total_distress_score=total_distress,
        clinical_notes=clinical_notes,
        recorded_by=user,
    )

    for symptom_key, score_val in symptom_scores.items():
        if score_val is not None and str(score_val).isdigit():
            SymptomScore.objects.create(
                record=record,
                symptom_type=symptom_key,
                score=int(score_val),
            )

    log_audit_event(
        action=AuditAction.CREATE,
        resource_type='SymptomRecord',
        resource_id=str(record.id),
        summary=f"Recorded ESAS symptom profile for {patient.full_name} (Distress Index: {total_distress})",
        user=user,
    )
    return record
