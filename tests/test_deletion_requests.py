import pytest
from django.test import Client
from django.urls import reverse

from apps.accounts.models import RoleChoices, StaffProfile, User
from apps.audit.models import AuditAction, AuditEvent
from apps.operations.models import DeletionRequestStatusChoices, PatientDeletionRequest
from apps.patients.models import Patient


@pytest.fixture
def receptionist_user(db):
    user = User.objects.create_user(
        username='margaret.ngesa',
        email='receptionist.test@nairobihospice.or.ke',
        password='password123',
        first_name='Margaret',
        last_name='Ngesa',
    )
    StaffProfile.objects.create(user=user, role=RoleChoices.RECEPTIONIST)
    return user


@pytest.fixture
def manager_user(db):
    user = User.objects.create_user(
        username='david.kimani',
        email='manager.test@nairobihospice.or.ke',
        password='password123',
        first_name='David',
        last_name='Kimani',
    )
    StaffProfile.objects.create(user=user, role=RoleChoices.MANAGER)
    return user


@pytest.fixture
def test_patient(db):
    return Patient.objects.create(
        first_name='DeleteTest',
        last_name='Patient',
        hospice_number='NH-2026-9999',
        date_of_birth='1980-01-01',
        sex='FEMALE',
        primary_diagnosis='Test Diagnosis',
    )


@pytest.mark.django_db
def test_receptionist_can_submit_deletion_request(receptionist_user, test_patient):
    client = Client()
    client.force_login(receptionist_user)

    url = reverse('patients:patient_request_delete', kwargs={'pk': test_patient.pk})
    response = client.post(url, {
        'reason': 'Duplicate patient file created in error'
    }, follow=True)

    assert response.status_code == 200
    
    # Check deletion request created
    req = PatientDeletionRequest.objects.get(patient_id_copy=test_patient.pk)
    assert req.status == DeletionRequestStatusChoices.PENDING
    assert req.requested_by == receptionist_user
    assert 'Duplicate patient file' in req.reason
    assert req.patient == test_patient

    # Patient is NOT yet deleted
    assert Patient.objects.filter(pk=test_patient.pk).exists()


@pytest.mark.django_db
def test_manager_can_approve_deletion_and_purges_patient(manager_user, receptionist_user, test_patient):
    # Submit request first
    deletion_req = PatientDeletionRequest.objects.create(
        patient=test_patient,
        patient_id_copy=test_patient.pk,
        patient_name=test_patient.full_name,
        hospice_number=test_patient.hospice_number,
        requested_by=receptionist_user,
        reason='Accidental duplicate dossier entry',
        status=DeletionRequestStatusChoices.PENDING
    )

    client = Client()
    client.force_login(manager_user)

    approve_url = reverse('operations:deletion_request_approve', kwargs={'pk': deletion_req.pk})
    response = client.post(approve_url, {
        'review_notes': 'Verified duplicate with NH-2021-0081. Approved for purge.'
    }, follow=True)

    assert response.status_code == 200

    # Request is approved
    deletion_req.refresh_from_db()
    assert deletion_req.status == DeletionRequestStatusChoices.APPROVED
    assert deletion_req.reviewed_by == manager_user
    assert 'Verified duplicate' in deletion_req.review_notes

    # Patient is permanently purged from DB
    assert not Patient.objects.filter(pk=test_patient.pk).exists()

    # Audit log created
    audit = AuditEvent.objects.filter(action=AuditAction.DELETE, resource_type='Patient').first()
    assert audit is not None
    assert 'Approved deletion' in audit.summary
    assert str(test_patient.pk) in audit.resource_id


@pytest.mark.django_db
def test_manager_can_reject_deletion_and_preserves_patient(manager_user, receptionist_user, test_patient):
    deletion_req = PatientDeletionRequest.objects.create(
        patient=test_patient,
        patient_id_copy=test_patient.pk,
        patient_name=test_patient.full_name,
        hospice_number=test_patient.hospice_number,
        requested_by=receptionist_user,
        reason='Delete requested by patient relative',
        status=DeletionRequestStatusChoices.PENDING
    )

    client = Client()
    client.force_login(manager_user)

    reject_url = reverse('operations:deletion_request_reject', kwargs={'pk': deletion_req.pk})
    response = client.post(reject_url, {
        'review_notes': 'Medical record must be retained for clinical governance.'
    }, follow=True)

    assert response.status_code == 200

    # Request is rejected
    deletion_req.refresh_from_db()
    assert deletion_req.status == DeletionRequestStatusChoices.REJECTED
    assert deletion_req.reviewed_by == manager_user
    assert 'clinical governance' in deletion_req.review_notes

    # Patient remains safely intact in DB
    assert Patient.objects.filter(pk=test_patient.pk).exists()


@pytest.mark.django_db
def test_clinician_can_submit_appointment_deletion_request(receptionist_user, test_patient):
    from apps.appointments.models import Appointment, AppointmentStatusChoices, AppointmentTypeChoices
    staff_profile = receptionist_user.staff_profile
    appt = Appointment.objects.create(
        patient=test_patient,
        staff_member=staff_profile,
        appointment_type=AppointmentTypeChoices.CLINIC_VISIT,
        scheduled_date='2026-08-24',
        scheduled_time='10:00:00',
        status=AppointmentStatusChoices.COMPLETED,
        location='Clinic Room 1',
    )

    client = Client()
    client.force_login(receptionist_user)

    url = reverse('appointments:appointment_request_delete', kwargs={'pk': appt.pk})
    response = client.post(url, {
        'reason': 'Completed visit already documented in clinical encounters ledger'
    }, follow=True)

    assert response.status_code == 200

    from apps.operations.models import AppointmentDeletionRequest
    req = AppointmentDeletionRequest.objects.get(appointment_id_copy=appt.pk)
    assert req.status == DeletionRequestStatusChoices.PENDING
    assert req.requested_by == receptionist_user
    assert req.appointment == appt
    assert Appointment.objects.filter(pk=appt.pk).exists()


@pytest.mark.django_db
def test_manager_can_approve_appointment_deletion_and_purges_appointment(manager_user, receptionist_user, test_patient):
    from apps.appointments.models import Appointment, AppointmentStatusChoices, AppointmentTypeChoices
    from apps.operations.models import AppointmentDeletionRequest
    
    staff_profile = receptionist_user.staff_profile
    appt = Appointment.objects.create(
        patient=test_patient,
        staff_member=staff_profile,
        appointment_type=AppointmentTypeChoices.CLINIC_VISIT,
        scheduled_date='2026-08-24',
        status=AppointmentStatusChoices.COMPLETED,
        location='Clinic Room 1',
    )

    deletion_req = AppointmentDeletionRequest.objects.create(
        appointment=appt,
        appointment_id_copy=appt.pk,
        patient_name=test_patient.full_name,
        hospice_number=test_patient.hospice_number,
        scheduled_date=appt.scheduled_date,
        appointment_type='Clinic Consultation',
        appointment_status='Completed',
        requested_by=receptionist_user,
        reason='Task completed and archived',
        status=DeletionRequestStatusChoices.PENDING
    )

    client = Client()
    client.force_login(manager_user)

    approve_url = reverse('operations:appointment_deletion_approve', kwargs={'pk': deletion_req.pk})
    response = client.post(approve_url, {
        'review_notes': 'Authorized by Operations Manager.'
    }, follow=True)

    assert response.status_code == 200

    deletion_req.refresh_from_db()
    assert deletion_req.status == DeletionRequestStatusChoices.APPROVED
    assert deletion_req.reviewed_by == manager_user
    assert not Appointment.objects.filter(pk=appt.pk).exists()


@pytest.mark.django_db
def test_manager_can_reject_appointment_deletion_and_preserves_appointment(manager_user, receptionist_user, test_patient):
    from apps.appointments.models import Appointment, AppointmentStatusChoices, AppointmentTypeChoices
    from apps.operations.models import AppointmentDeletionRequest
    
    staff_profile = receptionist_user.staff_profile
    appt = Appointment.objects.create(
        patient=test_patient,
        staff_member=staff_profile,
        appointment_type=AppointmentTypeChoices.CLINIC_VISIT,
        scheduled_date='2026-08-24',
        status=AppointmentStatusChoices.COMPLETED,
        location='Clinic Room 1',
    )

    deletion_req = AppointmentDeletionRequest.objects.create(
        appointment=appt,
        appointment_id_copy=appt.pk,
        patient_name=test_patient.full_name,
        hospice_number=test_patient.hospice_number,
        scheduled_date=appt.scheduled_date,
        appointment_type='Clinic Consultation',
        appointment_status='Completed',
        requested_by=receptionist_user,
        reason='Task completed and archived',
        status=DeletionRequestStatusChoices.PENDING
    )

    client = Client()
    client.force_login(manager_user)

    reject_url = reverse('operations:appointment_deletion_reject', kwargs={'pk': deletion_req.pk})
    response = client.post(reject_url, {
        'review_notes': 'Keep for quarterly MDT audit trail.'
    }, follow=True)

    assert response.status_code == 200

    deletion_req.refresh_from_db()
    assert deletion_req.status == DeletionRequestStatusChoices.REJECTED
    assert deletion_req.reviewed_by == manager_user
    assert Appointment.objects.filter(pk=appt.pk).exists()
