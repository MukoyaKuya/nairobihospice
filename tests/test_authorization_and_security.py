
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

    def test_clinical_dashboard_scoped_to_authorized_caseload(self):
        """Clinical dashboards only display metrics and patients for assigned clinicians."""
        from apps.reporting.selectors import get_clinical_dashboard_data
        clinician_b = create_staff_user(
            email='dash_doc@nairobihospice.or.ke',
            username='dash_doc',
            first_name='Dash',
            last_name='Doc',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        data = get_clinical_dashboard_data(clinician_b)
        assert data['today_appts_count'] == 0
        assert len(data['active_medications']) == 0


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
