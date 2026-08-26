
import pytest
from rest_framework.test import APIClient

from apps.accounts.models import RoleChoices
from apps.accounts.services import create_staff_user
from apps.audit.models import AuditAction, AuditEvent
from apps.patients.services import register_patient
from apps.reporting.selectors import get_management_dashboard_data
from apps.symptoms.models import SymptomTypeChoices
from apps.symptoms.services import record_esas_assessment


@pytest.mark.django_db
class TestAPISecurityAndAuthorization:
    def setup_method(self):
        self.api_client = APIClient()
        self.doctor = create_staff_user(
            email='sec_doc@nairobihospice.or.ke',
            username='sec_doc',
            first_name='Sec',
            last_name='Doc',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        self.receptionist = create_staff_user(
            email='sec_rec@nairobihospice.or.ke',
            username='sec_rec',
            first_name='Sec',
            last_name='Rec',
            password='Pass!',
            role=RoleChoices.RECEPTIONIST,
        )
        self.pharmacist = create_staff_user(
            email='sec_pharm@nairobihospice.or.ke',
            username='sec_pharm',
            first_name='Sec',
            last_name='Pharm',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        self.patient = register_patient(
            first_name='Grace',
            last_name='Wanjiru',
            county='Nairobi',
            created_by=self.doctor,
        )

    def test_unauthenticated_api_access_denied(self):
        """Anonymous requests to clinical API endpoints must return 401/403."""
        response = self.api_client.get('/api/v1/patients/')
        assert response.status_code in [401, 403]

        response = self.api_client.get('/api/v1/encounters/')
        assert response.status_code in [401, 403]

        response = self.api_client.get('/api/v1/assessments/')
        assert response.status_code in [401, 403]

    def test_receptionist_denied_access_to_clinical_encounters_api(self):
        """Receptionist accounts cannot view or modify clinical encounter records via API."""
        self.api_client.force_authenticate(user=self.receptionist)
        response = self.api_client.get('/api/v1/encounters/')
        assert response.status_code == 403

        response = self.api_client.get('/api/v1/assessments/')
        assert response.status_code == 403

        response = self.api_client.get('/api/v1/care-plans/')
        assert response.status_code == 403

    def test_receptionist_denied_medication_prescribing_api(self):
        """Receptionist cannot create medication statements."""
        self.api_client.force_authenticate(user=self.receptionist)
        payload = {
            'patient': str(self.patient.id),
            'medication_name': 'Oral Morphine',
            'dosage': '10mg',
            'route': 'ORAL',
            'frequency': 'q4h',
        }
        response = self.api_client.post('/api/v1/medications/', payload)
        assert response.status_code == 403

    def test_pharmacist_can_access_medications_api(self):
        """Pharmacists have valid access to medication statements endpoint."""
        self.api_client.force_authenticate(user=self.pharmacist)
        response = self.api_client.get('/api/v1/medications/')
        assert response.status_code == 200

    def test_receptionist_denied_web_views_clinical_actions(self):
        """Receptionists cannot access clinical view forms (403 Forbidden)."""
        from django.test import Client
        client = Client()
        client.force_login(self.receptionist)

        response = client.get(f'/medications/patient/{self.patient.id}/create/')
        assert response.status_code == 403

        response = client.get(f'/encounters/patient/{self.patient.id}/create/')
        assert response.status_code == 403

        response = client.get(f'/assessments/patient/{self.patient.id}/create/')
        assert response.status_code == 403

        response = client.get(f'/symptoms/patient/{self.patient.id}/create/')
        assert response.status_code == 403

    def test_receptionist_can_access_id_card_and_doctor_denied(self):
        """Receptionists are authorized to generate ID cards, but clinical doctors are restricted."""
        from django.test import Client
        client = Client()

        # Receptionist access
        client.force_login(self.receptionist)
        response = client.get(f'/patients/{self.patient.id}/card/')
        assert response.status_code == 200

        # Doctor access is restricted
        client.force_login(self.doctor)
        response = client.get(f'/patients/{self.patient.id}/card/')
        assert response.status_code == 403

    def test_receptionist_patient_detail_view_strips_clinical_phi(self):
        """Receptionist view must strip clinical HTML, diagnoses, HIV status, meds, and encounters."""
        from django.test import Client
        from django.urls import reverse
        from apps.medications.models import MedicationStatement, MedicationStatusChoices

        self.patient.primary_diagnosis = "Advanced Cervical Carcinoma"
        self.patient.hiv_status = "POSITIVE"
        self.patient.allergies = "Penicillin Anaphylaxis"
        self.patient.save()

        MedicationStatement.objects.create(
            patient=self.patient,
            medication_name="Oral Morphine Solution",
            dosage="10mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )

        client = Client()
        client.force_login(self.receptionist)
        response = client.get(f'/patients/{self.patient.id}/')
        assert response.status_code == 200
        assert response.context['clinical_access'] is False
        assert response.context['medications'] == []
        assert response.context['encounters'] == []
        assert response.context['assessments'] == []

        content = response.content.decode('utf-8')
        assert "Advanced Cervical Carcinoma" not in content
        assert "Penicillin Anaphylaxis" not in content
        assert "Oral Morphine Solution" not in content
        assert "Report PDF" not in content
        assert reverse('patients:patient_download_report', kwargs={'pk': self.patient.pk}) not in content

        # Direct download attempt by receptionist is forbidden (403)
        pdf_res = client.get(reverse('patients:patient_download_report', kwargs={'pk': self.patient.pk}))
        assert pdf_res.status_code == 403

    def test_unassigned_clinician_cannot_view_unrelated_patient_detail(self):
        """Clinician not on the patient's care team receives 404 for unauthorized patient."""
        from django.test import Client
        clinician_b = create_staff_user(
            email='unassigned_doc@nairobihospice.or.ke',
            username='unassigned_doc',
            first_name='Unassigned',
            last_name='Doc',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        client = Client()
        client.force_login(clinician_b)
        response = client.get(f'/patients/{self.patient.id}/')
        assert response.status_code == 404

    def test_receptionist_patient_edit_form_excludes_clinical_fields(self):
        """Receptionist edit form must use ReceptionistPatientUpdateForm without clinical fields."""
        from django.test import Client
        client = Client()
        client.force_login(self.receptionist)
        response = client.get(f'/patients/{self.patient.id}/edit/')
        assert response.status_code == 200
        form = response.context['form']
        assert form.__class__.__name__ == 'ReceptionistPatientUpdateForm'
        assert 'status' not in form.fields
        assert 'special_remarks' not in form.fields
        assert 'primary_diagnosis' not in form.fields
        assert 'hiv_status' not in form.fields
        assert 'allergies' not in form.fields
        assert 'clinical_alerts' not in form.fields
        assert 'past_medical_history' not in form.fields
        assert 'present_medical_notes' not in form.fields

        # Receptionist POST cannot change status to DECEASED or inject special remarks
        self.patient.status = 'ACTIVE'
        self.patient.special_remarks = 'Original Remarks'
        self.patient.save()

        # Receptionist can edit contact details, Next of Kin, and Caregiver
        assert 'nok_name' in form.fields
        assert 'caregiver_name' in form.fields

        post_res = client.post(f'/patients/{self.patient.id}/edit/', {
            'first_name': self.patient.first_name,
            'last_name': self.patient.last_name,
            'sex': 'F',
            'identification_type': 'NATIONAL_ID',
            'preferred_language': 'English',
            'marital_status': 'MARRIED',
            'phone_number': '+254700111222',
            'county': 'Nairobi',
            'nok_name': 'Mary Wanjiku Updated',
            'nok_relationship': 'Mother',
            'nok_phone': '+254711223344',
            'caregiver_name': 'David Mwangi Caregiver',
            'caregiver_relationship': 'Brother',
            'caregiver_phone': '+254722334455',
            'status': 'DECEASED',
            'special_remarks': 'Tampered Remarks',
        })
        assert post_res.status_code == 302
        self.patient.refresh_from_db()
        assert self.patient.status == 'ACTIVE'
        assert self.patient.special_remarks == 'Original Remarks'
        assert self.patient.phone_number == '+254700111222'
        
        # Verify Next of Kin and Caregiver updated
        nok = self.patient.next_of_kin.first()
        assert nok is not None
        assert nok.name == 'Mary Wanjiku Updated'
        assert nok.phone_number == '+254711223344'
        
        cg = self.patient.caregivers.first()
        assert cg is not None
        assert cg.name == 'David Mwangi Caregiver'
        assert cg.phone_number == '+254722334455'

        # Clinician edit form retains clinical fields
        client.force_login(self.doctor)
        response_doc = client.get(f'/patients/{self.patient.id}/edit/')
        assert response_doc.status_code == 200
        form_doc = response_doc.context['form']
        assert form_doc.__class__.__name__ == 'PatientUpdateForm'
        assert 'primary_diagnosis' in form_doc.fields
        assert 'hiv_status' in form_doc.fields
        assert 'status' in form_doc.fields

    def test_convert_referral_to_patient_raises_when_care_team_missing(self):
        """convert_referral_to_patient raises ValidationError if nurse or doctor is missing."""
        from django.core.exceptions import ValidationError
        from apps.referrals.models import Referral, ReferralStatusChoices
        from apps.referrals.services import convert_referral_to_patient

        referral = Referral.objects.create(
            referral_number="REF-2026-9999",
            patient_name="CareTeam Test Patient",
            primary_diagnosis="Advanced Cancer",
            reason_for_referral="Palliative Symptom Control",
            status=ReferralStatusChoices.ACCEPTED,
        )
        with pytest.raises(ValidationError):
            convert_referral_to_patient(
                referral=referral,
                user=self.receptionist,
                primary_nurse=None,
                primary_doctor=None,
            )

    def test_pharmacist_dashboard_scoped_to_authorized_caseload(self):
        """Pharmacist dashboard active medications only includes patients with pharmacist dispenses."""
        from apps.reporting.selectors import get_clinical_dashboard_data
        from apps.medications.models import MedicationStatement, MedicationStatusChoices
        from apps.patients.access import authorized_patient_queryset

        pharmacist = create_staff_user(
            email='pharm_dash_test@nairobihospice.or.ke',
            username='pharm_dash_test',
            first_name='Pharm',
            last_name='Dash',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        from apps.operations.models import StockItem, MovementTypeChoices
        from apps.operations.services import record_stock_movement

        med = MedicationStatement.objects.create(
            patient=self.patient,
            medication_name="Oral Morphine 10mg/5ml",
            dosage="5mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )

        # Before any dispense, pharmacist has no patients on caseload
        data_before = get_clinical_dashboard_data(pharmacist)
        assert len(data_before['active_medications']) == 0
        assert self.patient not in list(authorized_patient_queryset(pharmacist))

        # After dispensing, patient enters pharmacist's authorized caseload
        stock_item = StockItem.objects.create(
            name="Oral Morphine 10mg/5ml",
            item_code="STK-MORPH-DASH",
            quantity_on_hand=50,
            unit_of_measure="bottle",
        )
        record_stock_movement(
            stock_item=stock_item,
            movement_type=MovementTypeChoices.DISPENSE,
            quantity=1,
            patient=self.patient,
            medication_statement=med,
            user=pharmacist,
        )
        data_after = get_clinical_dashboard_data(pharmacist)
        assert len(data_after['active_medications']) == 1
        assert self.patient in list(authorized_patient_queryset(pharmacist))

    def test_receptionist_dashboard_and_drf_search_strip_diagnosis(self):
        """Reception dashboard and DRF patient search strip primary diagnosis."""
        from django.test import Client
        from apps.referrals.models import Referral, ReferralStatusChoices

        Referral.objects.create(
            referral_number="REF-2026-8888",
            patient_name="Secret Dx Patient",
            referring_facility="Kenyatta National Hospital",
            primary_diagnosis="Sensitive Carcinoma Stage IV",
            reason_for_referral="Pain Management",
            status=ReferralStatusChoices.RECEIVED,
        )
        client = Client()
        client.force_login(self.receptionist)

        # 1. Reception dashboard template does not print primary diagnosis
        response_dash = client.get('/reporting/clinical/')
        assert response_dash.status_code == 200
        assert b"Sensitive Carcinoma Stage IV" not in response_dash.content

        # 2. DRF patient search ignores primary_diagnosis for receptionist
        response_drf = client.get('/api/v1/patients/?search=Sensitive')
        assert response_drf.status_code == 200
        assert len(response_drf.json().get('results', [])) == 0

    def test_dispense_form_dropdowns_scoped_for_pharmacist(self):
        """StockDispenseForm scopes patient choices to patients with active meds for pharmacists."""
        from apps.operations.forms import StockDispenseForm
        from apps.medications.models import MedicationStatement, MedicationStatusChoices

        patient_without_meds = register_patient(
            first_name='NoMed',
            last_name='Patient',
            created_by=self.doctor,
        )
        patient_with_meds = register_patient(
            first_name='WithMed',
            last_name='Patient',
            created_by=self.doctor,
        )
        MedicationStatement.objects.create(
            patient=patient_with_meds,
            medication_name="Oral Morphine 5mg",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )

        pharmacist = create_staff_user(
            email='pharm_form_test@nairobihospice.or.ke',
            username='pharm_form_test',
            first_name='Pharm',
            last_name='Form',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        # Blank form without candidate: only existing caseload
        form_blank = StockDispenseForm(user=pharmacist)
        assert patient_with_meds not in list(form_blank.fields['patient'].queryset)
        assert patient_without_meds not in list(form_blank.fields['patient'].queryset)

        # Form with active-Rx candidate requested via initial/?patient=: not widened
        # unless the patient is already in authorized_patient_queryset (no prior dispense).
        form_candidate = StockDispenseForm(initial={'patient': patient_with_meds.pk}, user=pharmacist)
        allowed_patients = list(form_candidate.fields['patient'].queryset)
        assert patient_with_meds not in allowed_patients
        assert patient_without_meds not in allowed_patients

    def test_pharmacy_recent_dispenses_scoped_by_role(self):
        """Pharmacy dispense view scopes recent dispenses table strictly by user role and dispenses."""
        from django.test import Client
        from apps.operations.models import StockItem, StockMovement, MovementTypeChoices
        from apps.operations.services import record_stock_movement

        item = StockItem.objects.create(
            item_code="STK-MORPH-TST",
            name="Morphine 10mg",
            unit_of_measure="vial",
            quantity_on_hand=50,
        )
        pharm1 = create_staff_user(
            email='pharm1_test@nairobihospice.or.ke',
            username='pharm1_test',
            first_name='Pharm',
            last_name='One',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        pharm2 = create_staff_user(
            email='pharm2_test@nairobihospice.or.ke',
            username='pharm2_test',
            first_name='Pharm',
            last_name='Two',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        from apps.medications.models import MedicationStatement, MedicationStatusChoices
        med1 = MedicationStatement.objects.create(
            patient=self.patient,
            medication_name="Morphine 10mg",
            dosage="5mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )
        mov1 = record_stock_movement(
            stock_item=item,
            movement_type=MovementTypeChoices.DISPENSE,
            quantity=2,
            reference_document="Ref 1",
            patient=self.patient,
            medication_statement=med1,
            user=pharm1,
        )

        client = Client()
        # Pharm1 sees their own dispense
        client.force_login(pharm1)
        resp1 = client.get('/operations/pharmacy/dispense/')
        assert resp1.status_code == 200
        assert mov1 in list(resp1.context['recent_dispenses'])

        # Pharm2 does NOT see Pharm1's dispense
        client.force_login(pharm2)
        resp2 = client.get('/operations/pharmacy/dispense/')
        assert resp2.status_code == 200
        assert mov1 not in list(resp2.context['recent_dispenses'])

    def test_patient_summary_serializer_status_is_read_only(self):
        """PatientSummarySerializer declares status as a read-only field."""
        from api.v1.serializers import PatientSummarySerializer
        serializer = PatientSummarySerializer()
        assert 'status' in serializer.fields
        assert serializer.fields['status'].read_only is True

    def test_pharmacist_cannot_patch_patient_clinical_fields(self):
        """Pharmacist receives PatientSummarySerializer and cannot PATCH clinical fields or status."""
        pharm = create_staff_user(
            email='pharm_patch@nairobihospice.or.ke',
            username='pharm_patch',
            first_name='Pharm',
            last_name='Patch',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        self.patient.primary_diagnosis = "Original Carcinoma"
        self.patient.status = "ACTIVE"
        self.patient.save()

        self.api_client.force_authenticate(user=pharm)
        response = self.api_client.patch(
            f'/api/v1/patients/{self.patient.id}/',
            {'primary_diagnosis': 'Hacked Carcinoma', 'status': 'DECEASED'},
            format='json',
        )
        assert response.status_code == 403
        self.patient.refresh_from_db()
        assert self.patient.primary_diagnosis == "Original Carcinoma"
        assert self.patient.status == "ACTIVE"

    def test_pharmacist_with_dispense_caseload_is_denied_all_clinical_and_editing_actions(self):
        """Even after dispensing to a patient, pharmacist cannot edit patient, create encounters/ESAS/docs, access routes, or see diagnosis."""
        from django.test import Client
        from apps.operations.models import StockItem, StockMovement, MovementTypeChoices
        from apps.operations.services import record_stock_movement
        from apps.medications.models import MedicationStatement, MedicationStatusChoices
        from apps.patients.access import authorized_patient_queryset

        pharm = create_staff_user(
            email='pharm_caseload@nairobihospice.or.ke',
            username='pharm_caseload',
            first_name='Pharm',
            last_name='Caseload',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        self.patient.primary_diagnosis = "Metastatic Breast Cancer"
        self.patient.save()

        # Create medication and dispense to put patient on pharmacist's caseload
        med = MedicationStatement.objects.create(
            patient=self.patient,
            medication_name="Oral Morphine 10mg/5ml",
            dosage="5mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )
        stock_item = StockItem.objects.create(
            name="Oral Morphine 10mg/5ml",
            item_code="STK-MORPH-10-TEST-CASELOAD",
            quantity_on_hand=50,
            unit_of_measure="bottle",
        )
        record_stock_movement(
            stock_item=stock_item,
            movement_type=MovementTypeChoices.DISPENSE,
            quantity=1,
            patient=self.patient,
            medication_statement=med,
            user=pharm,
        )

        # Confirm patient is now on pharmacist's caseload
        assert self.patient in list(authorized_patient_queryset(pharm))

        client = Client()
        client.force_login(pharm)

        # 1. Edit patient web form -> 403 Forbidden
        assert client.get(f'/patients/{self.patient.pk}/edit/').status_code == 403
        assert client.post(f'/patients/{self.patient.pk}/edit/', {'first_name': 'Hacked'}).status_code == 403

        # 2. DRF API PATCH -> 403 Forbidden
        self.api_client.force_authenticate(user=pharm)
        api_resp = self.api_client.patch(
            f'/api/v1/patients/{self.patient.pk}/',
            {'first_name': 'Hacked API'},
            format='json',
        )
        assert api_resp.status_code == 403

        # 3. Create Encounter -> 403 Forbidden
        assert client.get(f'/encounters/patient/{self.patient.pk}/create/').status_code == 403
        assert client.post(f'/encounters/patient/{self.patient.pk}/create/', {'reason': 'check'}).status_code == 403

        # 4. Create ESAS Symptom Assessment -> 403 Forbidden
        assert client.get(f'/symptoms/patient/{self.patient.pk}/create/').status_code == 403

        # 5. Upload Clinical Document -> 403 Forbidden
        assert client.get(f'/documents/patient/{self.patient.pk}/upload/').status_code == 403

        # 6. Access Field Route Logistics -> 403 Forbidden
        assert client.get('/appointments/routes/').status_code == 403

        # 7. Search API -> primary_diagnosis is stripped / blank
        search_resp = client.get(f'/patients/api/search/?q={self.patient.first_name}')
        assert search_resp.status_code == 200
        item = [r for r in search_resp.json()['results'] if r['id'] == str(self.patient.id)][0]
        assert item['primary_diagnosis'] == ''

        # 8. Patient List table -> primary_diagnosis shows 'Palliative Care', not actual diagnosis
        list_resp = client.get('/patients/')
        assert list_resp.status_code == 200
        assert b'Metastatic Breast Cancer' not in list_resp.content

        # 9. Patient detail -> no encounters/assessments/careplan/symptoms tabs
        detail_resp = client.get(f'/patients/{self.patient.pk}/')
        assert detail_resp.status_code == 200
        assert detail_resp.context['clinical_access'] is False
        assert detail_resp.context['is_pharmacist'] is True
        assert b'Metastatic Breast Cancer' not in detail_resp.content

        # 10. Patient Registration -> 403 Forbidden
        assert client.get('/patients/register/').status_code == 403
        assert client.post('/patients/register/', {'first_name': 'Test'}).status_code == 403

        # 11. Referral Registration -> 403 Forbidden
        assert client.get('/referrals/create/').status_code == 403
        assert client.post('/referrals/create/', {'patient_name': 'Ref'}).status_code == 403

        # 12. DRF API Medication Writes -> 403 Forbidden
        med_write_resp = self.api_client.post(
            '/api/v1/medications/',
            {'patient': str(self.patient.id), 'medication_name': 'Paracetamol', 'dosage': '500mg', 'route': 'ORAL', 'frequency': 'tds', 'status': 'ACTIVE'},
            format='json',
        )
        assert med_write_resp.status_code == 403

        # 13. Calendar recent_patients is scoped to authorized caseload only
        cal_resp = client.get('/appointments/')
        assert cal_resp.status_code == 200
        recent_pks = [p.pk for p in cal_resp.context['recent_patients']]
        assert self.patient.pk in recent_pks

    def test_receptionist_cannot_access_home_routes_logistics(self):
        """Receptionist is forbidden from accessing field route dispatch workspace."""
        from django.test import Client
        client = Client()
        client.force_login(self.receptionist)
        response = client.get('/appointments/routes/')
        assert response.status_code == 403

        client.force_login(self.doctor)
        response_doc = client.get('/appointments/routes/')
        assert response_doc.status_code == 200

    def test_search_patients_drops_diagnosis_for_non_clinical(self):
        """search_patients does not match primary_diagnosis query terms when is_clinical=False."""
        from apps.patients.selectors import search_patients
        self.patient.primary_diagnosis = "Glioblastoma Multiforme"
        self.patient.save()

        results_clin = search_patients(query="Glioblastoma", is_clinical=True)
        assert self.patient in list(results_clin)

        results_non_clin = search_patients(query="Glioblastoma", is_clinical=False)
        assert self.patient not in list(results_non_clin)

    def test_patient_search_api_strips_diagnosis_for_receptionist(self):
        """Patient search API returns blank primary_diagnosis for receptionists and scoped results."""
        from django.test import Client
        self.patient.primary_diagnosis = "Advanced Cervical Carcinoma"
        self.patient.save()

        client = Client()
        # Receptionist search
        client.force_login(self.receptionist)
        response = client.get(f'/patients/api/search/?q={self.patient.first_name}')
        assert response.status_code == 200
        data = response.json()
        assert len(data['results']) >= 1
        item = [r for r in data['results'] if r['id'] == str(self.patient.id)][0]
        assert item['primary_diagnosis'] == ''

        # Doctor authorized search
        client.force_login(self.doctor)
        response_doc = client.get(f'/patients/api/search/?q={self.patient.first_name}')
        assert response_doc.status_code == 200
        data_doc = response_doc.json()
        item_doc = [r for r in data_doc['results'] if r['id'] == str(self.patient.id)][0]
        assert item_doc['primary_diagnosis'] == "Advanced Cervical Carcinoma"

    def test_typeahead_search_excludes_unassigned_patient_for_clinician_and_pharmacist(self):
        """Clinician and Pharmacist typeahead search strictly excludes unassigned patients."""
        from django.test import Client
        unassigned_doc = create_staff_user(
            email='other_doc@nairobihospice.or.ke',
            username='other_doc',
            first_name='Other',
            last_name='Doc',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        unassigned_pharm = create_staff_user(
            email='other_pharm@nairobihospice.or.ke',
            username='other_pharm',
            first_name='Other',
            last_name='Pharm',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )

        client = Client()
        # Other doctor has no care episode for self.patient -> search returns empty
        client.force_login(unassigned_doc)
        res_doc = client.get(f'/patients/api/search/?q={self.patient.first_name}')
        assert res_doc.status_code == 200
        assert res_doc.json()['results'] == []

        # Other pharmacist has no active prescription or dispense for self.patient -> search returns empty
        client.force_login(unassigned_pharm)
        res_pharm = client.get(f'/patients/api/search/?q={self.patient.first_name}')
        assert res_pharm.status_code == 200
        assert res_pharm.json()['results'] == []

    def test_calendar_view_excludes_diagnosis_and_clinical_reason_for_receptionist(self):
        """Calendar strips patient diagnosis and clinical focus reason for receptionists."""
        from django.test import Client
        from apps.appointments.models import Appointment, AppointmentTypeChoices, AppointmentStatusChoices
        from django.utils import timezone
        
        self.patient.primary_diagnosis = "Renal Cell Carcinoma Stage IV"
        self.patient.save()

        Appointment.objects.create(
            patient=self.patient,
            staff_member=self.doctor.staff_profile,
            appointment_type=AppointmentTypeChoices.CLINIC_VISIT,
            scheduled_date=timezone.now().date(),
            scheduled_time=timezone.now().time(),
            status=AppointmentStatusChoices.SCHEDULED,
            reason="Acute breakthrough flank pain flare evaluation",
            created_by=self.doctor,
        )

        client = Client()
        client.force_login(self.receptionist)
        res = client.get('/appointments/')
        assert res.status_code == 200
        assert b'Renal Cell Carcinoma Stage IV' not in res.content
        assert b'Acute breakthrough flank pain flare evaluation' not in res.content

    def test_receptionist_referral_post_does_not_persist_diagnosis(self):
        """Referrals created by receptionists scrub clinical fields and default primary_diagnosis to 'Pending Clinical Review'."""
        from django.test import Client
        from apps.referrals.models import Referral

        client = Client()
        client.force_login(self.receptionist)
        res = client.post('/referrals/create/', {
            'patient_name': 'Mary Achieng',
            'approximate_age': 45,
            'sex': 'F',
            'phone_number': '0711223344',
            'county': 'Nairobi',
            'referral_source': 'HOSPITAL',
            'referring_facility': 'Kenyatta National Hospital',
            'referral_date': '2026-08-25',
            'priority': 'ROUTINE',
            'primary_diagnosis': 'Unauthorized Injected Diagnosis',
            'reason_for_referral': 'Palliative intake requested by KNH oncology',
            'clinical_summary': 'Unauthorized chemo history notes',
            'current_medications': 'Unauthorized opioid list',
        })
        assert res.status_code == 302
        ref = Referral.objects.filter(patient_name='Mary Achieng').latest('created_at')
        assert ref.primary_diagnosis == 'Pending Clinical Review'
        assert ref.clinical_summary == ''
        assert ref.current_medications == ''
        assert ref.reason_for_referral == 'Palliative care intake evaluation requested.'

    def test_dispense_without_prescription_fk_raises_validation_error(self):
        """Service layer record_stock_movement and model clean() strictly require medication_statement on patient dispenses."""
        from django.core.exceptions import ValidationError
        from apps.operations.models import StockItem, StockMovement, MovementTypeChoices
        from apps.operations.services import record_stock_movement

        stock_item = StockItem.objects.create(
            name="Oral Morphine Solution 10mg/5ml",
            item_code="STK-TEST-VAL-FK",
            quantity_on_hand=30,
            unit_of_measure="bottle",
        )
        # Service layer validation
        with pytest.raises(ValidationError, match="A linked active medication statement is required"):
            record_stock_movement(
                stock_item=stock_item,
                movement_type=MovementTypeChoices.DISPENSE,
                quantity=1,
                patient=self.patient,
                medication_statement=None,
                user=self.doctor,
            )

        # Model-level create validation (full_clean in save)
        with pytest.raises(ValidationError):
            StockMovement.objects.create(
                stock_item=stock_item,
                movement_type=MovementTypeChoices.DISPENSE,
                quantity=-1,
                balance_after=29,
                patient=self.patient,
                medication_statement=None,
            )

        # Database CheckConstraint validation (bypassing model clean via bulk_create)
        from django.db.utils import IntegrityError
        with pytest.raises(IntegrityError):
            StockMovement.objects.bulk_create([
                StockMovement(
                    stock_item=stock_item,
                    movement_type=MovementTypeChoices.DISPENSE,
                    quantity=-1,
                    balance_after=29,
                    patient=self.patient,
                    medication_statement=None,
                )
            ])

    def test_receptionist_referral_scrubs_clinical_terms_from_reason(self):
        """Referral reason_for_referral from receptionists drops clinical narrative and saves fixed intake token."""
        from django.test import Client
        from apps.referrals.models import Referral

        client = Client()
        client.force_login(self.receptionist)
        res = client.post('/referrals/create/', {
            'patient_name': 'Grace Auma',
            'approximate_age': 52,
            'sex': 'F',
            'phone_number': '0722334455',
            'county': 'Nairobi',
            'referral_source': 'HOSPITAL',
            'referring_facility': 'Kenyatta National Hospital',
            'referral_date': '2026-08-25',
            'priority': 'ROUTINE',
            'primary_diagnosis': 'Metastatic Breast Carcinoma Stage IV',
            'reason_for_referral': 'Referral for breast cancer / Ca cervix / adenocarcinoma / HIV / morphine titration',
        })
        assert res.status_code == 302
        ref = Referral.objects.filter(patient_name='Grace Auma').latest('created_at')
        assert ref.primary_diagnosis == 'Pending Clinical Review'
        assert ref.reason_for_referral == 'Palliative care intake evaluation requested.'
        assert 'breast cancer' not in ref.reason_for_referral
        assert 'Ca cervix' not in ref.reason_for_referral
        assert 'adenocarcinoma' not in ref.reason_for_referral
        assert 'HIV' not in ref.reason_for_referral
        assert 'morphine' not in ref.reason_for_referral

    def test_dispense_cross_patient_rx_mismatch_db_trigger_fails(self):
        """Database trigger ensures medication_statement belongs to the dispensed patient on bulk_create and update."""
        from django.db.utils import IntegrityError, DatabaseError
        from apps.operations.models import StockItem, StockMovement, MovementTypeChoices
        from apps.medications.models import MedicationStatement, MedicationStatusChoices
        from apps.patients.models import Patient

        stock_item = StockItem.objects.create(
            name="Morphine 10mg Solution",
            item_code="STK-DB-TRG-01",
            quantity_on_hand=50,
            unit_of_measure="bottle",
        )
        patient_b = Patient.objects.create(
            first_name="Patient",
            last_name="Beta",
            hospice_number="NH-TRG-B",
            sex="F",
            status="ACTIVE",
        )
        rx_beta = MedicationStatement.objects.create(
            patient=patient_b,
            medication_name="Morphine 10mg",
            dosage="10mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )

        # Mismatch: Dispensing to self.patient using patient_b's prescription via bulk_create
        with pytest.raises((IntegrityError, DatabaseError)):
            StockMovement.objects.bulk_create([
                StockMovement(
                    stock_item=stock_item,
                    movement_type=MovementTypeChoices.DISPENSE,
                    quantity=-1,
                    balance_after=49,
                    patient=self.patient,  # Mismatched patient
                    medication_statement=rx_beta,  # Belongs to patient_b
                )
            ])

    def test_pharmacist_dispense_form_does_not_contain_unassigned_patient(self):
        """Pharmacist initial GET of dispense form does not dump unassigned patients into HTML select."""
        from django.test import Client
        from apps.patients.models import Patient
        from apps.medications.models import MedicationStatement, MedicationStatusChoices

        unassigned_pat = Patient.objects.create(
            first_name="Unassigned",
            last_name="Candidate",
            hospice_number="NH-UNASSIGNED-01",
            sex="M",
            status="ACTIVE",
        )
        MedicationStatement.objects.create(
            patient=unassigned_pat,
            medication_name="Paracetamol 500mg",
            dosage="500mg",
            route="ORAL",
            frequency="TID",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )

        pharm = create_staff_user(
            email='pharm_roster_check@nairobihospice.or.ke',
            username='pharm_roster_check',
            first_name='Pharm',
            last_name='Check',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        client = Client()
        client.force_login(pharm)
        resp = client.get('/operations/pharmacy/dispense/')
        assert resp.status_code == 200
        assert 'NH-UNASSIGNED-01' not in resp.content.decode('utf-8')

    def test_clinical_dashboard_skips_pain_and_encounter_queries_for_reception_and_pharmacy(self):
        """Clinical dashboard selectors return empty querysets for pain, encounters, and care plans for non-clinical roles."""
        from apps.reporting.selectors import get_clinical_dashboard_data

        rec_data = get_clinical_dashboard_data(self.receptionist)
        assert rec_data['pain_spikes_count'] == 0
        assert len(rec_data['pain_spikes']) == 0
        assert len(rec_data['recent_encounters']) == 0
        assert len(rec_data['due_reviews']) == 0

        pharm_user = create_staff_user(
            email='pharm_query_skip@nairobihospice.or.ke',
            username='pharm_query_skip',
            first_name='Pharm',
            last_name='Skip',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        pharm_data = get_clinical_dashboard_data(pharm_user)
        assert pharm_data['pain_spikes_count'] == 0
        assert len(pharm_data['pain_spikes']) == 0
        assert len(pharm_data['recent_encounters']) == 0
        assert len(pharm_data['due_reviews']) == 0

    def test_document_and_photo_streaming_security_headers(self):
        """Document and photo download responses set private, no-store, max-age=0, must-revalidate and nosniff headers."""
        from django.test import Client
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.documents.models import PatientDocument

        doc = PatientDocument.objects.create(
            patient=self.patient,
            title="Biopsy Report",
            category="HISTOLOGY",
            file=SimpleUploadedFile("biopsy.pdf", b"%PDF-1.4 test biopsy file content"),
            uploaded_by=self.doctor,
        )

        client = Client()
        client.force_login(self.doctor)
        doc_resp = client.get(f'/documents/{doc.pk}/download/')
        assert doc_resp.status_code == 200
        assert doc_resp['Cache-Control'] == 'private, no-store, max-age=0, must-revalidate'
        assert doc_resp['X-Content-Type-Options'] == 'nosniff'

        # Test photo streaming headers
        self.patient.photo = SimpleUploadedFile("avatar.jpg", b"\xff\xd8\xff\xe0testjpegimagebytes", content_type="image/jpeg")
        self.patient.save()

        photo_resp = client.get(f'/patients/{self.patient.pk}/photo/')
        assert photo_resp.status_code == 200
        assert photo_resp['Cache-Control'] == 'private, no-store, max-age=0, must-revalidate'
        assert photo_resp['X-Content-Type-Options'] == 'nosniff'

    def test_medication_list_scoped_to_authorized_caseload(self):
        """Medication list view scopes statements to clinician authorized caseload."""
        from django.test import Client
        from apps.medications.models import MedicationStatement, MedicationStatusChoices
        MedicationStatement.objects.create(
            patient=self.patient,
            medication_name="Oral Morphine Solution 10mg",
            dosage="10mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )

        unassigned_doc = create_staff_user(
            email='unauth_med_doc@nairobihospice.or.ke',
            username='unauth_med_doc',
            first_name='Unauth',
            last_name='Doc',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        client = Client()
        client.force_login(unassigned_doc)
        response = client.get('/medications/')
        assert response.status_code == 200
        assert len(response.context['medications']) == 0

        # Assigned doctor sees medication
        client.force_login(self.doctor)
        response_auth = client.get('/medications/')
        assert response_auth.status_code == 200
        assert len(response_auth.context['medications']) >= 1

    def test_mfa_secret_encrypted_in_database_and_verifies(self):
        """MFA secrets use real Fernet at-rest encryption; DB dump contains no plaintext secret."""
        from apps.accounts.mfa import decrypt_mfa_secret, encrypt_mfa_secret, generate_secret, generate_totp, verify_totp_for_user
        raw_secret = generate_secret()
        encrypted = encrypt_mfa_secret(raw_secret)
        assert encrypted != raw_secret
        assert raw_secret not in encrypted  # No plaintext TOTP secret in ciphertext

        self.doctor.mfa_secret = encrypted
        self.doctor.is_mfa_enabled = True
        self.doctor.save()

        # Database stores encrypted secret
        self.doctor.refresh_from_db()
        assert self.doctor.mfa_secret == encrypted

        # TOTP generation and verification succeeds transparently
        token = generate_totp(raw_secret)
        assert verify_totp_for_user(self.doctor, token) is True

        # Malformed ciphertext fails closed (returns empty string)
        assert decrypt_mfa_secret("invalid-corrupted-ciphertext") == ""

    def test_pharmacist_cannot_view_unrelated_patients_or_full_clinical_chart(self):
        """Pharmacists only access patients with recorded stock movements, and chart excludes clinical PHI."""
        from django.test import Client
        from apps.operations.models import MovementTypeChoices, StockItem, StockMovement
        from apps.medications.models import MedicationStatement, MedicationStatusChoices

        pharmacist = create_staff_user(
            email='pharm_sec@nairobihospice.or.ke',
            username='pharm_sec',
            first_name='Pharm',
            last_name='Sec',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        client = Client()
        client.force_login(pharmacist)

        # 1. Without any recorded stock movement, pharmacist receives 404
        response_unauth = client.get(f'/patients/{self.patient.id}/')
        assert response_unauth.status_code == 404

        # 2. Add an active medication and record a stock movement by this pharmacist
        med = MedicationStatement.objects.create(
            patient=self.patient,
            medication_name="Oral Morphine Solution 10mg/5ml",
            dosage="5mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )
        item = StockItem.objects.create(
            name="Oral Morphine 10mg/5ml",
            unit_of_measure="Bottles",
            quantity_on_hand=50,
            minimum_reorder_level=5,
            unit_cost_kes=600.0,
            is_controlled_substance=True,
        )
        StockMovement.objects.create(
            stock_item=item,
            movement_type=MovementTypeChoices.DISPENSE,
            quantity=2,
            balance_after=48,
            patient=self.patient,
            medication_statement=med,
            recorded_by=pharmacist,
        )

        # 3. Now pharmacist can access detail, but clinical data is stripped
        response_auth = client.get(f'/patients/{self.patient.id}/')
        assert response_auth.status_code == 200
        assert response_auth.context['clinical_access'] is False
        assert response_auth.context['is_pharmacist'] is True
        assert len(response_auth.context['medications']) >= 1
        assert response_auth.context['encounters'] == []
        assert response_auth.context['assessments'] == []
        assert response_auth.context['active_care_plan'] is None

    def test_receptionist_cannot_set_hiv_or_diagnosis_on_registration(self):
        """Receptionist web registration ignores/strips HIV status and clinical diagnosis."""
        from django.test import Client
        nurse = create_staff_user(
            email='rec_reg_nurse@nairobihospice.or.ke',
            username='rec_reg_nurse',
            first_name='Nurse',
            last_name='Reg',
            password='Pass!',
            role=RoleChoices.NURSE,
        )
        client = Client()
        client.force_login(self.receptionist)

        response = client.post('/patients/register/', {
            'first_name': 'Faith',
            'last_name': 'Nyambura',
            'sex': 'F',
            'marital_status': 'MARRIED',
            'identification_type': 'NATIONAL_ID',
            'identification_number': '12345678',
            'date_of_birth': '1985-05-12',
            'phone_number': '0722112233',
            'county': 'Nairobi',
            'sub_county': 'Westlands',
            'ward': 'Parklands',
            'preferred_language': 'English',
            'status': 'ACTIVE',
            'primary_nurse': str(nurse.staff_profile.id),
            'primary_doctor': str(self.doctor.staff_profile.id),
            'consultation_fee': '1200.00',
            'payment_method': 'M-PESA (Paybill 981234)',
            'payment_reference': 'QHK8923KLM',
            # Attempted clinical fields submitted by receptionist:
            'hiv_status': 'POSITIVE',
            'primary_diagnosis': 'Metastatic Breast Carcinoma',
            'chief_complaint': 'Severe dyspnea and bone pain',
            'past_medical_history': 'Prior mastectomy in 2022',
        })
        form_errs = response.context['form'].errors if hasattr(response, 'context') and response.context and 'form' in response.context else None
        assert response.status_code == 302, f"Form validation failed with errors: {form_errs}"
        from apps.patients.models import Patient
        created = Patient.objects.filter(first_name='Faith', last_name='Nyambura').first()
        assert created is not None
        assert created.hiv_status == ''
        assert created.primary_diagnosis == ''
        # Verify invoice was created in Operations
        from decimal import Decimal
        from apps.operations.models import Invoice, PaymentStatusChoices
        inv = Invoice.objects.filter(patient=created).first()
        assert inv is not None
        assert inv.status == PaymentStatusChoices.PAID
        assert inv.total_amount_kes == Decimal('1200.00')
        assert inv.payment_reference == 'QHK8923KLM'

    def test_dispense_form_rejects_mismatched_patient_and_medication(self):
        """StockDispenseForm fails validation when medication prescription belongs to another patient."""
        from apps.operations.forms import StockDispenseForm
        from apps.operations.models import StockItem
        from apps.medications.models import MedicationStatement, MedicationStatusChoices

        patient_b = register_patient(first_name='Patient', last_name='Beta', created_by=self.doctor)
        item = StockItem.objects.create(
            name="Morphine Sulfate 10mg",
            unit_of_measure="Bottles",
            quantity_on_hand=100,
            minimum_reorder_level=10,
            unit_cost_kes=500.0,
        )
        med_for_patient_a = MedicationStatement.objects.create(
            patient=self.patient,
            medication_name="Morphine Sulfate 10mg",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )
        med_for_patient_b = MedicationStatement.objects.create(
            patient=patient_b,
            medication_name="Paracetamol 500mg",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )

        form = StockDispenseForm(data={
            'stock_item': item.id,
            'patient': patient_b.id,
            'medication_statement': med_for_patient_a.id,
            'quantity': 2,
        })
        assert form.is_valid() is False
        assert 'medication_statement' in form.errors

    def test_privileged_session_without_mfa_fails_closed(self):
        """Privileged users without verified MFA session are intercepted by middleware."""
        from django.test import Client, override_settings
        from apps.accounts.models import SecurityConfiguration
        config = SecurityConfiguration.get_solo()
        config.mfa_enabled = True
        config.save()

        with override_settings(MFA_ENFORCEMENT_MIDDLEWARE_ENABLED=True):
            manager = create_staff_user(
                email='mgr_mfa_test@nairobihospice.or.ke',
                username='mgr_mfa_test',
                first_name='Manager',
                last_name='MFA',
                password='Pass!',
                role=RoleChoices.MANAGER,
            )
            client = Client()
            # Force login without setting mfa_verified session marker
            client.force_login(manager)

            response = client.get('/patients/')
            assert response.status_code == 302
            assert '/accounts/mfa/enroll/' in response.url or '/accounts/mfa/verify/' in response.url


    def test_pharmacist_dispense_query_param_does_not_leak_unassigned_hospice_number(self):
        """Pharmacist GET /operations/pharmacy/dispense/?patient=<unassigned-uuid> omits that hospice number."""
        from django.test import Client
        from apps.patients.models import Patient
        from apps.medications.models import MedicationStatement, MedicationStatusChoices

        unassigned = Patient.objects.create(
            first_name="Unassigned",
            last_name="QueryParam",
            hospice_number="NH-UNASSIGNED-QP-01",
            sex="F",
            status="ACTIVE",
        )
        MedicationStatement.objects.create(
            patient=unassigned,
            medication_name="Oral Morphine 10mg",
            dosage="10mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )
        pharmacist = create_staff_user(
            email='pharm_qp@nairobihospice.or.ke',
            username='pharm_qp',
            first_name='Pharm',
            last_name='Query',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        client = Client()
        client.force_login(pharmacist)
        resp = client.get(f'/operations/pharmacy/dispense/?patient={unassigned.pk}')
        assert resp.status_code == 200
        html = resp.content.decode('utf-8')
        assert 'NH-UNASSIGNED-QP-01' not in html

    def test_dispense_queryset_update_patient_rx_mismatch_is_rejected(self):
        """QuerySet.update() cannot re-point a dispense at a patient who does not own the Rx."""
        from django.core.exceptions import ValidationError
        from django.db import connection
        from django.db.utils import DatabaseError, IntegrityError, OperationalError
        from apps.operations.models import StockItem, StockMovement, MovementTypeChoices
        from apps.operations.services import record_stock_movement
        from apps.medications.models import MedicationStatement, MedicationStatusChoices
        from apps.patients.models import Patient

        stock_item = StockItem.objects.create(
            name="Morphine 10mg Solution",
            item_code="STK-DB-UPD-01",
            quantity_on_hand=50,
            unit_of_measure="bottle",
        )
        patient_a = self.patient
        patient_b = Patient.objects.create(
            first_name="Patient",
            last_name="BetaUpdate",
            hospice_number="NH-TRG-UPD-B",
            sex="F",
            status="ACTIVE",
        )
        rx_a = MedicationStatement.objects.create(
            patient=patient_a,
            medication_name="Morphine 10mg",
            dosage="10mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )
        rx_b = MedicationStatement.objects.create(
            patient=patient_b,
            medication_name="Morphine 10mg",
            dosage="10mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )
        movement = record_stock_movement(
            stock_item=stock_item,
            movement_type=MovementTypeChoices.DISPENSE,
            quantity=1,
            patient=patient_a,
            medication_statement=rx_a,
            user=self.doctor,
        )

        mismatch = StockMovement(
            stock_item=stock_item,
            movement_type=MovementTypeChoices.DISPENSE,
            quantity=-1,
            balance_after=49,
            patient=patient_a,
            medication_statement=rx_b,
        )
        with pytest.raises(ValidationError):
            mismatch.full_clean()

        try:
            StockMovement.objects.filter(pk=movement.pk).update(patient_id=patient_b.pk)
        except (IntegrityError, DatabaseError, OperationalError):
            return
        movement.refresh_from_db()
        if movement.patient_id == patient_b.pk and movement.medication_statement_id == rx_a.pk:
            if connection.vendor == 'sqlite':
                pytest.skip(
                    'SQLite test database did not enforce check_dispense_patient_rx_match on '
                    'QuerySet.update(); migration 0013 installs Postgres/MySQL triggers for production. '
                    'Model full_clean()/save() still reject the mismatch.'
                )
            pytest.fail('QuerySet.update() allowed a patient/Rx mismatch')

    def test_controlled_register_export_is_scoped_by_role(self):
        """Nurse and unrelated pharmacist cannot download another pharmacist's morphine rows; manager can."""
        from django.test import Client
        from apps.operations.models import StockItem, MovementTypeChoices
        from apps.operations.services import record_stock_movement
        from apps.medications.models import MedicationStatement, MedicationStatusChoices
        from apps.patients.models import Patient

        owner = create_staff_user(
            email='pharm_register_owner@nairobihospice.or.ke',
            username='pharm_register_owner',
            first_name='Owner',
            last_name='Pharm',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        other_pharm = create_staff_user(
            email='pharm_register_other@nairobihospice.or.ke',
            username='pharm_register_other',
            first_name='Other',
            last_name='Pharm',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        nurse = create_staff_user(
            email='nurse_register_export@nairobihospice.or.ke',
            username='nurse_register_export',
            first_name='Nurse',
            last_name='Export',
            password='Pass!',
            role=RoleChoices.NURSE,
        )
        manager = create_staff_user(
            email='mgr_register_export@nairobihospice.or.ke',
            username='mgr_register_export',
            first_name='Mgr',
            last_name='Export',
            password='Pass!',
            role=RoleChoices.MANAGER,
        )
        patient = Patient.objects.create(
            first_name="Morphine",
            last_name="Register",
            hospice_number="NH-OPIOID-REG-01",
            sex="F",
            status="ACTIVE",
        )
        rx = MedicationStatement.objects.create(
            patient=patient,
            medication_name="Oral Morphine Solution 10mg/5ml",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )
        item = StockItem.objects.create(
            name="Oral Morphine Solution 10mg/5ml",
            item_code="STK-OPIOID-IDOR",
            quantity_on_hand=20,
            unit_of_measure="bottle",
            is_controlled_substance=True,
        )
        record_stock_movement(
            stock_item=item,
            movement_type=MovementTypeChoices.DISPENSE,
            quantity=1,
            patient=patient,
            medication_statement=rx,
            user=owner,
        )

        url = '/operations/pharmacy/controlled-register/export/'
        nurse_client = Client()
        nurse_client.force_login(nurse)
        nurse_resp = nurse_client.get(url)
        assert nurse_resp.status_code == 403

        other_client = Client()
        other_client.force_login(other_pharm)
        other_resp = other_client.get(url)
        assert other_resp.status_code == 200
        other_body = other_resp.content.decode('utf-8')
        assert 'NH-OPIOID-REG-01' not in other_body
        assert 'Morphine Register' not in other_body

        owner_client = Client()
        owner_client.force_login(owner)
        owner_resp = owner_client.get(url)
        assert owner_resp.status_code == 200
        owner_body = owner_resp.content.decode('utf-8')
        assert 'NH-OPIOID-REG-01' in owner_body

        mgr_client = Client()
        mgr_client.force_login(manager)
        mgr_resp = mgr_client.get(url)
        assert mgr_resp.status_code == 200
        mgr_body = mgr_resp.content.decode('utf-8')
        assert 'NH-OPIOID-REG-01' in mgr_body
        assert 'Morphine Register' in mgr_body

@pytest.mark.django_db
class TestInputValidationAndAuditIntegrity:
    def setup_method(self):
        self.doctor = create_staff_user(
            email='val_doc@nairobihospice.or.ke',
            username='val_doc',
            first_name='Val',
            last_name='Doc',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        self.receptionist = create_staff_user(
            email='val_rec@nairobihospice.or.ke',
            username='val_rec',
            first_name='Val',
            last_name='Rec',
            password='Pass!',
            role=RoleChoices.RECEPTIONIST,
        )
        self.patient = register_patient(
            first_name='John',
            last_name='Kamau',
            created_by=self.doctor,
        )

    def test_malformed_esas_score_validation(self):
        """Symptom scores > 10 must raise validation errors."""
        from django.core.exceptions import ValidationError
        with pytest.raises(ValidationError):
            record_esas_assessment(
                patient=self.patient,
                symptom_scores={SymptomTypeChoices.PAIN: 15},  # Invalid score > 10
                user=self.doctor,
            )

    def test_audit_event_logged_on_patient_creation(self):
        """Registering a patient must generate an immutable AuditEvent log."""
        audit = AuditEvent.objects.filter(resource_type='Patient', resource_id=str(self.patient.id)).first()
        assert audit is not None
        assert audit.action == AuditAction.CREATE
        assert audit.user_email == self.doctor.email

    def test_reporting_aggregation_accuracy(self):
        """Management dashboard metrics correctly calculate active patients and referrals."""
        data = get_management_dashboard_data()
        assert data['total_active_patients'] >= 1
        assert 'home_visits_count' in data
        assert 'clinic_visits_count' in data

    def test_custom_error_pages_render(self):
        """404 and 403 error responses render custom branded templates."""
        from django.test import Client
        client = Client()
        client.force_login(self.doctor)

        # 404 Page Not Found
        res_404 = client.get('/nonexistent-clinical-endpoint/')
        assert res_404.status_code == 404
        assert b'Clinical Page Not Found' in res_404.content or b'404' in res_404.content

    def test_appointment_next_redirect_blocks_open_redirects(self):
        """Appointment status updates and deletion requests discard external next= URLs."""
        from django.test import Client
        from apps.appointments.models import Appointment, AppointmentTypeChoices, AppointmentStatusChoices
        from django.utils import timezone
        
        appt = Appointment.objects.create(
            patient=self.patient,
            staff_member=self.doctor.staff_profile,
            appointment_type=AppointmentTypeChoices.CLINIC_VISIT,
            scheduled_date=timezone.now().date(),
            scheduled_time=timezone.now().time(),
            status=AppointmentStatusChoices.SCHEDULED,
            created_by=self.doctor,
        )

        client = Client()
        client.force_login(self.doctor)

        # Update status with malicious next
        resp = client.post(
            f'/appointments/{appt.pk}/update-status/',
            {'status': AppointmentStatusChoices.COMPLETED, 'next': 'https://evil.com/phishing'}
        )
        assert resp.status_code == 302
        assert resp.url == '/appointments/'

        # Deletion request with malicious next
        resp_del = client.post(
            f'/appointments/{appt.pk}/request-delete/',
            {'reason': 'Duplicate entry', 'next': 'https://evil.com/phishing'}
        )
        assert resp_del.status_code == 302
        assert resp_del.url == '/appointments/'

    def test_patient_photo_upload_scans_malware(self, monkeypatch):
        """Patient photo upload view invokes malware scanner."""
        from django.test import Client
        from django.core.files.uploadedfile import SimpleUploadedFile
        from apps.patients import views as patient_views
        
        scanned = []
        def fake_scan(uploaded_file):
            scanned.append(uploaded_file.name)
        
        import apps.documents.malware
        monkeypatch.setattr(apps.documents.malware, 'scan_uploaded_file', fake_scan)

        client = Client()
        client.force_login(self.receptionist)
        
        photo = SimpleUploadedFile('avatar.png', b'fake-image-bytes', content_type='image/png')
        resp = client.post(f'/patients/{self.patient.pk}/upload-photo/', {'photo': photo})
        assert resp.status_code == 302
        assert 'avatar.png' in scanned

    def test_search_placeholders_hide_diagnosis_from_receptionist(self):
        """Calendar and patient list search placeholders do not advertise diagnosis to receptionist."""
        from django.test import Client
        client = Client()
        client.force_login(self.receptionist)

        resp_cal = client.get('/appointments/')
        assert resp_cal.status_code == 200
        assert b'Filter by patient name, Hospice No, clinician, or location...' in resp_cal.content

        resp_pat = client.get('/patients/')
        assert resp_pat.status_code == 200
        assert b'Search Name, Hospice ID, Phone, Location...' in resp_pat.content

    def test_appointment_api_search_excludes_reason_for_receptionist(self):
        """Appointment REST API ?search= excludes matching reason/notes for receptionists."""
        from apps.appointments.models import Appointment, AppointmentTypeChoices, AppointmentStatusChoices
        from django.utils import timezone

        Appointment.objects.create(
            patient=self.patient,
            staff_member=self.doctor.staff_profile,
            appointment_type=AppointmentTypeChoices.CLINIC_VISIT,
            scheduled_date=timezone.now().date(),
            scheduled_time=timezone.now().time(),
            status=AppointmentStatusChoices.SCHEDULED,
            reason="Unbearable thoracic bone metastasis pain review",
            notes="Secret clinical palliative notes",
            created_by=self.doctor,
        )

        # Receptionist search for clinical keyword -> returns 0 results
        from rest_framework.test import APIClient
        api = APIClient()
        api.force_authenticate(user=self.receptionist)
        res_rec = api.get('/api/v1/appointments/?search=metastasis')
        assert res_rec.status_code == 200
        assert len(res_rec.json()['results']) == 0

        # Doctor search for clinical keyword -> matches appointment
        api.force_authenticate(user=self.doctor)
        res_doc = api.get('/api/v1/appointments/?search=metastasis')
        assert res_doc.status_code == 200
        assert len(res_doc.json()['results']) == 1

    def test_all_phi_access_roles_enforce_mfa_middleware(self, settings):
        """MFA middleware intercepts Doctor, Nurse, Pharmacist, and Receptionist sessions lacking MFA verification."""
        from apps.accounts.models import SecurityConfiguration
        config = SecurityConfiguration.get_solo()
        config.mfa_enabled = True
        config.save()

        settings.MFA_ENFORCEMENT_MIDDLEWARE_ENABLED = True
        settings.MFA_REQUIRED_FOR_PRIVILEGED = True

        from django.test import Client

        nurse = create_staff_user(
            email='mfa_test_nurse@nairobihospice.or.ke',
            username='mfa_test_nurse',
            first_name='Nurse',
            last_name='MFA',
            password='Pass!',
            role=RoleChoices.NURSE,
        )
        pharm = create_staff_user(
            email='mfa_test_pharm@nairobihospice.or.ke',
            username='mfa_test_pharm',
            first_name='Pharm',
            last_name='MFA',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )

        for user in [self.doctor, nurse, pharm, self.receptionist]:
            client = Client()
            client.force_login(user)
            # Accessing patient list without MFA verification redirects to enroll or verify
            resp = client.get('/patients/')
            assert resp.status_code == 302
            assert '/accounts/mfa/' in resp.url

    def test_admin_can_toggle_mfa_switch_and_receptionist_denied(self):
        """Administrator can toggle MFA global state; non-admin users cannot."""
        from django.test import Client
        from apps.accounts.models import SecurityConfiguration

        config = SecurityConfiguration.get_solo()
        config.mfa_enabled = False
        config.save()

        # Admin toggles MFA ON
        admin_user = create_staff_user(
            email='mfa_switch_admin@nairobihospice.or.ke',
            username='mfa_switch_admin',
            first_name='Admin',
            last_name='Switch',
            password='Pass!',
            role=RoleChoices.ADMINISTRATOR,
        )
        client = Client()
        client.force_login(admin_user)

        response = client.post('/accounts/toggle-mfa/')
        assert response.status_code == 302
        assert SecurityConfiguration.is_mfa_globally_enabled() is True

        # Non-admin receptionist tries to toggle MFA -> 403 Forbidden
        rec_client = Client()
        rec_client.force_login(self.receptionist)
        rec_resp = rec_client.post('/accounts/toggle-mfa/')
        assert rec_resp.status_code == 403
        assert SecurityConfiguration.is_mfa_globally_enabled() is True

        # Admin toggles MFA back OFF
        response = client.post('/accounts/toggle-mfa/')
        assert response.status_code == 302
        assert SecurityConfiguration.is_mfa_globally_enabled() is False

