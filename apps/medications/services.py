from django.db import transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.patients.models import Patient

from .models import MedicationStatement, MedicationStatusChoices, RouteChoices


@transaction.atomic
def prescribe_medication(
    *,
    patient: Patient,
    medication_name: str,
    dosage: str,
    route: RouteChoices = RouteChoices.ORAL,
    frequency: str,
    indication: str = '',
    instructions_for_caregiver: str = '',
    start_date=None,
    user=None,
) -> MedicationStatement:
    med = MedicationStatement.objects.create(
        patient=patient,
        medication_name=medication_name,
        dosage=dosage,
        route=route,
        frequency=frequency,
        indication=indication,
        instructions_for_caregiver=instructions_for_caregiver,
        start_date=start_date or timezone.now().date(),
        status=MedicationStatusChoices.ACTIVE,
        prescriber=user,
        prescriber_name=user.display_name if user else '',
    )
    log_audit_event(
        action=AuditAction.CREATE,
        resource_type='Medication',
        resource_id=str(med.id),
        summary=f"Prescribed/Recorded {med.medication_name} ({dosage}, {med.get_route_display()}) for {patient.full_name}",
        user=user,
    )
    return med


@transaction.atomic
def update_medication_status(*, medication: MedicationStatement, status: MedicationStatusChoices, reason: str = '', user=None) -> MedicationStatement:
    medication.status = status
    if status in [MedicationStatusChoices.DISCONTINUED, MedicationStatusChoices.COMPLETED]:
        medication.end_date = timezone.now().date()
    if reason:
        medication.discontinuation_reason = reason
    medication.save()

    log_audit_event(
        action=AuditAction.UPDATE,
        resource_type='Medication',
        resource_id=str(medication.id),
        summary=f"Changed medication status for {medication.medication_name} ({medication.patient.full_name}) to {medication.get_status_display()}. Reason: {reason}",
        user=user,
    )
    return medication
