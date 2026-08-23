from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.patients.models import Patient, PatientStatusChoices
from apps.patients.services import generate_hospice_number

from .models import Referral, ReferralStatusChoices


def generate_referral_number() -> str:
    year = timezone.now().year
    prefix = f"REF-{year}-"
    last_ref = Referral.objects.filter(referral_number__startswith=prefix).order_by('-referral_number').first()
    if last_ref and last_ref.referral_number:
        try:
            seq = int(last_ref.referral_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


@transaction.atomic
def create_referral(*, patient_name: str, referring_facility: str, primary_diagnosis: str, reason_for_referral: str, created_by=None, **fields) -> Referral:
    # The unique constraint is the final arbiter under concurrency; retry after a collision.
    for attempt in range(5):
        referral_number = generate_referral_number()
        try:
            with transaction.atomic():
                referral = Referral.objects.create(
                    referral_number=referral_number,
                    patient_name=patient_name,
                    referring_facility=referring_facility,
                    primary_diagnosis=primary_diagnosis,
                    reason_for_referral=reason_for_referral,
                    created_by=created_by,
                    **fields
                )
            break
        except IntegrityError:
            if attempt == 4:
                raise

    log_audit_event(
        action=AuditAction.CREATE,
        resource_type='Referral',
        resource_id=str(referral.id),
        summary=f"Logged incoming referral {referral.referral_number} for {referral.patient_name} from {referring_facility}",
        user=created_by,
    )
    return referral


@transaction.atomic
def review_referral(*, referral: Referral, reviewer, status: ReferralStatusChoices, review_notes: str = '', rejection_reason: str = '') -> Referral:
    referral.assigned_reviewer = reviewer
    referral.reviewed_at = timezone.now()
    referral.status = status
    referral.review_notes = review_notes
    if status == ReferralStatusChoices.REJECTED:
        referral.rejection_reason = rejection_reason
    referral.save()

    log_audit_event(
        action=AuditAction.UPDATE,
        resource_type='Referral',
        resource_id=str(referral.id),
        summary=f"Referral {referral.referral_number} reviewed by {reviewer.display_name}. Status changed to {referral.get_status_display()}",
        user=reviewer,
    )
    return referral


@transaction.atomic
def convert_referral_to_patient(*, referral: Referral, user=None) -> Patient:
    """
    Seamlessly converts an accepted referral into a registered patient without duplicate manual entry.
    """
    # Lock the referral row so two simultaneous conversion requests cannot
    # create duplicate patients; the loser returns the existing record.
    referral = Referral.objects.select_for_update().get(pk=referral.pk)
    if referral.status == ReferralStatusChoices.CONVERTED and referral.converted_patient_id:
        return referral.converted_patient

    # Parse names
    name_parts = referral.patient_name.strip().split()
    first_name = name_parts[0] if name_parts else 'Patient'
    last_name = name_parts[-1] if len(name_parts) > 1 else 'Unknown'
    middle_name = " ".join(name_parts[1:-1]) if len(name_parts) > 2 else ''

    hospice_number = generate_hospice_number()

    patient = Patient.objects.create(
        hospice_number=hospice_number,
        first_name=first_name,
        middle_name=middle_name,
        last_name=last_name,
        date_of_birth=referral.date_of_birth,
        sex=referral.sex,
        phone_number=referral.phone_number,
        alternative_phone=referral.alternative_phone,
        address=referral.address,
        county=referral.county,
        sub_county=referral.sub_county,
        landmark=referral.landmark,
        primary_diagnosis=referral.primary_diagnosis,
        notes=f"Converted from Referral {referral.referral_number}. Reason: {referral.reason_for_referral}\nClinical Summary: {referral.clinical_summary}",
        status=PatientStatusChoices.ACTIVE,
        registration_date=timezone.now().date(),
        created_by=user,
    )

    # Link referral to newly created patient
    referral.converted_patient = patient
    referral.status = ReferralStatusChoices.CONVERTED
    referral.save()

    # Automatically create initial EpisodeOfCare from care app
    from apps.care.models import EpisodeOfCare, EpisodeStatusChoices
    EpisodeOfCare.objects.create(
        patient=patient,
        start_date=timezone.now().date(),
        reason_for_admission=referral.reason_for_referral,
        status=EpisodeStatusChoices.ACTIVE,
        created_by=user,
    )

    log_audit_event(
        action=AuditAction.CREATE,
        resource_type='Patient',
        resource_id=str(patient.id),
        summary=f"Converted Referral {referral.referral_number} to Patient {patient.full_name} ({patient.hospice_number})",
        user=user,
    )

    from apps.notifications.services import notify_clinical_team_of_new_patient
    transaction.on_commit(
        lambda: notify_clinical_team_of_new_patient(patient=patient, registered_by=user)
    )

    return patient
