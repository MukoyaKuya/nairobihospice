from datetime import date

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.notifications.services import notify_clinical_team_of_new_patient

from .models import Caregiver, NextOfKin, Patient, PatientStatusChoices


def generate_hospice_number() -> str:
    """
    Generates formatted Hospice ID: NH-YYYY-XXXX (e.g. NH-2026-0001).
    """
    year = timezone.now().year
    prefix = f"NH-{year}-"
    last_patient = Patient.objects.filter(hospice_number__startswith=prefix).order_by('-hospice_number').first()
    if last_patient and last_patient.hospice_number:
        try:
            seq = int(last_patient.hospice_number.split('-')[-1]) + 1
        except (ValueError, IndexError):
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


@transaction.atomic
def register_patient(
    *,
    first_name: str,
    last_name: str,
    middle_name: str = '',
    ip_op_number: str = '',
    daycare_number: str = '',
    hiv_status: str = '',
    referred_by: str = '',
    date_of_birth: date = None,
    sex: str = 'F',
    identification_type: str = 'NATIONAL_ID',
    identification_number: str = '',
    phone_number: str = '',
    alternative_phone: str = '',
    email: str = '',
    address: str = '',
    county: str = 'Nairobi',
    sub_county: str = '',
    ward: str = '',
    landmark: str = '',
    preferred_language: str = 'English',
    marital_status: str = 'MARRIED',
    religion: str = '',
    occupation: str = '',
    primary_diagnosis: str = '',
    allergies: str = '',
    clinical_alerts: str = '',
    notes: str = '',
    created_by=None,
    nok_name: str = '',
    nok_relationship: str = '',
    nok_phone: str = '',
    nok_address: str = '',
    nok_age: int = None,
    nok_gender: str = '',
    caregiver_name: str = '',
    caregiver_relationship: str = '',
    caregiver_phone: str = '',
    caregiver_address: str = '',
    caregiver_age: int = None,
    caregiver_gender: str = '',
    caregiver_notes: str = '',
    chief_complaint: str = '',
    past_medical_history: str = '',
    family_history: str = '',
    drug_history: str = '',
    primary_nurse=None,
    primary_doctor=None,
) -> Patient:
    """
    Registers a new patient, generates unique identifier, and records next of kin / caregiver.
    """
    patient_fields = {
        'first_name': first_name,
        'middle_name': middle_name,
        'last_name': last_name,
        'ip_op_number': ip_op_number,
        'daycare_number': daycare_number,
        'hiv_status': hiv_status,
        'referred_by': referred_by,
        'date_of_birth': date_of_birth,
        'sex': sex,
        'identification_type': identification_type,
        'identification_number': identification_number,
        'phone_number': phone_number,
        'alternative_phone': alternative_phone,
        'email': email,
        'address': address,
        'county': county,
        'sub_county': sub_county,
        'ward': ward,
        'landmark': landmark,
        'preferred_language': preferred_language,
        'marital_status': marital_status,
        'religion': religion,
        'occupation': occupation,
        'primary_diagnosis': primary_diagnosis,
        'allergies': allergies,
        'clinical_alerts': clinical_alerts,
        'notes': notes,
        'status': PatientStatusChoices.ACTIVE,
        'registration_date': timezone.now().date(),
        'created_by': created_by,
    }
    # The unique constraint is the final arbiter under concurrency; retry after a collision.
    for attempt in range(5):
        hospice_number = generate_hospice_number()
        try:
            with transaction.atomic():
                patient = Patient.objects.create(hospice_number=hospice_number, **patient_fields)
            break
        except IntegrityError:
            if attempt == 4:
                raise

    if nok_name and (nok_phone or nok_address):
        NextOfKin.objects.create(
            patient=patient,
            name=nok_name,
            relationship=nok_relationship or 'Next of Kin',
            phone_number=nok_phone,
            address=nok_address,
            age=nok_age,
            gender=nok_gender,
            is_primary=True,
        )

    if caregiver_name and (caregiver_phone or caregiver_address):
        Caregiver.objects.create(
            patient=patient,
            name=caregiver_name,
            relationship=caregiver_relationship or 'Primary Caregiver',
            phone_number=caregiver_phone,
            address=caregiver_address,
            age=caregiver_age,
            gender=caregiver_gender,
            notes=caregiver_notes,
            is_primary=True,
        )

    # If medical history was provided during registration, create initial Assessment record
    med_hist_parts = []
    if chief_complaint:
        med_hist_parts.append(f"Chief Complaint: {chief_complaint}")
    if past_medical_history:
        med_hist_parts.append(f"Past Medical & Surgical History: {past_medical_history}")
    if family_history:
        med_hist_parts.append(f"Family History: {family_history}")
    if drug_history:
        med_hist_parts.append(f"Drug History: {drug_history}")

    if med_hist_parts:
        from apps.assessments.models import Assessment, AssessmentTypeChoices
        Assessment.objects.create(
            patient=patient,
            assessment_type=AssessmentTypeChoices.INITIAL,
            assessment_date=patient.registration_date or timezone.now().date(),
            clinical_summary="\n".join(med_hist_parts),
            assessor=created_by,
        )

    # Automatically initialize active Episode of Care and multidisciplinary care team
    from apps.care.models import CareTeamMember, CareTeamRoleChoices, EpisodeOfCare, EpisodeStatusChoices
    episode = EpisodeOfCare.objects.create(
        patient=patient,
        start_date=patient.registration_date or timezone.now().date(),
        reason_for_admission=primary_diagnosis or 'Initial Palliative Registration',
        status=EpisodeStatusChoices.ACTIVE,
        created_by=created_by,
    )

    if primary_nurse:
        CareTeamMember.objects.create(
            episode=episode,
            staff_member=primary_nurse,
            role=CareTeamRoleChoices.PRIMARY_NURSE,
            is_primary=True,
            start_date=episode.start_date,
        )
    if primary_doctor:
        CareTeamMember.objects.create(
            episode=episode,
            staff_member=primary_doctor,
            role=CareTeamRoleChoices.PRIMARY_DOCTOR,
            is_primary=True,
            start_date=episode.start_date,
        )

    log_audit_event(
        action=AuditAction.CREATE,
        resource_type='Patient',
        resource_id=str(patient.id),
        summary=f"Registered new patient {patient.full_name} ({patient.hospice_number})",
        user=created_by,
        metadata={'hospice_number': patient.hospice_number, 'diagnosis': primary_diagnosis}
    )

    # Never publish a notification/webhook for a transaction that later rolls
    # back. The callback also keeps outbound work outside the DB transaction.
    transaction.on_commit(
        lambda: notify_clinical_team_of_new_patient(patient=patient, registered_by=created_by)
    )

    return patient


@transaction.atomic
def update_patient_demographics(*, patient: Patient, user=None, **fields) -> Patient:
    for key, value in fields.items():
        if hasattr(patient, key) and value is not None:
            setattr(patient, key, value)
    patient.save()

    log_audit_event(
        action=AuditAction.UPDATE,
        resource_type='Patient',
        resource_id=str(patient.id),
        summary=f"Updated demographic/clinical details for patient {patient.full_name} ({patient.hospice_number})",
        user=user,
    )
    return patient


@transaction.atomic
def discharge_patient(*, patient: Patient, reason: str, discharge_date: date = None, user=None) -> Patient:
    patient.status = PatientStatusChoices.DISCHARGED
    patient.discharge_date = discharge_date or timezone.now().date()
    patient.discharge_reason = reason
    patient.save()

    log_audit_event(
        action=AuditAction.UPDATE,
        resource_type='Patient',
        resource_id=str(patient.id),
        summary=f"Discharged patient {patient.full_name} ({patient.hospice_number}). Reason: {reason}",
        user=user,
    )
    return patient


@transaction.atomic
def record_patient_death(*, patient: Patient, date_of_death: date, place_of_death: str = '', cause_of_death: str = '', user=None) -> Patient:
    patient.status = PatientStatusChoices.DECEASED
    patient.date_of_death = date_of_death
    patient.place_of_death = place_of_death
    patient.cause_of_death = cause_of_death
    patient.save()

    log_audit_event(
        action=AuditAction.UPDATE,
        resource_type='Patient',
        resource_id=str(patient.id),
        summary=f"Recorded death of patient {patient.full_name} ({patient.hospice_number}) on {date_of_death}",
        user=user,
    )
    return patient
