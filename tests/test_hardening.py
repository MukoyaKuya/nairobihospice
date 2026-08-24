from datetime import date, time

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, override_settings
from rest_framework.test import APIClient

from apps.accounts.mfa import generate_totp
from apps.accounts.models import RoleChoices
from apps.accounts.services import create_staff_user
from apps.appointments.models import AppointmentTypeChoices
from apps.appointments.services import schedule_appointment
from apps.audit.models import AuditAction, AuditEvent
from apps.documents.forms import PatientDocumentForm
from apps.encounters.models import EncounterTypeChoices
from apps.encounters.services import record_encounter
from apps.operations.forms import InvoiceForm
from apps.operations.models import MovementTypeChoices, StockItem
from apps.operations.services import record_stock_movement
from apps.patients.models import Patient
from apps.patients.services import register_patient
from apps.referrals.services import create_referral


@override_settings(CONTENT_SECURITY_POLICY="default-src 'self';", TRUST_PROXY_HEADERS=False)
def test_security_headers_and_proxy_ip_defaults_are_safe():
    response = Client().get('/health/live/', HTTP_X_FORWARDED_FOR='203.0.113.10')
    assert response['Content-Security-Policy'] == "default-src 'self';"

    from apps.audit.services import get_client_ip

    request = response.wsgi_request
    assert get_client_ip(request) == request.META.get('REMOTE_ADDR')


@override_settings(TRUST_PROXY_HEADERS=True)
def test_proxy_ip_uses_rightmost_untrusted_hop_when_enabled():
    # Leftmost XFF values are client-controlled; only the rightmost entry was
    # appended by our own reverse proxy and is safe to attribute.
    response = Client().get('/health/live/', HTTP_X_FORWARDED_FOR='203.0.113.10, 10.0.0.1')

    from apps.audit.services import get_client_ip

    assert get_client_ip(response.wsgi_request) == '10.0.0.1'


@pytest.mark.django_db
def test_receptionist_cannot_write_patient_api():
    receptionist = create_staff_user(
        email='hardening_rec@nairobihospice.or.ke',
        username='hardening_rec',
        first_name='Hardening',
        last_name='Receptionist',
        password='Pass!',
        role=RoleChoices.RECEPTIONIST,
    )
    client = APIClient()
    client.force_authenticate(user=receptionist)

    response = client.post('/api/v1/patients/', {'first_name': 'Blocked', 'last_name': 'Write'})

    assert response.status_code == 403


@pytest.mark.django_db
def test_stock_movement_rejects_overdraw_and_preserves_balance():
    item = StockItem.objects.create(
        item_code='HARD-STK-01',
        name='Hardening Test Stock',
        unit_of_measure='units',
        quantity_on_hand=2,
    )

    with pytest.raises(ValidationError, match='Insufficient stock'):
        record_stock_movement(
            stock_item=item,
            movement_type=MovementTypeChoices.DISPENSE,
            quantity=3,
        )

    item.refresh_from_db()
    assert item.quantity_on_hand == 2


def test_document_form_rejects_unsupported_file_type():
    form = PatientDocumentForm(
        data={'category': 'OTHER', 'title': 'Unexpected file', 'description': ''},
        files={'file': SimpleUploadedFile('payload.exe', b'not a document', content_type='application/octet-stream')},
    )

    assert not form.is_valid()
    assert 'file' in form.errors


def test_document_form_rejects_legacy_doc_file():
    from django.core.files.uploadedfile import SimpleUploadedFile

    from apps.documents.forms import PatientDocumentForm

    form = PatientDocumentForm(data={'category': 'OTHER', 'title': 'Legacy document'}, files={
        'file': SimpleUploadedFile('legacy.doc', b'old binary document', content_type='application/msword'),
    })
    assert not form.is_valid()
    assert 'file' in form.errors


@override_settings(PCMS_REQUIRE_MALWARE_SCAN=True, PCMS_MALWARE_SCANNER_COMMAND='')
def test_document_form_fails_closed_when_malware_scanner_is_required():
    form = PatientDocumentForm(data={'category': 'OTHER', 'title': 'Unscanned document'}, files={
        'file': SimpleUploadedFile('note.pdf', b'%PDF-1.7', content_type='application/pdf'),
    })
    assert not form.is_valid()
    assert 'file' in form.errors


@pytest.mark.django_db
def test_receptionist_cannot_download_clinical_document():
    doctor = create_staff_user(
        email='hardening_doc@nairobihospice.or.ke',
        username='hardening_doc',
        first_name='Hardening',
        last_name='Doctor',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    receptionist = create_staff_user(
        email='hardening_doc_rec@nairobihospice.or.ke',
        username='hardening_doc_rec',
        first_name='Hardening',
        last_name='Front Desk',
        password='Pass!',
        role=RoleChoices.RECEPTIONIST,
    )
    patient = register_patient(first_name='File', last_name='Patient', created_by=doctor)

    from apps.documents.models import PatientDocument

    document = PatientDocument.objects.create(
        patient=patient,
        title='Clinical note',
        category='OTHER',
        file=SimpleUploadedFile('clinical-note.pdf', b'%PDF-test', content_type='application/pdf'),
        uploaded_by=doctor,
    )
    assert 'private_media' in document.file.path

    client = Client()
    client.force_login(receptionist)
    response = client.get(f'/documents/{document.pk}/download/')

    assert response.status_code == 403


@pytest.mark.django_db
def test_clinician_cannot_download_another_patient_document():
    owner = create_staff_user(
        email='document_owner@nairobihospice.or.ke',
        username='document_owner',
        first_name='Document',
        last_name='Owner',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    other_doctor = create_staff_user(
        email='document_other@nairobihospice.or.ke',
        username='document_other',
        first_name='Document',
        last_name='Other',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    patient = register_patient(first_name='Private', last_name='Document', created_by=owner)

    from apps.documents.models import PatientDocument

    document = PatientDocument.objects.create(
        patient=patient,
        title='Private clinical note',
        category='OTHER',
        file=SimpleUploadedFile('private-note.pdf', b'%PDF-test', content_type='application/pdf'),
        uploaded_by=owner,
    )

    client = Client()
    client.force_login(other_doctor)
    response = client.get(f'/documents/{document.pk}/download/')

    assert response.status_code == 404


@pytest.mark.django_db
def test_api_cannot_reassign_clinical_record_to_another_patient():
    doctor = create_staff_user(
        email='api_reassign@nairobihospice.or.ke',
        username='api_reassign',
        first_name='API',
        last_name='Reassign',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    patient_a = register_patient(first_name='Patient', last_name='A', created_by=doctor)
    patient_b = register_patient(first_name='Patient', last_name='B', created_by=doctor)
    encounter = record_encounter(
        patient=patient_a,
        encounter_type=EncounterTypeChoices.CLINIC_VISIT,
        reason='API authorization test',
        clinical_notes='Private note',
        user=doctor,
    )

    client = APIClient()
    client.force_authenticate(user=doctor)
    response = client.patch(
        f'/api/v1/encounters/{encounter.pk}/',
        {'patient': str(patient_b.pk)},
        format='json',
    )

    assert response.status_code == 400
    encounter.refresh_from_db()
    assert encounter.patient_id == patient_a.pk


@pytest.mark.django_db
def test_receptionist_receives_patient_summary_without_clinical_fields():
    doctor = create_staff_user(
        email='summary_doc@nairobihospice.or.ke',
        username='summary_doc',
        first_name='Summary',
        last_name='Doctor',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    receptionist = create_staff_user(
        email='summary_rec@nairobihospice.or.ke',
        username='summary_rec',
        first_name='Summary',
        last_name='Receptionist',
        password='Pass!',
        role=RoleChoices.RECEPTIONIST,
    )
    patient = register_patient(
        first_name='Summary',
        last_name='Patient',
        primary_diagnosis='Confidential diagnosis',
        allergies='Confidential allergy',
        created_by=doctor,
    )

    api_client = APIClient()
    api_client.force_authenticate(user=receptionist)
    api_response = api_client.get(f'/api/v1/patients/{patient.pk}/')
    assert api_response.status_code == 200
    assert 'primary_diagnosis' not in api_response.json()
    assert 'allergies' not in api_response.json()

    web_client = Client()
    web_client.force_login(receptionist)
    web_response = web_client.get(f'/patients/{patient.pk}/')
    assert web_response.status_code == 200


@pytest.mark.django_db
def test_clinical_record_access_is_scoped_to_responsible_staff():
    owner = create_staff_user(
        email='scope_owner@nairobihospice.or.ke',
        username='scope_owner',
        first_name='Scope',
        last_name='Owner',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    other_doctor = create_staff_user(
        email='scope_other@nairobihospice.or.ke',
        username='scope_other',
        first_name='Scope',
        last_name='Other',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    patient = register_patient(first_name='Scoped', last_name='Patient', created_by=owner)

    client = Client()
    client.force_login(other_doctor)
    assert client.get(f'/patients/{patient.pk}/photo/').status_code == 404

    api_client = APIClient()
    api_client.force_authenticate(user=other_doctor)
    response = api_client.get('/api/v1/patients/', {'search': patient.hospice_number})
    assert response.status_code == 200
    assert response.json()['count'] == 0

    assert Patient.objects.filter(pk=patient.pk).exists()


@pytest.mark.django_db
def test_appointment_api_and_status_update_are_scoped_to_patient_access():
    owner = create_staff_user(
        email='appointment_owner@nairobihospice.or.ke',
        username='appointment_owner',
        first_name='Appointment',
        last_name='Owner',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    other_doctor = create_staff_user(
        email='appointment_other@nairobihospice.or.ke',
        username='appointment_other',
        first_name='Appointment',
        last_name='Other',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    receptionist = create_staff_user(
        email='appointment_reception@nairobihospice.or.ke',
        username='appointment_reception',
        first_name='Appointment',
        last_name='Reception',
        password='Pass!',
        role=RoleChoices.RECEPTIONIST,
    )
    patient = register_patient(first_name='Appointment', last_name='Patient', created_by=owner)
    appointment = schedule_appointment(
        patient=patient,
        staff_member=owner.staff_profile,
        appointment_type=AppointmentTypeChoices.CLINIC_VISIT,
        scheduled_date=date.today(),
        scheduled_time=time(9, 0),
        reason='Scoped test appointment',
        user=owner,
    )

    api_client = APIClient()
    api_client.force_authenticate(user=other_doctor)
    response = api_client.get('/api/v1/appointments/')
    assert response.status_code == 200
    assert response.json()['count'] == 0

    web_client = Client()
    web_client.force_login(other_doctor)
    assert web_client.post(f'/appointments/{appointment.pk}/update-status/', {'status': 'COMPLETED'}).status_code == 404

    api_client.force_authenticate(user=receptionist)
    response = api_client.get('/api/v1/appointments/')
    assert response.status_code == 200
    assert 'reason' not in response.json()['results'][0]

    web_client.force_login(receptionist)
    calendar = web_client.get('/appointments/')
    assert calendar.status_code == 200
    assert b'Scoped test appointment' not in calendar.content


@pytest.mark.django_db
def test_clinical_user_can_load_appointment_calendar_with_scoped_recent_patients():
    doctor = create_staff_user(
        email='calendar_doctor@nairobihospice.or.ke',
        username='calendar_doctor',
        first_name='Calendar',
        last_name='Doctor',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    register_patient(first_name='Calendar', last_name='Patient', created_by=doctor)

    client = Client()
    client.force_login(doctor)
    response = client.get('/appointments/')

    assert response.status_code == 200


@pytest.mark.django_db
def test_referral_clinical_data_and_mutations_are_scoped():
    owner = create_staff_user(
        email='referral_owner@nairobihospice.or.ke',
        username='referral_owner',
        first_name='Referral',
        last_name='Owner',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    other_doctor = create_staff_user(
        email='referral_other@nairobihospice.or.ke',
        username='referral_other',
        first_name='Referral',
        last_name='Other',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    receptionist = create_staff_user(
        email='referral_rec@nairobihospice.or.ke',
        username='referral_rec',
        first_name='Referral',
        last_name='Reception',
        password='Pass!',
        role=RoleChoices.RECEPTIONIST,
    )
    referral = create_referral(
        patient_name='Referral Patient',
        referring_facility='Test Hospital',
        primary_diagnosis='Confidential diagnosis',
        reason_for_referral='Confidential clinical reason',
        current_medications='Confidential medication',
        created_by=owner,
    )

    client = Client()
    client.force_login(other_doctor)
    assert client.get(f'/referrals/{referral.pk}/').status_code == 404

    client.force_login(receptionist)
    response = client.get(f'/referrals/{referral.pk}/')
    assert response.status_code == 200
    assert b'Confidential diagnosis' not in response.content
    assert b'Confidential medication' not in response.content
    assert client.post(f'/referrals/{referral.pk}/review/', {'status': 'UNDER_REVIEW'}).status_code == 403


@pytest.mark.django_db
def test_patient_photo_is_private_and_authorized():
    owner = create_staff_user(
        email='photo_owner@nairobihospice.or.ke',
        username='photo_owner',
        first_name='Photo',
        last_name='Owner',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    other_doctor = create_staff_user(
        email='photo_other@nairobihospice.or.ke',
        username='photo_other',
        first_name='Photo',
        last_name='Other',
        password='Pass!',
        role=RoleChoices.DOCTOR,
    )
    receptionist = create_staff_user(
        email='photo_rec@nairobihospice.or.ke',
        username='photo_rec',
        first_name='Photo',
        last_name='Reception',
        password='Pass!',
        role=RoleChoices.RECEPTIONIST,
    )
    patient = register_patient(first_name='Photo', last_name='Patient', created_by=owner)
    patient.photo = SimpleUploadedFile('patient.jpg', b'private-photo', content_type='image/jpeg')
    patient.save(update_fields=['photo', 'updated_at'])
    assert 'private_media' in patient.photo.path

    client = Client()
    client.force_login(owner)
    assert client.get(f'/patients/{patient.pk}/photo/').status_code == 200
    client.force_login(other_doctor)
    assert client.get(f'/patients/{patient.pk}/photo/').status_code == 404
    client.force_login(receptionist)
    assert client.get(f'/patients/{patient.pk}/photo/').status_code == 200


@pytest.mark.django_db
def test_invoice_form_rejects_overpayment():
    form = InvoiceForm(data={
        'invoice_number': '',
        'invoice_type': 'PATIENT_SERVICE',
        'issue_date': date.today().isoformat(),
        'status': 'ISSUED',
        'subtotal_amount_kes': '100.00',
        'tax_amount_kes': '0.00',
        'discount_amount_kes': '0.00',
        'total_amount_kes': '100.00',
        'amount_paid_kes': '101.00',
        'payment_method': 'Cash',
        'payment_reference': '',
        'notes': '',
    })
    assert not form.is_valid()
    assert 'amount_paid_kes' in form.errors


@pytest.mark.django_db
def test_health_endpoints_are_available():
    client = Client()
    live = client.get('/health/live/')
    ready = client.get('/health/ready/')
    assert live.status_code == 200
    assert live.json() == {'status': 'ok'}
    assert ready.status_code == 200
    payload = ready.json()
    assert payload['status'] == 'ready'
    # Readiness must cover every hard production dependency.
    assert payload['components']['database'] == 'ok'
    assert payload['components']['cache'] == 'ok'
    assert payload['components']['broker'] == 'ok'


@pytest.mark.django_db
def test_privileged_login_requires_mfa_enrollment_and_supports_recovery_code():
    manager = create_staff_user(
        email='mfa_manager@nairobihospice.or.ke',
        username='mfa_manager',
        first_name='MFA',
        last_name='Manager',
        password='Pass!',
        role=RoleChoices.MANAGER,
    )
    client = Client()
    response = client.post('/accounts/login/', {'username': manager.email, 'password': 'Pass!'})
    assert response.status_code == 302
    assert response['Location'].endswith('/accounts/mfa/enroll/')

    enroll = client.get('/accounts/mfa/enroll/')
    assert enroll.status_code == 200
    secret = client.session['mfa_enrollment_secret']
    recovery_code = client.session['mfa_recovery_codes_plain'][0]
    response = client.post('/accounts/mfa/enroll/', {'token': generate_totp(secret)})
    assert response.status_code == 302
    manager.refresh_from_db()
    assert manager.is_mfa_enabled is True
    assert len(manager.mfa_recovery_codes) == 10

    client.post('/accounts/logout/')
    response = client.post('/accounts/login/', {'username': manager.email, 'password': 'Pass!'})
    assert response['Location'].endswith('/accounts/mfa/verify/')
    response = client.post('/accounts/mfa/verify/', {'recovery_code': recovery_code})
    assert response.status_code == 302

    client.post('/accounts/logout/')
    client.post('/accounts/login/', {'username': manager.email, 'password': 'Pass!'})
    failed_reuse = client.post('/accounts/mfa/verify/', {'recovery_code': recovery_code})
    assert failed_reuse.status_code == 400


@pytest.mark.django_db
def test_failed_login_rate_limit_and_password_reset_audit_path():
    user = create_staff_user(
        email='recovery_user@nairobihospice.or.ke',
        username='recovery_user',
        first_name='Recovery',
        last_name='User',
        password='Pass!',
        role=RoleChoices.NURSE,
    )
    client = Client()
    for _ in range(5):
        assert client.post('/accounts/login/', {'username': user.email, 'password': 'Wrong!' }).status_code == 200
    assert client.post('/accounts/login/', {'username': user.email, 'password': 'Wrong!' }).status_code == 429
    assert AuditEvent.objects.filter(action=AuditAction.LOGIN, resource_type='Authentication').count() >= 5

    response = client.post('/accounts/password-reset/', {'email': user.email})
    assert response.status_code == 302
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_audit_events_are_immutable_at_application_layer():
    event = AuditEvent.objects.create(
        action=AuditAction.VIEW,
        resource_type='SecurityTest',
        summary='Immutable audit test',
    )
    with pytest.raises(RuntimeError, match='immutable'):
        event.save()
    with pytest.raises(RuntimeError, match='immutable'):
        event.delete()
