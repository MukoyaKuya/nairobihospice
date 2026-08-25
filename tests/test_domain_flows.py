from datetime import date, timedelta

import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import RoleChoices
from apps.accounts.services import create_staff_user
from apps.appointments.models import AppointmentStatusChoices, AppointmentTypeChoices
from apps.appointments.services import schedule_appointment
from apps.assessments.models import AssessmentTypeChoices
from apps.assessments.services import amend_assessment, record_assessment
from apps.audit.models import AuditAction, AuditEvent
from apps.care.models import EpisodeStatusChoices
from apps.encounters.models import EncounterTypeChoices
from apps.encounters.services import record_encounter
from apps.medications.models import MedicationStatusChoices
from apps.medications.services import prescribe_medication, update_medication_status
from apps.patients.models import PatientStatusChoices, SexChoices
from apps.patients.services import generate_hospice_number, register_patient
from apps.referrals.models import ReferralPriorityChoices, ReferralStatusChoices
from apps.referrals.services import convert_referral_to_patient, create_referral
from apps.symptoms.models import SymptomTypeChoices
from apps.symptoms.services import record_esas_assessment


@pytest.mark.django_db
class TestAccountsAndRBAC:
    def test_create_staff_user_doctor(self):
        user = create_staff_user(
            email='testdoc@nairobihospice.or.ke',
            username='testdoc',
            first_name='Test',
            last_name='Doctor',
            password='TestPassword123!',
            role=RoleChoices.DOCTOR,
            license_number='KMPDC-999',
        )
        assert user.role == RoleChoices.DOCTOR
        assert user.is_doctor is True
        assert user.is_clinical is True
        assert user.is_nurse is False

    def test_receptionist_cannot_access_management_dashboard(self):
        user = create_staff_user(
            email='testrec@nairobihospice.or.ke',
            username='testrec',
            first_name='Test',
            last_name='Receptionist',
            password='TestPassword123!',
            role=RoleChoices.RECEPTIONIST,
        )
        client = Client()
        client.force_login(user)
        response = client.get(reverse('reporting:management_dashboard'))
        assert response.status_code == 403

    def test_clinical_dashboard_and_navigation_renders_for_receptionist(self):
        user = create_staff_user(
            email='testrec2@nairobihospice.or.ke',
            username='testrec2',
            first_name='Reception',
            last_name='Staff',
            password='TestPassword123!',
            role=RoleChoices.RECEPTIONIST,
        )
        client = Client()
        client.force_login(user)
        response = client.get(reverse('reporting:clinical_dashboard'))
        assert response.status_code == 200

        # Check navigation pages
        care_res = client.get(reverse('care:care_plan_list'))
        assert care_res.status_code == 200

        med_res = client.get(reverse('medications:medication_list'))
        assert med_res.status_code == 200

        ref_res = client.get(reverse('referrals:referral_list'))
        assert ref_res.status_code == 200

    def test_all_role_dashboards_render_specialized_widgets(self):
        roles_to_test = [
            (RoleChoices.NURSE, "Today's Home Route"),
            (RoleChoices.DOCTOR, "Today's Consultations"),
            (RoleChoices.PHARMACIST, "Active Prescriptions"),
            (RoleChoices.SOCIAL_WORKER, "Psychosocial Caseload"),
        ]

        for role, expected_text in roles_to_test:
            user = create_staff_user(
                email=f'test_{role.lower()}@nairobihospice.or.ke',
                username=f'test_{role.lower()}',
                first_name='Role',
                last_name=role.title(),
                password='TestPassword123!',
                role=role,
            )
            client = Client()
            client.force_login(user)
            res = client.get(reverse('reporting:clinical_dashboard'))
            assert res.status_code == 200
            assert expected_text in res.content.decode('utf-8')


@pytest.mark.django_db
class TestPatientDomain:
    def test_hospice_number_generation(self):
        num = generate_hospice_number()
        year = date.today().year
        assert num.startswith(f"NH-{year}-")

    def test_register_patient_service(self):
        user = create_staff_user(
            email='nurse1@nairobihospice.or.ke',
            username='nurse1',
            first_name='Nurse',
            last_name='One',
            password='Pass!',
            role=RoleChoices.NURSE,
        )
        patient = register_patient(
            first_name='Kipchirchir',
            last_name='Koech',
            date_of_birth=date(1980, 1, 1),
            sex=SexChoices.MALE,
            county='Nairobi',
            primary_diagnosis='Ca Prostate Stage IV',
            allergies='None',
            created_by=user,
            nok_name='Hellen Koech',
            nok_relationship='Spouse',
            nok_phone='+254700000000',
        )
        assert patient.status == PatientStatusChoices.ACTIVE
        assert patient.next_of_kin.count() == 1
        assert patient.next_of_kin.first().name == 'Hellen Koech'

        # Verify audit event logged
        audit = AuditEvent.objects.filter(resource_type='Patient', resource_id=str(patient.id)).first()
        assert audit is not None
        assert audit.action == AuditAction.CREATE

    def test_search_patients_with_filters(self):
        from apps.patients.selectors import search_patients
        doc = create_staff_user(
            email='filter_doc@nairobihospice.or.ke',
            username='filter_doc',
            first_name='Filter',
            last_name='Doc',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        p_female = register_patient(
            first_name='Amina',
            last_name='Hassan',
            date_of_birth=date(1995, 5, 20),
            sex=SexChoices.FEMALE,
            county='Mombasa',
            primary_diagnosis='Ca Colon',
            created_by=doc,
        )
        p_male = register_patient(
            first_name='Jackson',
            last_name='Ochieng',
            date_of_birth=date(1955, 3, 10),
            sex=SexChoices.MALE,
            county='Kisumu',
            primary_diagnosis='Ca Prostate',
            created_by=doc,
        )

        # Filter by sex
        females = search_patients(sex='F')
        assert p_female in females
        assert p_male not in females

        males = search_patients(sex='M')
        assert p_male in males
        assert p_female not in males

        # Filter by county
        mombasa_pts = search_patients(county='Mombasa')
        assert p_female in mombasa_pts
        assert p_male not in mombasa_pts

        # Filter by age group
        senior_pts = search_patients(age_group='senior')
        assert p_male in senior_pts
        assert p_female not in senior_pts

        youth_pts = search_patients(age_group='youth')
        assert p_female in youth_pts
        assert p_male not in youth_pts


@pytest.mark.django_db
class TestReferralAndConversion:
    def test_create_and_convert_referral(self):
        doc = create_staff_user(
            email='doc1@nairobihospice.or.ke',
            username='doc1',
            first_name='Doctor',
            last_name='One',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        referral = create_referral(
            patient_name='Alice Mutindi',
            referring_facility='Mater Hospital',
            primary_diagnosis='Breast Ca Stage IV',
            reason_for_referral='Pain titration and home hospice visits',
            priority=ReferralPriorityChoices.URGENT,
            created_by=doc,
        )
        nurse = create_staff_user(
            email='conv_nurse1@nairobihospice.or.ke',
            username='conv_nurse1',
            first_name='Nurse',
            last_name='One',
            password='Pass!',
            role=RoleChoices.NURSE,
        )
        # Convert to patient
        patient = convert_referral_to_patient(
            referral=referral,
            user=doc,
            primary_nurse=nurse.staff_profile,
            primary_doctor=doc.staff_profile,
        )
        referral.refresh_from_db()
        assert referral.status == ReferralStatusChoices.CONVERTED
        assert referral.converted_patient == patient
        assert patient.first_name == 'Alice'
        assert patient.last_name == 'Mutindi'
        assert patient.episodes.filter(status=EpisodeStatusChoices.ACTIVE).count() == 1


@pytest.mark.django_db
class TestClinicalCareEncountersAndAssessments:
    def test_encounter_recording(self):
        doc = create_staff_user(
            email='doc2@nairobihospice.or.ke',
            username='doc2',
            first_name='Doctor',
            last_name='Two',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        patient = register_patient(first_name='Paul', last_name='Ouma', created_by=doc)
        encounter = record_encounter(
            patient=patient,
            encounter_type=EncounterTypeChoices.HOME_VISIT,
            reason='Routine home follow-up',
            clinical_notes='Patient stable, resting comfortably. Pain controlled.',
            location='Kibera Makina',
            user=doc,
        )
        assert encounter.patient == patient
        assert encounter.encounter_type == EncounterTypeChoices.HOME_VISIT

    def test_esas_symptom_scores_and_distress_calculation(self):
        doc = create_staff_user(
            email='doc3@nairobihospice.or.ke',
            username='doc3',
            first_name='Doctor',
            last_name='Three',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        patient = register_patient(first_name='Fatuma', last_name='Ali', created_by=doc)
        scores = {
            SymptomTypeChoices.PAIN: 7,
            SymptomTypeChoices.TIREDNESS: 5,
            SymptomTypeChoices.NAUSEA: 3,
            SymptomTypeChoices.WELLBEING: 6,
        }
        rec = record_esas_assessment(
            patient=patient,
            symptom_scores=scores,
            clinical_notes='Baseline ESAS assessment',
            user=doc,
        )
        assert rec.total_distress_score == 21
        assert rec.scores.count() == 4

    def test_assessment_amendment_integrity(self):
        doc = create_staff_user(
            email='doc4@nairobihospice.or.ke',
            username='doc4',
            first_name='Doctor',
            last_name='Four',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        patient = register_patient(first_name='George', last_name='Ndungu', created_by=doc)
        assessment = record_assessment(
            patient=patient,
            assessment_type=AssessmentTypeChoices.INITIAL,
            clinical_summary='Initial impression: Stable with moderate pain.',
            pain_score=5,
            user=doc,
        )
        amendment = amend_assessment(
            assessment=assessment,
            reason_for_amendment='Correction of pain radiation findings',
            updated_summary='Initial impression: Stable. Pain radiates to left hip.',
            user=doc,
        )
        assessment.refresh_from_db()
        assert 'AMENDMENT' in assessment.clinical_summary
        assert amendment.assessment == assessment
        assert assessment.amendments.count() == 1


@pytest.mark.django_db
class TestMedicationAndAppointmentLifecycle:
    def test_medication_prescription_and_discontinuation(self):
        doc = create_staff_user(
            email='doc5@nairobihospice.or.ke',
            username='doc5',
            first_name='Doctor',
            last_name='Five',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        patient = register_patient(first_name='Lucy', last_name='Wairimu', created_by=doc)
        med = prescribe_medication(
            patient=patient,
            medication_name='Oral Morphine Solution 5mg/5ml',
            dosage='10mg',
            frequency='q4h',
            indication='Severe cancer pain',
            user=doc,
        )
        assert med.status == MedicationStatusChoices.ACTIVE

        # Discontinue
        update_medication_status(
            medication=med,
            status=MedicationStatusChoices.DISCONTINUED,
            reason='Switching to higher concentration',
            user=doc,
        )
        med.refresh_from_db()
        assert med.status == MedicationStatusChoices.DISCONTINUED
        from django.utils import timezone
        assert med.end_date == timezone.now().date()

    def test_schedule_appointment(self):
        nurse = create_staff_user(
            email='nurse2@nairobihospice.or.ke',
            username='nurse2',
            first_name='Nurse',
            last_name='Two',
            password='Pass!',
            role=RoleChoices.NURSE,
        )
        patient = register_patient(first_name='Titus', last_name='Kariuki', created_by=nurse)
        appt = schedule_appointment(
            patient=patient,
            staff_member=nurse.profile,
            appointment_type=AppointmentTypeChoices.HOME_VISIT,
            scheduled_date=date.today() + timedelta(days=3),
            reason='Wound dressing review',
            user=nurse,
        )
        assert appt.status == AppointmentStatusChoices.SCHEDULED
        assert appt.patient == patient


@pytest.mark.django_db
class TestAPIEndpoints:
    def test_api_patients_list(self):
        doc = create_staff_user(
            email='api_doc@nairobihospice.or.ke',
            username='api_doc',
            first_name='API',
            last_name='Doctor',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        register_patient(first_name='API', last_name='Patient', created_by=doc)
        client = Client()
        client.force_login(doc)
        response = client.get('/api/v1/patients/')
        assert response.status_code == 200
        assert 'results' in response.json()


@pytest.mark.django_db(transaction=True)
class TestReceptionistWorkflowAndNotifications:
    def test_receptionist_registers_patient_alerts_doctor_and_nurse(self):
        from apps.notifications.models import Notification, NotificationTypeChoices

        # Set up Doctor and Nurse
        doctor = create_staff_user(
            email='alert_doc@nairobihospice.or.ke',
            username='alert_doc',
            first_name='Faith',
            last_name='Kariuki',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        nurse = create_staff_user(
            email='alert_nurse@nairobihospice.or.ke',
            username='alert_nurse',
            first_name='Mary',
            last_name='Wambui',
            password='Pass!',
            role=RoleChoices.NURSE,
        )
        receptionist = create_staff_user(
            email='alert_rec@nairobihospice.or.ke',
            username='alert_rec',
            first_name='Jane',
            last_name='Receptionist',
            password='Pass!',
            role=RoleChoices.RECEPTIONIST,
        )

        # Receptionist registers a new patient
        register_patient(
            first_name='Ezekiel',
            last_name='Mutua',
            county='Nairobi',
            primary_diagnosis='Ca Esophagus Stage III',
            created_by=receptionist,
        )

        # Verify Doctor got notification
        doc_notif = Notification.objects.filter(
            recipient=doctor,
            notification_type=NotificationTypeChoices.NEW_PATIENT_REGISTERED
        ).first()
        assert doc_notif is not None
        assert 'Ezekiel Mutua' in doc_notif.title
        assert 'Ca Esophagus' not in doc_notif.message

        # Verify Nurse got notification
        nurse_notif = Notification.objects.filter(
            recipient=nurse,
            notification_type=NotificationTypeChoices.NEW_PATIENT_REGISTERED
        ).first()
        assert nurse_notif is not None
        assert 'Ezekiel Mutua' in nurse_notif.title

        # Verify Receptionist (author) did NOT get spammed
        rec_notif = Notification.objects.filter(
            recipient=receptionist,
            notification_type=NotificationTypeChoices.NEW_PATIENT_REGISTERED
        ).first()
        assert rec_notif is None

    def test_scheduling_appointment_alerts_assigned_staff(self):
        from apps.notifications.models import Notification, NotificationTypeChoices

        nurse = create_staff_user(
            email='sched_nurse@nairobihospice.or.ke',
            username='sched_nurse',
            first_name='Agnes',
            last_name='Mwangi',
            password='Pass!',
            role=RoleChoices.NURSE,
        )
        receptionist = create_staff_user(
            email='sched_rec@nairobihospice.or.ke',
            username='sched_rec',
            first_name='Paul',
            last_name='Reception',
            password='Pass!',
            role=RoleChoices.RECEPTIONIST,
        )
        patient = register_patient(first_name='Samuel', last_name='Gikonyo', created_by=receptionist)

        # Schedule appointment assigned to nurse
        schedule_appointment(
            patient=patient,
            staff_member=nurse.profile,
            appointment_type=AppointmentTypeChoices.HOME_VISIT,
            scheduled_date=date.today() + timedelta(days=2),
            reason='Initial home palliative review',
            user=receptionist,
        )

        # Check nurse received appointment alert
        nurse_alert = Notification.objects.filter(
            recipient=nurse,
            notification_type=NotificationTypeChoices.NEW_APPOINTMENT_SCHEDULED
        ).first()
        assert nurse_alert is not None
        assert 'Samuel Gikonyo' in nurse_alert.title

    def test_unread_badge_htmx_endpoint(self):
        doc = create_staff_user(
            email='badge_doc@nairobihospice.or.ke',
            username='badge_doc',
            first_name='Badge',
            last_name='Doc',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        client = Client()
        client.force_login(doc)
        response = client.get('/notifications/badge/')
        assert response.status_code == 200
        assert b'notification-bell-container' in response.content

    def test_patient_workspace_all_tabs_render_data(self):
        from apps.care.models import CarePlan, CareTeamMember, CareTeamRoleChoices
        from apps.communications.models import CommunicationRecord
        from apps.encounters.services import record_encounter
        from apps.medications.services import prescribe_medication
        from apps.symptoms.services import record_esas_assessment

        doc = create_staff_user(
            email='tab_doc@nairobihospice.or.ke',
            username='tab_doc',
            first_name='Tab',
            last_name='Doctor',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        nurse = create_staff_user(
            email='tab_nurse@nairobihospice.or.ke',
            username='tab_nurse',
            first_name='Tab',
            last_name='Nurse',
            password='Pass!',
            role=RoleChoices.NURSE,
        )

        patient = register_patient(
            first_name='TabPatient',
            last_name='Tester',
            primary_diagnosis='Ca Cervix Stage IV',
            created_by=doc,
        )

        # 1. Log encounter
        record_encounter(
            patient=patient,
            encounter_type=EncounterTypeChoices.CLINIC_VISIT,
            reason='Initial holistic assessment',
            clinical_notes='Patient in moderate pain.',
            user=doc,
        )

        # 2. Care plan & Care team
        episode = patient.episodes.filter(status='ACTIVE').first()
        assert episode is not None
        CarePlan.objects.create(
            patient=patient,
            episode=episode,
            title='Comprehensive Palliative Care Plan',
            overall_goals='Pain relief and psychological family support',
            created_by=doc,
        )
        CareTeamMember.objects.create(
            episode=episode,
            staff_member=nurse.profile,
            role=CareTeamRoleChoices.PRIMARY_NURSE,
            is_primary=True,
        )

        # 3. ESAS evaluation
        record_esas_assessment(
            patient=patient,
            symptom_scores={SymptomTypeChoices.PAIN: 8, SymptomTypeChoices.TIREDNESS: 6},
            clinical_notes='Severe bone pain reported',
            user=doc,
        )

        # 4. Medication
        prescribe_medication(
            patient=patient,
            medication_name='Morphine Sulfate 10mg/5ml',
            dosage='5mg',
            frequency='q4h',
            indication='Severe visceral pain',
            user=doc,
        )

        # 5. Communication
        CommunicationRecord.objects.create(
            patient=patient,
            contact_person='Mary Tester (Daughter)',
            summary='Discussed palliative home plan and caregiver routine.',
            recorded_by=doc,
        )

        client = Client()
        client.force_login(doc)
        response = client.get(f'/patients/{patient.pk}/')
        assert response.status_code == 200

        content = response.content.decode('utf-8')
        # Check Tab 1: Timeline
        assert 'Clinical Timeline &amp; Encounters (1)' in content or 'Clinical Timeline & Encounters (1)' in content
        assert 'Initial holistic assessment' in content

        # Check Tab 2: Care Plan & Team
        assert 'Comprehensive Palliative Care Plan' in content
        assert 'Tab Nurse' in content

        # Check Tab 3: ESAS Symptoms
        assert 'ESAS Symptom Trends (1)' in content
        assert 'Distress: 14/100' in content

        # Check Tab 4: Medications
        assert 'Medications (1)' in content
        assert 'Morphine Sulfate 10mg/5ml' in content

        # Check Tab 5: Documents & Calls
        assert 'Mary Tester (Daughter)' in content

    def test_doctor_creates_care_plan_via_web_view(self):
        doc = create_staff_user(
            email='doc_cp@nairobihospice.or.ke',
            username='doc_cp',
            first_name='Doctor',
            last_name='Careplan',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        patient = register_patient(first_name='George', last_name='Kamau', created_by=doc)

        client = Client()
        client.force_login(doc)

        # 1. Post to patient-specific care plan create view
        response = client.post(f'/care/patient/{patient.pk}/care-plan/create/', {
            'title': 'Individualized Palliative Care Plan',
            'primary_diagnosis': 'Stage IV Prostate Carcinoma',
            'overall_goals': 'Optimal symptom and pain relief with home care team visits',
            'resuscitation_preference': 'Allow Natural Death (AND) / Comfort Measures',
            'review_date': '2026-09-30',
            'status': 'ACTIVE',
        })
        assert response.status_code == 302
        assert patient.care_plans.filter(status='ACTIVE').count() == 1
        cp = patient.care_plans.first()
        assert cp.overall_goals == 'Optimal symptom and pain relief with home care team visits'
        assert cp.created_by == doc

        # 2. Post to generic care plan create view
        patient2 = register_patient(first_name='Grace', last_name='Wanjiku', created_by=doc)
        response2 = client.post('/care/create/', {
            'patient': str(patient2.pk),
            'title': 'Holistic Psychosocial & Pain Management Plan',
            'primary_diagnosis': 'Cervical Cancer Stage IIIB',
            'overall_goals': 'Pain titration and bereavement preparation',
            'resuscitation_preference': 'Allow Natural Death (AND)',
            'status': 'ACTIVE',
        })
        assert response2.status_code == 302
        assert patient2.care_plans.filter(status='ACTIVE').count() == 1

    def test_referral_conversion_requires_explicit_care_team(self):
        """Converting a referral creates an active episode with explicitly chosen nurse and doctor."""
        from apps.referrals.models import Referral, ReferralPriorityChoices, ReferralStatusChoices
        from apps.care.models import CareTeamRoleChoices, EpisodeOfCare

        doc = create_staff_user(
            email='conv_doc@nairobihospice.or.ke',
            username='conv_doc',
            first_name='Conversion',
            last_name='Doctor',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        nurse = create_staff_user(
            email='conv_nurse@nairobihospice.or.ke',
            username='conv_nurse',
            first_name='Conversion',
            last_name='Nurse',
            password='Pass!',
            role=RoleChoices.NURSE,
        )
        referral = Referral.objects.create(
            patient_name='Bernard Kibet',
            sex='MALE',
            phone_number='0711998877',
            priority=ReferralPriorityChoices.URGENT,
            status=ReferralStatusChoices.UNDER_REVIEW,
            primary_diagnosis='Multiple Myeloma',
            reason_for_referral='Pain crisis management',
            created_by=doc,
        )

        client = Client()
        client.force_login(doc)

        # 1. Post without care team fails/redirects with error
        response_missing = client.post(f'/referrals/{referral.pk}/convert/', {})
        assert response_missing.status_code == 302
        referral.refresh_from_db()
        assert referral.status == ReferralStatusChoices.UNDER_REVIEW

        # 2. Post with explicit nurse and doctor succeeds
        response_valid = client.post(f'/referrals/{referral.pk}/convert/', {
            'primary_nurse': str(nurse.staff_profile.id),
            'primary_doctor': str(doc.staff_profile.id),
        })
        assert response_valid.status_code == 302
        referral.refresh_from_db()
        assert referral.status == ReferralStatusChoices.CONVERTED
        patient = referral.converted_patient
        assert patient is not None
        assert patient.first_name == 'Bernard'
        assert patient.last_name == 'Kibet'

        episode = patient.episodes.filter(status='ACTIVE').first()
        assert episode is not None
        team = episode.team_members.all()
        assert team.filter(role=CareTeamRoleChoices.PRIMARY_NURSE, staff_member=nurse.staff_profile).exists()
        assert team.filter(role=CareTeamRoleChoices.PRIMARY_DOCTOR, staff_member=doc.staff_profile).exists()
