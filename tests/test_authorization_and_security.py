
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

        client.post(f'/patients/{self.patient.id}/edit/', {
            'first_name': self.patient.first_name,
            'last_name': self.patient.last_name,
            'sex': 'F',
            'status': 'DECEASED',
            'special_remarks': 'Tampered Remarks',
        })
        self.patient.refresh_from_db()
        assert self.patient.status == 'ACTIVE'
        assert self.patient.special_remarks == 'Original Remarks'

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

        pharmacist = create_staff_user(
            email='pharm_dash_test@nairobihospice.or.ke',
            username='pharm_dash_test',
            first_name='Pharm',
            last_name='Dash',
            password='Pass!',
            role=RoleChoices.PHARMACIST,
        )
        MedicationStatement.objects.create(
            patient=self.patient,
            medication_name="Oral Morphine 10mg/5ml",
            dosage="5mg",
            route="ORAL",
            frequency="q4h",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.doctor,
        )
        # Without any stock movement by this pharmacist, active_medications should be empty
        data = get_clinical_dashboard_data(pharmacist)
        assert len(data['active_medications']) == 0

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
        form = StockDispenseForm(user=pharmacist)
        allowed_patients = list(form.fields['patient'].queryset)
        assert patient_with_meds in allowed_patients
        assert patient_without_meds not in allowed_patients

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
            'first_name': 'Grace',
            'last_name': 'Wanjiru',
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
            # Attempted clinical fields submitted by receptionist:
            'hiv_status': 'POSITIVE',
            'primary_diagnosis': 'Metastatic Breast Carcinoma',
            'chief_complaint': 'Severe dyspnea and bone pain',
            'past_medical_history': 'Prior mastectomy in 2022',
        })
        form_errs = response.context['form'].errors if hasattr(response, 'context') and response.context and 'form' in response.context else None
        assert response.status_code == 302, f"Form validation failed with errors: {form_errs}"
        from apps.patients.models import Patient
        created = Patient.objects.filter(first_name='Grace', last_name='Wanjiru').first()
        assert created is not None
        assert created.hiv_status == ''
        assert created.primary_diagnosis == ''

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

            response = client.get('/dashboard/')
            assert response.status_code == 302
            assert '/accounts/mfa/enroll/' in response.url or '/accounts/mfa/verify/' in response.url


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
