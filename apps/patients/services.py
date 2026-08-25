from datetime import date

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.accounts.models import RoleChoices
from apps.assessments.models import Assessment, AssessmentTypeChoices
from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.care.models import CareTeamMember, CareTeamRoleChoices, EpisodeOfCare, EpisodeStatusChoices
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


def generate_next_ip_op_number() -> str:
    """
    Calculates the next sequential Hospital IP/OP file number for current year based on most recent patient (e.g. 146/26 -> 147/26).
    """
    import re
    now = timezone.now()
    year_2digit = now.strftime('%y')
    year_4digit = str(now.year)
    max_seq = 0

    for ip in Patient.objects.exclude(ip_op_number='').values_list('ip_op_number', flat=True):
        if not ip:
            continue
        match = re.match(r'^(\d+)\s*/\s*(\d+)$', ip.strip())
        if match:
            num, yr = int(match.group(1)), match.group(2)
            if yr in (year_2digit, year_4digit):
                if num > max_seq:
                    max_seq = num

    next_seq = max_seq + 1 if max_seq > 0 else 1
    return f"{next_seq}/{year_2digit}"


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
    require_care_team: bool = False,
) -> Patient:
    """
    Registers a new patient, generates unique identifier, and records next of kin / caregiver.
    """
    if require_care_team and (not primary_nurse or not primary_doctor):
        raise ValidationError("Both a primary palliative nurse and doctor must be assigned to open an active care episode.")

    # Duplicate registration guard
    fn_clean = (first_name or '').strip()
    ln_clean = (last_name or '').strip()
    id_clean = (identification_number or '').strip()
    ip_clean = (ip_op_number or '').strip()
    phone_clean = (phone_number or '').strip()

    if id_clean:
        existing_id = Patient.objects.filter(identification_number__iexact=id_clean).first()
        if existing_id:
            raise ValidationError(f"A patient with Identification Number '{id_clean}' is already registered: {existing_id.full_name} ({existing_id.hospice_number}).")

    if ip_clean:
        existing_ip = Patient.objects.filter(ip_op_number__iexact=ip_clean).first()
        if existing_ip:
            raise ValidationError(f"A patient with Hospital IP/OP Number '{ip_clean}' is already registered: {existing_ip.full_name} ({existing_ip.hospice_number}).")

    if fn_clean and ln_clean:
        if phone_clean:
            existing_phone = Patient.objects.filter(first_name__iexact=fn_clean, last_name__iexact=ln_clean, phone_number__iexact=phone_clean).first()
            if existing_phone:
                raise ValidationError(f"Duplicate registration detected: '{fn_clean} {ln_clean}' with phone '{phone_clean}' is already registered with Hospice ID {existing_phone.hospice_number}.")
        if date_of_birth:
            existing_dob = Patient.objects.filter(first_name__iexact=fn_clean, last_name__iexact=ln_clean, date_of_birth=date_of_birth).first()
            if existing_dob:
                raise ValidationError(f"Duplicate registration detected: '{fn_clean} {ln_clean}' born {date_of_birth} is already registered with Hospice ID {existing_dob.hospice_number}.")

    assigned_ip_op = ip_clean or generate_next_ip_op_number()

    patient_fields = {
        'first_name': first_name,
        'middle_name': middle_name,
        'last_name': last_name,
        'ip_op_number': assigned_ip_op,
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
        Assessment.objects.create(
            patient=patient,
            assessment_type=AssessmentTypeChoices.INITIAL,
            assessment_date=patient.registration_date or timezone.now().date(),
            clinical_summary="\n".join(med_hist_parts),
            assessor=created_by,
        )

    # Automatically initialize active Episode of Care and multidisciplinary care team
    episode = EpisodeOfCare.objects.create(
        patient=patient,
        start_date=patient.registration_date or timezone.now().date(),
        reason_for_admission=primary_diagnosis or 'Initial Palliative Registration',
        status=EpisodeStatusChoices.ACTIVE,
        created_by=created_by,
    )

    assigned_nurse = primary_nurse
    assigned_doctor = primary_doctor
    if not assigned_nurse and created_by and hasattr(created_by, 'staff_profile') and created_by.staff_profile and created_by.staff_profile.role == RoleChoices.NURSE:
        assigned_nurse = created_by.staff_profile
    if not assigned_doctor and created_by and hasattr(created_by, 'staff_profile') and created_by.staff_profile and created_by.staff_profile.role in [RoleChoices.DOCTOR, RoleChoices.CLINICAL_OFFICER]:
        assigned_doctor = created_by.staff_profile

    if assigned_nurse:
        CareTeamMember.objects.create(
            episode=episode,
            staff_member=assigned_nurse,
            role=CareTeamRoleChoices.PRIMARY_NURSE,
            is_primary=True,
            start_date=episode.start_date,
        )
    if assigned_doctor:
        CareTeamMember.objects.create(
            episode=episode,
            staff_member=assigned_doctor,
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
