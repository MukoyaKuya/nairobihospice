from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.patients.models import Patient

from .models import Encounter, EncounterTypeChoices


@transaction.atomic
def record_encounter(*, patient: Patient, encounter_type: EncounterTypeChoices, reason: str, clinical_notes: str, location: str = '', interventions_performed: str = '', next_followup_date=None, next_followup_plan: str = '', user=None) -> Encounter:
    episode = patient.episodes.filter(status='ACTIVE').first()
    encounter = Encounter.objects.create(
        patient=patient,
        episode=episode,
        encounter_type=encounter_type,
        reason=reason,
        clinical_notes=clinical_notes,
        location=location or ('Nairobi Hospice Clinic' if encounter_type == EncounterTypeChoices.CLINIC_VISIT else patient.address or 'Home'),
        interventions_performed=interventions_performed,
        next_followup_date=next_followup_date,
        next_followup_plan=next_followup_plan,
        recorded_by=user,
    )
    log_audit_event(
        action=AuditAction.CREATE,
        resource_type='Encounter',
        resource_id=str(encounter.id),
        summary=f"Recorded {encounter.get_encounter_type_display()} for {patient.full_name}",
        user=user,
    )
    return encounter
