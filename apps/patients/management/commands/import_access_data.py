import os
from datetime import date, datetime

import pyodbc
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.appointments.models import Appointment, AppointmentStatusChoices, AppointmentTypeChoices
from apps.assessments.models import Assessment, AssessmentTypeChoices
from apps.encounters.models import Encounter, EncounterTypeChoices
from apps.medications.models import MedicationStatement, MedicationStatusChoices, RouteChoices
from apps.patients.models import (
    Caregiver,
    NextOfKin,
    Patient,
    PatientStatusChoices,
    SexChoices,
)
from apps.symptoms.models import SymptomAssessmentRecord, SymptomScore, SymptomTypeChoices


class Command(BaseCommand):
    help = 'Import historical patients, clinical encounters, prescriptions, and history from legacy MS Access database (.accdb / .mdb)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--db-path',
            type=str,
            default=r"C:\Users\Little Human\Desktop\NairobiHospice Access\Hospice V6.0_be.accdb",
            help='Path to the MS Access .accdb or .mdb file'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Perform a dry run without committing database changes'
        )
        parser.add_argument(
            '--limit',
            type=int,
            default=None,
            help='Limit the number of patients to import (for testing)'
        )

    def handle(self, *args, **options):
        db_path = options['db_path']
        is_dry_run = options['dry_run']
        limit = options['limit']

        if not os.path.exists(db_path):
            self.stderr.write(self.style.ERROR(f"Database file not found: {db_path}"))
            return

        self.stdout.write(self.style.NOTICE("\n======================================================="))
        self.stdout.write(self.style.NOTICE(" NAIROBI HOSPICE PCMS: MS ACCESS DATA MIGRATION"))
        self.stdout.write(self.style.NOTICE(f" Source: {db_path}"))
        self.stdout.write(self.style.NOTICE(f" Mode: {'DRY RUN (No changes saved)' if is_dry_run else 'LIVE IMPORT (Saving to DB)'}"))
        self.stdout.write(self.style.NOTICE("=======================================================\n"))

        conn_str = f"DRIVER={{Microsoft Access Driver (*.mdb, *.accdb)}};DBQ={db_path};"
        try:
            conn = pyodbc.connect(conn_str)
        except Exception as e:
            self.stderr.write(self.style.ERROR(f"Failed to connect to MS Access database: {e}"))
            return

        cursor = conn.cursor()

        # Get system creator user and default staff profile
        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()
        from apps.accounts.models import StaffProfile
        default_staff = StaffProfile.objects.filter(user=admin_user).first() or StaffProfile.objects.first()
        if not default_staff and admin_user:
            default_staff = StaffProfile.objects.create(user=admin_user, role='DOCTOR', department='Clinical Services')

        try:
            with transaction.atomic():
                # -------------------------------------------------------------
                # 1. Import Patients, Next of Kin & Caregivers
                # -------------------------------------------------------------
                imported_patients_count = 0
                updated_patients_count = 0
                nok_count = 0
                cg_count = 0
                patient_map = {}  # legacy_id -> Patient instance

                query = "SELECT * FROM [Patients Database] WHERE [Patient ID] IS NOT NULL"
                cursor.execute(query)
                columns = [col[0] for col in cursor.description]
                raw_patients = cursor.fetchall()

                if limit:
                    raw_patients = raw_patients[:limit]

                self.stdout.write(f"Found {len(raw_patients)} patient records in MS Access. Processing...")

                for row in raw_patients:
                    r = {columns[i]: row[i] for i in range(len(columns))}

                    legacy_id = r.get('Patient ID')
                    if not legacy_id:
                        continue

                    pid_str = str(legacy_id)
                    if len(pid_str) >= 5:
                        year = pid_str[:4]
                        seq = int(pid_str[4:])
                        hospice_num = f"NH-{year}-{seq:04d}"
                    else:
                        hospice_num = f"NH-LEG-{pid_str}"

                    # Names
                    first_name = (r.get('First Name') or '').strip().title() or 'Unknown'
                    surname = (r.get('SurName') or '').strip().title()
                    last_name = (r.get('Last Name') or '').strip().title()
                    if not last_name:
                        last_name = surname or 'Patient'
                        middle_name = ''
                    else:
                        middle_name = surname

                    # Sex
                    sex_raw = (r.get('Sex') or '').strip().upper()
                    if sex_raw == 'MALE' or sex_raw == 'M':
                        sex = SexChoices.MALE
                    elif sex_raw == 'FEMALE' or sex_raw == 'F':
                        sex = SexChoices.FEMALE
                    else:
                        sex = SexChoices.UNKNOWN

                    # Phone Number
                    phone_raw = r.get('Mobile Phone')
                    phone_str = ''
                    if phone_raw:
                        p_digits = str(phone_raw).strip()
                        if len(p_digits) >= 9:
                            if p_digits.startswith('254'):
                                phone_str = f"+{p_digits}"
                            elif p_digits.startswith('0'):
                                phone_str = f"+254 {p_digits[1:]}"
                            elif p_digits.startswith('7') or p_digits.startswith('1'):
                                phone_str = f"+254 {p_digits}"
                            else:
                                phone_str = p_digits
                        else:
                            phone_str = p_digits

                    # Address & Location
                    address_str = (r.get('Residential Address') or '').strip().title()
                    county = 'Nairobi'

                    # Registration Date
                    reg_date = r.get('Enrollment Date')
                    if isinstance(reg_date, datetime):
                        reg_date_val = reg_date.date()
                    elif isinstance(reg_date, date):
                        reg_date_val = reg_date
                    else:
                        reg_date_val = date(2016, 1, 1)

                    # Age & DOB calculation
                    age_val = r.get('Age')
                    dob_val = None
                    is_approx_dob = False
                    if age_val and isinstance(age_val, int) and 0 < age_val < 120:
                        dob_year = max(1900, reg_date_val.year - age_val)
                        dob_val = date(dob_year, 1, 1)
                        is_approx_dob = True

                    # Patient Status
                    status_raw = (r.get('Patient Status') or '').strip().upper()
                    date_of_death_val = r.get('Date of Death')
                    if isinstance(date_of_death_val, datetime):
                        date_of_death_val = date_of_death_val.date()

                    cause_of_death = (r.get('Cause of Death') or '').strip()

                    if date_of_death_val or 'DECEASED' in status_raw or 'DEATH' in status_raw:
                        patient_status = PatientStatusChoices.DECEASED
                    elif 'CLOSED' in status_raw or 'DISCHARGE' in status_raw:
                        patient_status = PatientStatusChoices.DISCHARGED
                    else:
                        patient_status = PatientStatusChoices.ACTIVE

                    # Clinical diagnosis & notes
                    diagnosis = (r.get('Diagnosis') or '').strip()
                    app_notes = (r.get('Appointment Notes') or '').strip()
                    add_notes = (r.get('Additional Notes') or '').strip()
                    spec_remarks = (r.get('Special Remarks') or '').strip()
                    other_notes = (r.get('Other Notes') or '').strip()
                    referred_by = (r.get('Reffered By') or '').strip()
                    hiv_status = (r.get('HIV /RVD Status') or '').strip()
                    ip_op_no = (r.get('IP/OP No') or '').strip()

                    clinical_notes_parts = []
                    if ip_op_no:
                        clinical_notes_parts.append(f"Legacy IP/OP No: {ip_op_no}")
                    if diagnosis:
                        clinical_notes_parts.append(f"Legacy Diagnosis: {diagnosis}")
                    if referred_by:
                        clinical_notes_parts.append(f"Referred By: {referred_by}")
                    if hiv_status:
                        clinical_notes_parts.append(f"HIV/RVD Status: {hiv_status}")
                    if app_notes:
                        clinical_notes_parts.append(f"Appointment Notes: {app_notes}")
                    if add_notes:
                        clinical_notes_parts.append(f"Additional Notes: {add_notes}")
                    if spec_remarks:
                        clinical_notes_parts.append(f"Special Remarks: {spec_remarks}")
                    if other_notes:
                        clinical_notes_parts.append(f"Other Notes: {other_notes}")

                    combined_notes = "\n".join(clinical_notes_parts)

                    daycare_no = (r.get('Daycare No') or '').strip()

                    patient_defaults = {
                        'first_name': first_name,
                        'middle_name': middle_name,
                        'last_name': last_name,
                        'sex': sex,
                        'ip_op_number': ip_op_no,
                        'daycare_number': daycare_no,
                        'hiv_status': hiv_status,
                        'referred_by': referred_by,
                        'date_of_birth': dob_val,
                        'is_approximate_dob': is_approx_dob,
                        'phone_number': phone_str,
                        'address': address_str,
                        'county': county,
                        'primary_diagnosis': diagnosis,
                        'status': patient_status,
                        'registration_date': reg_date_val,
                        'date_of_death': date_of_death_val,
                        'cause_of_death': cause_of_death,
                        'notes': combined_notes,
                        'created_by': admin_user,
                    }

                    patient, created = Patient.objects.update_or_create(
                        hospice_number=hospice_num,
                        defaults=patient_defaults
                    )

                    if created:
                        imported_patients_count += 1
                    else:
                        updated_patients_count += 1

                    patient_map[legacy_id] = patient

                    # Next of Kin
                    nok_name = (r.get('Next Of Kin Name') or '').strip().title()
                    nok_phone_raw = r.get('Next of Kin Contacts')
                    nok_rel = (r.get('NOK Relationship') or '').strip() or 'Family Member'
                    nok_residence = (r.get('Next of Kin Residence') or '').strip()
                    nok_gender = (r.get('NOK Gender') or '').strip()
                    nok_age_raw = r.get('NOK Age')
                    nok_age = None
                    if nok_age_raw:
                        try:
                            nok_age = int(str(nok_age_raw).strip())
                        except ValueError:
                            nok_age = None

                    if nok_name:
                        nok_phone = ''
                        if nok_phone_raw:
                            np_digits = str(nok_phone_raw).strip()
                            if len(np_digits) >= 9:
                                nok_phone = f"+254 {np_digits}" if not np_digits.startswith('+') else np_digits
                            else:
                                nok_phone = np_digits

                        NextOfKin.objects.update_or_create(
                            patient=patient,
                            name=nok_name,
                            defaults={
                                'relationship': nok_rel,
                                'phone_number': nok_phone,
                                'address': nok_residence,
                                'gender': nok_gender,
                                'age': nok_age,
                                'is_primary': True,
                            }
                        )
                        nok_count += 1

                    # Caregiver
                    cg_name = (r.get('CG FirsName') or '').strip().title()
                    cg_phone_raw = r.get('CG Contacts')
                    cg_rel = (r.get('CG Relationship') or '').strip() or 'Caregiver'
                    cg_residence = (r.get('CG Residence') or '').strip()
                    cg_notes = (r.get('CG Notes') or '').strip()
                    cg_gender = (r.get('CG Gender') or '').strip()
                    cg_age_raw = r.get('CG Age')
                    cg_age = None
                    if cg_age_raw:
                        try:
                            cg_age = int(str(cg_age_raw).strip())
                        except ValueError:
                            cg_age = None

                    if cg_name:
                        cg_phone = ''
                        if cg_phone_raw:
                            cgp_digits = str(cg_phone_raw).strip()
                            if len(cgp_digits) >= 9:
                                cg_phone = f"+254 {cgp_digits}" if not cgp_digits.startswith('+') else cgp_digits
                            else:
                                cg_phone = cgp_digits

                        Caregiver.objects.update_or_create(
                            patient=patient,
                            name=cg_name,
                            defaults={
                                'relationship': cg_rel,
                                'phone_number': cg_phone,
                                'address': cg_residence,
                                'gender': cg_gender,
                                'age': cg_age,
                                'notes': cg_notes,
                                'is_primary': True,
                            }
                        )
                        cg_count += 1

                self.stdout.write(self.style.SUCCESS(
                    f"Patients Processed: {imported_patients_count} new created, {updated_patients_count} updated. Next of Kin: {nok_count}, Caregivers: {cg_count}."
                ))

                # -------------------------------------------------------------
                # 2. Import Appointments, Encounters & ESAS Symptoms
                # -------------------------------------------------------------
                imported_encounters_count = 0
                imported_esas_count = 0
                imported_appts_count = 0

                cursor.execute("SELECT * FROM [Appointments] WHERE [Patient ID] IS NOT NULL")
                appt_columns = [col[0] for col in cursor.description]
                raw_appts = cursor.fetchall()

                self.stdout.write(f"Found {len(raw_appts)} appointment & encounter records in MS Access. Processing...")

                for row in raw_appts:
                    a = {appt_columns[i]: row[i] for i in range(len(appt_columns))}
                    p_id = a.get('Patient ID')
                    patient = patient_map.get(p_id)
                    if not patient:
                        if p_id:
                            pid_s = str(p_id)
                            h_num = f"NH-{pid_s[:4]}-{int(pid_s[4:]):04d}" if len(pid_s) >= 5 else f"NH-LEG-{pid_s}"
                            patient = Patient.objects.filter(hospice_number=h_num).first()

                    if not patient:
                        continue

                    appt_date = a.get('Appointment Date')
                    if isinstance(appt_date, datetime):
                        appt_date_val = appt_date.date()
                    elif isinstance(appt_date, date):
                        appt_date_val = appt_date
                    else:
                        appt_date_val = patient.registration_date

                    doctor_name = (a.get('Doctor') or '').strip()
                    appt_type_str = (a.get('Appointment Type') or '').strip().upper()

                    if 'HOME' in appt_type_str:
                        enc_type = EncounterTypeChoices.HOME_VISIT
                        loc = 'Patient Residence (Home Visit)'
                        appt_type = AppointmentTypeChoices.HOME_VISIT
                    elif 'COUNSEL' in appt_type_str:
                        enc_type = EncounterTypeChoices.COUNSELLING
                        loc = 'Psychosocial Support Room'
                        appt_type = AppointmentTypeChoices.CLINIC_VISIT
                    else:
                        enc_type = EncounterTypeChoices.CLINIC_VISIT
                        loc = 'Nairobi Hospice Outpatient Clinic'
                        appt_type = AppointmentTypeChoices.CLINIC_VISIT

                    # Extract Clinical Details
                    treatments_done = (a.get('Treatment Done') or a.get('Treatment1') or '').strip()
                    pain_score_raw = a.get('Pain Score')
                    triage_notes = (a.get('Triage Notes') or '').strip()
                    comments = (a.get('Comments') or '').strip()

                    # Vitals
                    bp_systolic = a.get('Systolic')
                    bp_diastolic = a.get('Diastolic')
                    pulse = a.get('Pulse Rate')
                    temp = a.get('Temparature')
                    spo2 = a.get('spO2')
                    weight = a.get('Weight') or a.get('weight')

                    vitals_parts = []
                    if bp_systolic and bp_diastolic:
                        vitals_parts.append(f"BP: {bp_systolic}/{bp_diastolic} mmHg")
                    if pulse:
                        vitals_parts.append(f"Pulse: {pulse} bpm")
                    if temp:
                        vitals_parts.append(f"Temp: {temp}°C")
                    if spo2:
                        vitals_parts.append(f"SpO2: {spo2}%")
                    if weight:
                        vitals_parts.append(f"Weight: {weight} kg")

                    vitals_summary = " | ".join(vitals_parts) if vitals_parts else "Vitals not recorded"

                    # Symptoms
                    symptoms_list = [
                        a.get(f'Symptom{i}') for i in range(1, 6) if a.get(f'Symptom{i}')
                    ]
                    other_symptom = a.get('Other Symptom')
                    if other_symptom:
                        symptoms_list.append(str(other_symptom))

                    symptoms_text = ", ".join(symptoms_list) if symptoms_list else "None noted"

                    # Care & Nursing Interventions
                    interventions = []
                    if a.get('Wound Care'):
                        interventions.append('Wound Care & Dressing')
                    if a.get('Mouth Care'):
                        interventions.append('Oral Hygiene & Mouth Care')
                    if a.get('Bathing Assistance'):
                        interventions.append('Bathing Assistance')
                    if a.get('Positioning Assistance'):
                        interventions.append('Pressure Area & Positioning Care')
                    if a.get('Counseling'):
                        interventions.append('Psychosocial / Family Counseling')
                    if a.get('Morphine'):
                        morphine_type = a.get('TypeOfMorphine') or 'Oral Morphine'
                        tablets = a.get('Morphine Tablets')
                        amt = a.get('Amount Given (mL)')
                        interventions.append(f"Morphine Administration ({morphine_type}, Tabs: {tablets}, Given: {amt}mL)")

                    interventions_summary = "; ".join(interventions) if interventions else treatments_done or "Clinical Consultation"

                    notes_lines = [
                        f"Legacy Clinician: {doctor_name or 'Nairobi Hospice Clinical Team'}",
                        f"Vitals: {vitals_summary}",
                        f"Reported Symptoms: {symptoms_text}",
                    ]
                    if triage_notes:
                        notes_lines.append(f"Triage Notes: {triage_notes}")
                    if comments:
                        notes_lines.append(f"Clinician Comments: {comments}")

                    full_clinical_notes = "\n".join(notes_lines)

                    encounter = Encounter.objects.create(
                        patient=patient,
                        encounter_type=enc_type,
                        encounter_date=appt_date_val,
                        location=loc,
                        reason=treatments_done or f"Palliative review ({patient.primary_diagnosis or 'Routine follow-up'})",
                        clinical_notes=full_clinical_notes,
                        interventions_performed=interventions_summary,
                        recorded_by=admin_user,
                    )
                    imported_encounters_count += 1

                    # Create ESAS / Symptom assessment
                    numeric_pain = 0
                    if pain_score_raw:
                        try:
                            numeric_pain = min(10, max(0, int(str(pain_score_raw).strip())))
                        except ValueError:
                            numeric_pain = 0

                    if numeric_pain > 0 or symptoms_list:
                        esas_rec = SymptomAssessmentRecord.objects.create(
                            patient=patient,
                            encounter=encounter,
                            recorded_at=timezone.make_aware(datetime.combine(appt_date_val, datetime.min.time())),
                            total_distress_score=numeric_pain * 2,
                            clinical_notes=f"Symptoms noted: {symptoms_text}. Pain: {numeric_pain}/10",
                            recorded_by=admin_user,
                        )
                        if numeric_pain > 0:
                            SymptomScore.objects.create(
                                record=esas_rec,
                                symptom_type=SymptomTypeChoices.PAIN,
                                score=numeric_pain,
                                notes='Historical pain severity score'
                            )
                        imported_esas_count += 1

                    # Also create appointment record for historical scheduling
                    if default_staff:
                        Appointment.objects.get_or_create(
                            patient=patient,
                            scheduled_date=appt_date_val,
                            defaults={
                                'staff_member': default_staff,
                                'appointment_type': appt_type,
                                'location': loc,
                                'reason': treatments_done or 'Palliative follow-up appointment',
                                'status': AppointmentStatusChoices.COMPLETED,
                                'outcome_notes': f"Attended on {appt_date_val}. {interventions_summary}",
                                'created_by': admin_user,
                            }
                        )
                        imported_appts_count += 1

                self.stdout.write(self.style.SUCCESS(
                    f"Appointments & Encounters Processed: {imported_encounters_count} encounters, {imported_esas_count} ESAS assessments, {imported_appts_count} appointments."
                ))

                # -------------------------------------------------------------
                # 3. Import Prescriptions & Medication Statements
                # -------------------------------------------------------------
                imported_meds_count = 0
                cursor.execute("SELECT * FROM [Prescriptions] WHERE [Patient ID] IS NOT NULL")
                rx_columns = [col[0] for col in cursor.description]
                raw_rxs = cursor.fetchall()

                self.stdout.write(f"Found {len(raw_rxs)} prescription records in MS Access. Processing...")

                for row in raw_rxs:
                    rx = {rx_columns[i]: row[i] for i in range(len(rx_columns))}
                    p_id = rx.get('Patient ID')
                    patient = patient_map.get(p_id)
                    if not patient and p_id:
                        pid_s = str(p_id)
                        h_num = f"NH-{pid_s[:4]}-{int(pid_s[4:]):04d}" if len(pid_s) >= 5 else f"NH-LEG-{pid_s}"
                        patient = Patient.objects.filter(hospice_number=h_num).first()

                    if not patient:
                        continue

                    rx_date = rx.get('Prescription Date')
                    if isinstance(rx_date, datetime):
                        rx_date_val = rx_date.date()
                    elif isinstance(rx_date, date):
                        rx_date_val = rx_date
                    else:
                        rx_date_val = patient.registration_date

                    for d_idx in range(1, 8):
                        drug_name = rx.get(f'DRUG{d_idx}')
                        if drug_name and str(drug_name).strip():
                            dosage = rx.get(f'Dosage{d_idx}') or 'As directed'
                            duration = rx.get(f'Duration{d_idx}') or ''
                            dtype = rx.get(f'Type{d_idx}') or 'Oral'

                            route = RouteChoices.ORAL
                            if 'INJECTION' in str(dtype).upper() or 'INJ' in str(drug_name).upper():
                                route = RouteChoices.SUBCUTANEOUS
                            elif 'TOPICAL' in str(dtype).upper():
                                route = RouteChoices.TOPICAL

                            MedicationStatement.objects.create(
                                patient=patient,
                                medication_name=str(drug_name).strip(),
                                dosage=str(dosage).strip(),
                                route=route,
                                frequency=str(duration).strip() or 'Daily',
                                indication=f"Prescribed on {rx_date_val}",
                                start_date=rx_date_val,
                                status=MedicationStatusChoices.COMPLETED,
                                prescriber=admin_user,
                                prescriber_name='Nairobi Hospice Medical Officer',
                                instructions_for_caregiver=f"Type: {dtype}. Duration: {duration}",
                            )
                            imported_meds_count += 1

                self.stdout.write(self.style.SUCCESS(
                    f"Prescriptions Processed: {imported_meds_count} medication statements created."
                ))

                # -------------------------------------------------------------
                # 4. Import Patient Clinical History Records
                # -------------------------------------------------------------
                imported_history_count = 0
                cursor.execute("SELECT * FROM [patients history] WHERE [History ID] IS NOT NULL")
                hist_columns = [col[0] for col in cursor.description]
                raw_hist = cursor.fetchall()

                self.stdout.write(f"Found {len(raw_hist)} patient history records in MS Access. Processing...")

                for row in raw_hist:
                    h = {hist_columns[i]: row[i] for i in range(len(hist_columns))}
                    h_id = h.get('History ID')
                    patient = patient_map.get(h_id)
                    if not patient and h_id:
                        pid_s = str(h_id)
                        h_num = f"NH-{pid_s[:4]}-{int(pid_s[4:]):04d}" if len(pid_s) >= 5 else f"NH-LEG-{pid_s}"
                        patient = Patient.objects.filter(hospice_number=h_num).first()

                    if not patient:
                        continue

                    h_summary_parts = []
                    if h.get('C/C'):
                        h_summary_parts.append(f"Chief Complaint: {h.get('C/C')}")
                    if h.get('History of Presenting Illness'):
                        h_summary_parts.append(f"History of Presenting Illness: {h.get('History of Presenting Illness')}")
                    if h.get('History of past illness'):
                        h_summary_parts.append(f"Past Medical History: {h.get('History of past illness')}")
                    if h.get('Familial history'):
                        h_summary_parts.append(f"Family History: {h.get('Familial history')}")
                    if h.get('Drug History'):
                        h_summary_parts.append(f"Past Drug History: {h.get('Drug History')}")
                    if h.get('On Examination'):
                        h_summary_parts.append(f"Physical Examination: {h.get('On Examination')}")
                    if h.get('Radiological Examination'):
                        h_summary_parts.append(f"Radiology Findings: {h.get('Radiological Examination')}")
                    if h.get('Investigation results'):
                        h_summary_parts.append(f"Lab Investigations: {h.get('Investigation results')}")
                    if h.get('Confirm Diagnosis') or h.get('Provisional Diagnosis'):
                        h_summary_parts.append(f"Confirmed Diagnosis: {h.get('Confirm Diagnosis') or h.get('Provisional Diagnosis')}")

                    if h_summary_parts:
                        Assessment.objects.create(
                            patient=patient,
                            assessment_type=AssessmentTypeChoices.INITIAL,
                            assessment_date=patient.registration_date,
                            clinical_summary="\n".join(h_summary_parts),
                            assessor=admin_user,
                        )
                        imported_history_count += 1

                self.stdout.write(self.style.SUCCESS(
                    f"Patient History Processed: {imported_history_count} initial clinical assessments created."
                ))

                if is_dry_run:
                    raise RuntimeError("DRY_RUN_COMPLETE_ROLLBACK")

        except RuntimeError as e:
            if str(e) == "DRY_RUN_COMPLETE_ROLLBACK":
                self.stdout.write(self.style.WARNING("\n[DRY RUN COMPLETE] All database transactions successfully rolled back without modifying live data."))
            else:
                raise e
        finally:
            cursor.close()
            conn.close()

        self.stdout.write(self.style.SUCCESS("\n======================================================="))
        self.stdout.write(self.style.SUCCESS(" MIGRATION SUCCESSFUL!"))
        self.stdout.write(self.style.SUCCESS(f" Total Patients: {Patient.objects.count():,}"))
        self.stdout.write(self.style.SUCCESS(f" Total Next of Kin: {NextOfKin.objects.count():,}"))
        self.stdout.write(self.style.SUCCESS(f" Total Caregivers: {Caregiver.objects.count():,}"))
        self.stdout.write(self.style.SUCCESS(f" Total Encounters: {Encounter.objects.count():,}"))
        self.stdout.write(self.style.SUCCESS(f" Total Prescriptions: {MedicationStatement.objects.count():,}"))
        self.stdout.write(self.style.SUCCESS(f" Total Clinical Assessments: {Assessment.objects.count():,}"))
        self.stdout.write(self.style.SUCCESS("=======================================================\n"))
