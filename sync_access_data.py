import os
import sys
import django
import pyodbc
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
from access_sync_guard import abort_if_production_access_sync
abort_if_production_access_sync()
django.setup()

from apps.patients.models import Patient, NextOfKin, Caregiver, PatientStatusChoices
from apps.assessments.models import Assessment, AssessmentTypeChoices
from apps.accounts.models import User

def sync_access():
    staff = User.objects.filter(is_superuser=True).first() or User.objects.first()

    conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=C:\Users\Little Human\Desktop\NairobiHospice Access\Hospice V6.0_be.accdb;'
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()
    
    cur.execute('SELECT * FROM [Patients Database]')
    cols = [c[0] for c in cur.description]
    rows = cur.fetchall()

    print(f'Syncing {len(rows)} patients from Access Database...')

    updated_patients = 0
    created_assessments = 0
    created_nok = 0
    created_cg = 0

    for r in rows:
        data = dict(zip(cols, r))
        pid = data.get('Patient ID')
        ip_op = str(data.get('IP/OP No') or '').strip()
        first_name = str(data.get('First Name') or '').strip()
        last_name = str(data.get('Last Name') or data.get('SurName') or '').strip()
        sur_name = str(data.get('SurName') or '').strip()

        # Find matching patient
        p = None
        if ip_op:
            p = Patient.objects.filter(ip_op_number__iexact=ip_op).first()
        if not p and first_name and last_name:
            p = Patient.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name).first()
        if not p and first_name and sur_name:
            p = Patient.objects.filter(first_name__iexact=first_name, last_name__iexact=sur_name).first()
        if not p and pid:
            p = Patient.objects.filter(hospice_number__icontains=str(pid)).first()

        if p:
            dx = str(data.get('Diagnosis') or '').strip()
            add_notes = str(data.get('Additional Notes') or '').strip()
            app_notes = str(data.get('Appointment Notes') or '').strip()
            other_notes = str(data.get('Other Notes') or '').strip()
            hiv = str(data.get('HIV /RVD Status') or '').strip()
            ref = str(data.get('Reffered By') or '').strip()
            spec_rem = str(data.get('Special Remarks') or '').strip()
            file_closed = str(data.get('File Closed') or '').strip()
            p_status = str(data.get('Patient Status') or '').strip().upper()
            mobile = str(data.get('Mobile Phone') or '').strip()
            residence = str(data.get('Residential Address') or '').strip()

            if dx:
                p.primary_diagnosis = dx
                p.past_medical_history = dx
            if add_notes:
                p.present_medical_notes = add_notes
                if not p.notes:
                    p.notes = add_notes
            if other_notes or app_notes:
                p.other_medical_notes = ' | '.join(filter(None, [other_notes, app_notes]))
            if hiv:
                p.hiv_status = hiv
            if ref:
                p.referred_by = ref
            if ip_op:
                p.ip_op_number = ip_op
            if file_closed:
                p.file_closed = file_closed
            if mobile and not p.phone_number:
                p.phone_number = mobile
            if residence and not p.address:
                p.address = residence

            if data.get('File Closure Date'):
                f_date = data.get('File Closure Date')
                p.closure_date = f_date.date() if hasattr(f_date, 'date') else None

            if data.get('Date of Death'):
                dod = data.get('Date of Death')
                p.date_of_death = dod.date() if hasattr(dod, 'date') else None
                p.special_remarks = 'Deceased'
                p.status = PatientStatusChoices.DECEASED
            elif spec_rem:
                p.special_remarks = spec_rem
            elif p_status in [PatientStatusChoices.ACTIVE, PatientStatusChoices.INACTIVE, PatientStatusChoices.CLOSED, PatientStatusChoices.DISCHARGED, PatientStatusChoices.DECEASED]:
                p.status = p_status

            cause_death = str(data.get('Cause of Death') or '').strip()
            if cause_death:
                p.cause_of_death = cause_death

            p.save()
            updated_patients += 1

            # Next of Kin
            nok_name = str(data.get('Next Of Kin Name') or '').strip()
            nok_rel = str(data.get('NOK Relationship') or '').strip() or 'Next of Kin'
            nok_phone = str(data.get('Next of Kin Contacts') or '').strip()
            if nok_name and not p.next_of_kin.exists():
                NextOfKin.objects.create(
                    patient=p,
                    name=nok_name,
                    relationship=nok_rel,
                    phone_number=nok_phone,
                    is_primary=True
                )
                created_nok += 1

            # Caregiver
            cg_name = str(data.get('CG FirsName') or '').strip()
            cg_rel = str(data.get('CG Relationship') or '').strip() or 'Caregiver'
            cg_phone = str(data.get('CG Contacts') or '').strip()
            cg_notes = str(data.get('CG Notes') or '').strip()
            if cg_name and not p.caregivers.exists():
                Caregiver.objects.create(
                    patient=p,
                    name=cg_name,
                    relationship=cg_rel,
                    phone_number=cg_phone,
                    notes=cg_notes,
                    is_primary=True
                )
                created_cg += 1

            # Create or update Initial Assessment record
            if (p.primary_diagnosis or p.past_medical_history or p.present_medical_notes or p.notes):
                assessment = p.assessments.first()
                enr_date = data.get('Enrollment Date')
                ass_date = enr_date.date() if hasattr(enr_date, 'date') else p.registration_date
                
                struct_data = {
                    'primary_diagnosis': p.primary_diagnosis,
                    'past_medical_history': p.past_medical_history or p.primary_diagnosis,
                    'present_medical_notes': p.present_medical_notes or p.notes,
                    'other_medical_notes': p.other_medical_notes,
                    'hiv_status': p.hiv_status,
                    'referred_by': p.referred_by,
                    'source': 'Legacy Access PCMS V6.0'
                }
                
                summary = (
                    f"Historical Nairobi Hospice Clinical Dossier\n"
                    f"• Primary Diagnosis: {p.primary_diagnosis}\n"
                    f"• Past Medical History: {p.past_medical_history or 'Recorded as ' + p.primary_diagnosis}\n"
                    f"• Present Clinical Notes: {p.present_medical_notes or p.notes or 'Palliative clinical follow-up'}\n"
                    f"• Other Notes / Allergies: {p.other_medical_notes or 'None recorded'}\n"
                    f"• HIV / RVD Status: {p.hiv_status or 'Not Specified'}\n"
                    f"• Referred By: {p.referred_by or 'Not Specified'}"
                )
                
                if not assessment:
                    Assessment.objects.create(
                        patient=p,
                        assessor=staff,
                        assessment_type=AssessmentTypeChoices.INITIAL,
                        assessment_date=ass_date,
                        structured_data=struct_data,
                        clinical_summary=summary
                    )
                    created_assessments += 1
                else:
                    assessment.structured_data = struct_data
                    assessment.clinical_summary = summary
                    assessment.save()

    print(f"DONE!")
    print(f"Updated Patients: {updated_patients}")
    print(f"Created/Synced Assessments: {created_assessments}")
    print(f"Created Next of Kin: {created_nok}")
    print(f"Created Caregivers: {created_cg}")

if __name__ == '__main__':
    sync_access()
