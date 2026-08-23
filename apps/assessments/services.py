from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.patients.models import Patient

from .models import Assessment, AssessmentAmendment, AssessmentTypeChoices


@transaction.atomic
def record_assessment(
    *,
    patient: Patient,
    assessment_type: AssessmentTypeChoices,
    clinical_summary: str,
    pain_score: int = None,
    pps_score: int = None,
    ecog_score: int = None,
    structured_data: dict = None,
    encounter=None,
    next_review_date=None,
    user=None,
) -> Assessment:
    assessment = Assessment.objects.create(
        patient=patient,
        encounter=encounter,
        assessment_type=assessment_type,
        clinical_summary=clinical_summary,
        pain_score=pain_score,
        pps_score=pps_score,
        ecog_score=ecog_score,
        structured_data=structured_data or {},
        next_review_date=next_review_date,
        assessor=user,
    )
    log_audit_event(
        action=AuditAction.CREATE,
        resource_type='Assessment',
        resource_id=str(assessment.id),
        summary=f"Conducted {assessment.get_assessment_type_display()} for {patient.full_name}",
        user=user,
        metadata={'assessment_type': assessment_type, 'pain_score': pain_score, 'pps_score': pps_score}
    )
    return assessment


@transaction.atomic
def amend_assessment(*, assessment: Assessment, reason_for_amendment: str, updated_summary: str, user=None) -> AssessmentAmendment:
    previous_content = assessment.clinical_summary
    amendment = AssessmentAmendment.objects.create(
        assessment=assessment,
        amended_by=user,
        reason_for_amendment=reason_for_amendment,
        previous_content=previous_content,
        amended_notes=updated_summary,
    )
    assessment.clinical_summary = f"{updated_summary}\n\n[AMENDMENT on {amendment.amended_at.strftime('%d %b %Y %H:%M')} by {user.display_name if user else 'Staff'}]: {reason_for_amendment}"
    assessment.save()

    log_audit_event(
        action=AuditAction.AMEND,
        resource_type='Assessment',
        resource_id=str(assessment.id),
        summary=f"Amended clinical assessment {assessment.id} for {assessment.patient.full_name}. Reason: {reason_for_amendment}",
        user=user,
    )
    return amendment
