import os
from datetime import date, datetime

import pyodbc
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.encounters.models import Encounter, EncounterTypeChoices
from apps.patients.models import (
    NextOfKin,
    Patient,
    PatientStatusChoices,
    SexChoices,
)
from apps.symptoms.models import SymptomAssessmentRecord, SymptomScore, SymptomTypeChoices


class Command(BaseCommand):
    help = 'Import historical patients and clinical records from legacy MS Access database (.accdb / .mdb)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--db-path',
            type=str,
            default=r"C:\Users\Little Human\Downloads\New folder (3)\Hospice V6.0_be.accdb",
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

        # Get system creator user
        admin_user = User.objects.filter(is_superuser=True).first() or User.objects.first()

        try:
            with transaction.atomic():
                # 1. Import Patients
                imported_patients_count = 0
                updated_patients_count = 0
                nok_count = 0
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

                    clinical_notes_parts = []
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

                    patient_defaults = {
                        'first_name': first_name,
                        'middle_name': middle_name,
                        'last_name': last_name,
                        'sex': sex,
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
                                'is_primary': True,
                            }
                        )
                        nok_count += 1

                self.stdout.write(self.style.SUCCESS(
                    f"Patients Processed: {imported_patients_count} new created, {updated_patients_count} updated. Next of Kin records: {nok_count}."
                ))

                # 2. Import Appointments & Encounters
                imported_encounters_count = 0
                imported_esas_count = 0

                cursor.execute("SELECT * FROM [Appointments] WHERE [Patient ID] IS NOT NULL")
                appt_columns = [col[0] for col in cursor.description]
                raw_appts = cursor.fetchall()

                self.stdout.write(f"Found {len(raw_appts)} appointment & encounter records in MS Access. Processing...")

                for row in raw_appts:
                    a = {appt_columns[i]: row[i] for i in range(len(appt_columns))}
                    p_id = a.get('Patient ID')
                    patient = patient_map.get(p_id)
                    if not patient:
                        # Try to look up patient by formatted hospice number
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
                    elif 'COUNSEL' in appt_type_str:
                        enc_type = EncounterTypeChoices.COUNSELLING
                        loc = 'Psychosocial Support Room'
                    else:
                        enc_type = EncounterTypeChoices.CLINIC_VISIT
                        loc = 'Nairobi Hospice Outpatient Clinic'

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

                    # Notes assembly
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

                    # Create ESAS / Symptom assessment if pain score or symptoms are present
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

                self.stdout.write(self.style.SUCCESS(
                    f"Encounters Processed: {imported_encounters_count} encounters created, {imported_esas_count} ESAS symptom assessments."
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
        self.stdout.write(self.style.SUCCESS(f" Total Encounters: {Encounter.objects.count():,}"))
        self.stdout.write(self.style.SUCCESS(f" Total Next of Kin: {NextOfKin.objects.count():,}"))
        self.stdout.write(self.style.SUCCESS("=======================================================\n"))
