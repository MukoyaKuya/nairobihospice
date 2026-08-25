import os
import sys
import django
import pyodbc
from datetime import datetime
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
from access_sync_guard import abort_if_production_access_sync
abort_if_production_access_sync()
django.setup()

from apps.patients.models import Patient
from apps.encounters.models import Encounter, EncounterTypeChoices
from apps.assessments.models import Assessment, AssessmentTypeChoices
from apps.medications.models import MedicationStatement, MedicationStatusChoices, RouteChoices
from apps.operations.models import StockItem, StockCategoryChoices, Vendor, VendorCategoryChoices, VendorStatusChoices
from apps.accounts.models import User

def sync_all():
    print("=== Starting Full Access Data Mapping: Clinical, Symptoms, Treatments & Inventory ===")
    
    conn_str = r'DRIVER={Microsoft Access Driver (*.mdb, *.accdb)};DBQ=C:\Users\Little Human\Desktop\NairobiHospice Access\Hospice V6.0_be.accdb;'
    conn = pyodbc.connect(conn_str)
    cur = conn.cursor()

    staff = User.objects.filter(is_superuser=True).first() or User.objects.first()

    # 1. Map Vendors (10 records)
    print("\n--- 1. Syncing Vendors ---")
    cur.execute('SELECT * FROM [Vendors]')
    cols = [c[0] for c in cur.description]
    v_rows = cur.fetchall()
    created_vendors = 0
    for r in v_rows:
        d = dict(zip(cols, r))
        name = str(d.get('Vendor Name') or d.get('Company') or d.get('Name') or '').strip()
        if not name:
            continue
        code = f"VEND-{created_vendors+1:03d}"
        v, created = Vendor.objects.get_or_create(
            name=name,
            defaults={
                'code': code,
                'category': VendorCategoryChoices.PHARMACEUTICAL,
                'contact_person': str(d.get('Contact Name') or d.get('Contact Person') or 'Account Manager').strip(),
                'phone_number': str(d.get('Phone Number') or d.get('Business Phone') or 'N/A').strip(),
                'email': str(d.get('E-mail Address') or '').strip(),
                'physical_address': str(d.get('Address') or d.get('City') or '').strip(),
                'status': VendorStatusChoices.ACTIVE,
            }
        )
        if created:
            created_vendors += 1
    print(f"Synced {len(v_rows)} vendors ({created_vendors} newly created).")

    # 2. Map Pharmacy Inventory Catalog (179 items + 34 DRUGS)
    print("\n--- 2. Syncing Pharmacy Inventory Catalog ---")
    cur.execute('SELECT * FROM [Inventory]')
    cols = [c[0] for c in cur.description]
    inv_rows = cur.fetchall()
    created_items = 0
    default_vendor = Vendor.objects.first()

    for idx, r in enumerate(inv_rows):
        d = dict(zip(cols, r))
        item_name = str(d.get('Item Name') or d.get('Item') or d.get('Description') or '').strip()
        if not item_name:
            continue
        
        sku = f"MED-{idx+1:04d}"
        category = StockCategoryChoices.ESSENTIAL_MEDICINE
        is_controlled = False
        name_lower = item_name.lower()
        if 'morphine' in name_lower or 'fentanyl' in name_lower or 'oxycodone' in name_lower or 'methadone' in name_lower or 'pethidine' in name_lower:
            category = StockCategoryChoices.CONTROLLED_OPIOID
            is_controlled = True
        elif 'gauze' in name_lower or 'bandage' in name_lower or 'dressing' in name_lower or 'gloves' in name_lower or 'syringe' in name_lower:
            category = StockCategoryChoices.WOUND_CARE
        elif 'ensure' in name_lower or 'supplement' in name_lower or 'nutrition' in name_lower:
            category = StockCategoryChoices.NUTRITIONAL_FEED

        qty = 0
        try:
            qty = int(d.get('Quantity') or d.get('Units In Stock') or d.get('Quantity on Hand') or 50)
        except Exception:
            qty = 50

        unit_cost = Decimal('100.00')
        try:
            if d.get('Unit Price') or d.get('Cost'):
                unit_cost = Decimal(str(d.get('Unit Price') or d.get('Cost')))
        except Exception:
            pass

        item, created = StockItem.objects.get_or_create(
            name=item_name,
            defaults={
                'item_code': sku,
                'category': category,
                'unit_of_measure': 'Pack / Unit',
                'quantity_on_hand': max(qty, 20),
                'minimum_reorder_level': 10,
                'unit_cost_kes': unit_cost,
                'is_controlled_substance': is_controlled,
                'preferred_vendor': default_vendor,
            }
        )
        if created:
            created_items += 1
    print(f"Synced {len(inv_rows)} inventory items ({created_items} newly created).")

    # 3. Map Clinical Encounters, Symptoms & Treatments from Appointments Table (141 records)
    print("\n--- 3. Syncing Clinical Encounters, Symptoms & Prescriptions from Appointments ---")
    cur.execute('SELECT * FROM [Appointments]')
    cols = [c[0] for c in cur.description]
    app_rows = cur.fetchall()

    created_encounters = 0
    created_meds = 0
    created_assessments = 0

    for r in app_rows:
        d = dict(zip(cols, r))
        pid = d.get('Patient ID')
        if not pid:
            continue

        s_pid = str(pid)
        year = s_pid[:4]
        num = s_pid[4:].lstrip('0') or '0'
        short_num = f"{int(num):03d}/{year[2:]}"
        hospice_num = f"NH-{year}-{int(num):04d}"

        # Find matching patient in Django
        p = Patient.objects.filter(hospice_number__iexact=hospice_num).first() or \
            Patient.objects.filter(hospice_number__icontains=short_num).first() or \
            Patient.objects.filter(ip_op_number__icontains=short_num).first()

        if not p:
            continue

        # Extract encounter date
        enc_date = None
        raw_date = d.get('Appointment Date')
        if isinstance(raw_date, datetime):
            enc_date = raw_date.date()
        elif raw_date:
            try:
                enc_date = datetime.strptime(str(raw_date)[:10], '%Y-%m-%d').date()
            except Exception:
                enc_date = datetime.now().date()
        else:
            enc_date = datetime.now().date()

        # Build comprehensive clinical notes
        notes_sections = []
        
        # Doctor / Clinician
        doctor = str(d.get('Doctor') or '').strip()
        if doctor:
            notes_sections.append(f"Attending Clinician: {doctor}")

        # Symptoms
        symptoms_list = []
        for s_key in ['Symptom1', 'Symptom2', 'Symptom3', 'Symptom4', 'Symptom5']:
            val = str(d.get(s_key) or '').strip()
            if val and val != 'None':
                symptoms_list.append(val)
        other_sym = str(d.get('Other Symptom') or '').strip()
        if other_sym:
            symptoms_list.append(other_sym)

        if symptoms_list:
            notes_sections.append("Presenting Symptoms:\n• " + "\n• ".join(symptoms_list))

        # Diagnoses & staging
        dx_list = []
        for dx_key in ['Diagnosis1', 'Diagnosis2', 'Diagnosis3', 'Diagnosis4', 'Other Diagnosis']:
            val = str(d.get(dx_key) or '').strip()
            if val and val != 'None':
                dx_list.append(val)
        if dx_list:
            notes_sections.append("Diagnoses on Review:\n• " + "\n• ".join(dx_list))

        # Triage & Vitals
        vitals = []
        if d.get('Temparature'): vitals.append(f"Temp: {d.get('Temparature')}°C")
        if d.get('Pulse Rate'): vitals.append(f"Pulse: {d.get('Pulse Rate')} bpm")
        if d.get('Systolic') and d.get('Diastolic'): vitals.append(f"BP: {d.get('Systolic')}/{d.get('Diastolic')} mmHg")
        if d.get('spO2'): vitals.append(f"SpO2: {d.get('spO2')}%")
        if d.get('Weigt') or d.get('weight'): vitals.append(f"Weight: {d.get('Weigt') or d.get('weight')} kg")
        if d.get('Height'): vitals.append(f"Height: {d.get('Height')} cm")
        if vitals:
            notes_sections.append("Vitals: " + " | ".join(vitals))

        # Palliative Scores & Interventions
        interventions = []
        if d.get('Pain Score'): interventions.append(f"Pain Score (0-10): {d.get('Pain Score')}")
        if d.get('PPS'): interventions.append(f"PPS Functional Score: {d.get('PPS')}%")
        if d.get('Wound Care'): interventions.append("Wound Care & Dressing Performed")
        if d.get('Mouth Care'): interventions.append("Oral / Mouth Care Assistance")
        if d.get('Family Meeting'): interventions.append("Family Caregiver Meeting Conducted")
        if d.get('Bereavement'): interventions.append("Bereavement Support Session")
        if d.get('HIVdiscussed'): interventions.append("HIV / ART Counselling Discussed")
        if d.get('WHO stage'): interventions.append(f"WHO Clinical Stage: {d.get('WHO stage')}")
        if d.get('onARVs'): interventions.append("Patient on Antiretroviral Therapy (ARVs)")
        if interventions:
            notes_sections.append("Clinical Interventions & Assessment:\n• " + "\n• ".join(interventions))

        # Treatments Done
        treatments_list = []
        for t_key in ['Treatment1', 'Treatment2', 'Treatment3', 'Treatment4', 'Treatment5', 'Other Treament', 'Treatment Done']:
            val = str(d.get(t_key) or '').strip()
            if val and val != 'None' and val != 's':
                treatments_list.append(val)
        if d.get('Morphine'):
            morph_note = f"Morphine Prescribed / Administered"
            if d.get('TypeOfMorphine'): morph_note += f" ({d.get('TypeOfMorphine')})"
            if d.get('Amount Given (mL)'): morph_note += f" - Dose: {d.get('Amount Given (mL)')} mL"
            treatments_list.append(morph_note)

        if treatments_list:
            notes_sections.append("Treatments & Prescriptions Dispensed:\n• " + "\n• ".join(treatments_list))

        # Comments & Triage Notes
        if d.get('Comments'): notes_sections.append(f"Clinical Notes / Comments: {d.get('Comments')}")
        if d.get('Triage Notes'): notes_sections.append(f"Triage Notes: {d.get('Triage Notes')}")
        if d.get('Outcome'): notes_sections.append(f"Encounter Outcome: {d.get('Outcome')}")

        full_clinical_notes = "\n\n".join(notes_sections) if notes_sections else "Routine Hospice Clinical Review & Assessment"

        # Determine Encounter Type
        app_type = str(d.get('Appointment Type') or '').upper()
        enc_type = EncounterTypeChoices.CLINIC_VISIT
        if 'HOME' in app_type or d.get('Visits'):
            enc_type = EncounterTypeChoices.HOME_VISIT
        elif 'PHONE' in app_type or 'TELE' in app_type:
            enc_type = EncounterTypeChoices.TELEPHONE
        elif 'COMMUNITY' in app_type or 'OUTREACH' in app_type:
            enc_type = EncounterTypeChoices.COMMUNITY_VISIT
        elif 'COUNSEL' in app_type:
            enc_type = EncounterTypeChoices.COUNSELLING

        # Create Encounter record
        enc = Encounter.objects.create(
            patient=p,
            encounter_type=enc_type,
            encounter_date=enc_date,
            location='Nairobi Hospice Clinic' if enc_type == EncounterTypeChoices.CLINIC_VISIT else 'Patient Residence',
            reason=symptoms_list[0] if symptoms_list else 'Palliative Review & Pain Management',
            clinical_notes=full_clinical_notes,
            recorded_by=staff,
        )
        created_encounters += 1

        # Create Structured Medications Statements
        for t_item in treatments_list:
            MedicationStatement.objects.create(
                patient=p,
                medication_name=t_item[:200],
                dosage="As directed by hospice protocol",
                route=RouteChoices.ORAL,
                frequency="Daily as prescribed",
                status=MedicationStatusChoices.ACTIVE,
                indication="Palliative pain & symptom control",
                prescriber=staff,
                start_date=enc_date,
                instructions_for_caregiver=f"Dispensed during encounter on {enc_date}. Ref: Access Appointment #{d.get('Appointment ID')}",
            )
            created_meds += 1

        # Create Assessment if pain or symptom scores are present
        if symptoms_list or d.get('Pain Score') or d.get('PPS'):
            p_score = None
            try:
                if d.get('Pain Score'):
                    p_score = min(max(int(d.get('Pain Score')), 0), 10)
            except Exception:
                p_score = None

            pps_score = None
            try:
                if d.get('PPS'):
                    pps_score = min(max(int(d.get('PPS')), 0), 100)
            except Exception:
                pps_score = None

            Assessment.objects.create(
                patient=p,
                assessment_type=AssessmentTypeChoices.FOLLOWUP,
                assessment_date=enc_date,
                assessor=staff,
                clinical_summary=f"Clinical review: {', '.join(symptoms_list) if symptoms_list else 'Routine palliative follow-up'}",
                pain_score=p_score,
                pps_score=pps_score,
                structured_data={
                    'symptoms': symptoms_list,
                    'vitals': vitals,
                    'interventions': interventions,
                },
            )
            created_assessments += 1

    # 4. Map Prescriptions Table (2 records)
    print("\n--- 4. Syncing Prescriptions Table ---")
    cur.execute('SELECT * FROM [Prescriptions]')
    cols = [c[0] for c in cur.description]
    presc_rows = cur.fetchall()
    for r in presc_rows:
        d = dict(zip(cols, r))
        pid = d.get('Patient ID')
        if not pid:
            continue
        s_pid = str(pid)
        year = s_pid[:4]
        num = s_pid[4:].lstrip('0') or '0'
        short_num = f"{int(num):03d}/{year[2:]}"
        hospice_num = f"NH-{year}-{int(num):04d}"

        p = Patient.objects.filter(hospice_number__iexact=hospice_num).first() or \
            Patient.objects.filter(hospice_number__icontains=short_num).first()
        if not p:
            continue

        for i in range(1, 8):
            drug_name = str(d.get(f'DRUG{i}') or '').strip()
            if drug_name and drug_name != 'None':
                dosage = str(d.get(f'Dosage{i}') or 'As directed').strip()
                duration = str(d.get(f'Duration{i}') or '').strip()
                route = RouteChoices.ORAL
                MedicationStatement.objects.create(
                    patient=p,
                    medication_name=drug_name[:200],
                    dosage=dosage,
                    route=route,
                    frequency=f"{dosage} - Duration: {duration}" if duration else dosage,
                    status=MedicationStatusChoices.ACTIVE,
                    indication="Prescribed hospice medication",
                    prescriber=staff,
                    instructions_for_caregiver=f"Prescription record #{d.get('Prescription ID')}",
                )
                created_meds += 1

    conn.close()

    print("\n=== SYNC COMPLETE ===")
    print(f"[OK] Encounters Created: {created_encounters}")
    print(f"[OK] Medications / Treatments Created: {created_meds}")
    print(f"[OK] Clinical Assessments Created: {created_assessments}")
    print(f"[OK] Stock Items Catalogued: {created_items}")
    print(f"[OK] Vendors Registered: {created_vendors}")

if __name__ == '__main__':
    sync_all()
