"""Regression tests for the P1/P2 audit remediations."""
import json
from datetime import date
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.test import Client
from rest_framework.test import APIClient

from apps.accounts.mfa import generate_secret, generate_totp
from apps.accounts.models import RoleChoices
from apps.accounts.services import create_staff_user
from apps.assessments.models import Assessment
from apps.audit.models import AuditEvent
from apps.care.models import CarePlan, CarePlanStatusChoices, CareTeamRoleChoices
from apps.care.services import create_care_plan
from apps.operations.models import Invoice, InvoiceTypeChoices, PaymentStatusChoices, StockItem, Vendor
from apps.operations.selectors import get_disease_analytics_data, get_operations_dashboard_data
from apps.patients.models import Patient
from apps.patients.services import register_patient
from apps.referrals.services import convert_referral_to_patient, create_referral
from apps.reporting.charting import chart_json


def make_staff(email, role, username=None):
    return create_staff_user(
        email=email,
        username=username or email.split('@')[0],
        first_name='Test',
        last_name=email.split('@')[0].title(),
        password='Pass!',
        role=role,
    )


# ---------------------------------------------------------------------------
# Fix 1 — default-deny patient visibility for role-less users
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_roleless_user_sees_no_patients_on_web_and_api():
    doctor = make_staff('roleless_doctor@nairobihospice.or.ke', RoleChoices.DOCTOR)
    register_patient(first_name='Hidden', last_name='Record', created_by=doctor)

    roleless = get_user_model().objects.create_user(
        username='roleless_user', email='roleless@nairobihospice.or.ke', password='Pass!'
    )

    web_client = Client()
    web_client.force_login(roleless)
    response = web_client.get('/patients/')
    assert response.status_code == 200
    assert response.context['patients'].count() == 0

    api_client = APIClient()
    api_client.force_authenticate(user=roleless)
    api_response = api_client.get('/api/v1/patients/')
    assert api_response.status_code == 200
    assert api_response.json()['count'] == 0

    detail_response = api_client.get(f'/api/v1/patients/{Patient.objects.get().pk}/')
    assert detail_response.status_code == 404


@pytest.mark.django_db
def test_receptionist_still_sees_full_patient_register():
    doctor = make_staff('reg_doctor@nairobihospice.or.ke', RoleChoices.DOCTOR)
    register_patient(first_name='Front', last_name='DeskVisible', created_by=doctor)

    receptionist = make_staff('reg_reception@nairobihospice.or.ke', RoleChoices.RECEPTIONIST)
    web_client = Client()
    web_client.force_login(receptionist)
    response = web_client.get('/patients/')
    assert response.status_code == 200
    assert response.context['patients'].count() == 1


# ---------------------------------------------------------------------------
# Fix 2 + 6a — care plan patient authorization + single-active-plan invariant
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_care_plan_cannot_target_unauthorized_patient():
    owner = make_staff('cp_owner@nairobihospice.or.ke', RoleChoices.DOCTOR)
    intruder = make_staff('cp_intruder@nairobihospice.or.ke', RoleChoices.DOCTOR)
    patient = register_patient(first_name='Guarded', last_name='Chart', created_by=owner)

    client = Client()
    client.force_login(intruder)
    response = client.post('/care/create/', {
        'patient': str(patient.pk),
        'title': 'Unauthorized Plan',
        'overall_goals': 'Should not be created',
        'status': 'ACTIVE',
    })
    assert response.status_code == 200
    assert not CarePlan.objects.filter(patient=patient).exists()


@pytest.mark.django_db
def test_care_plan_via_view_completes_previous_active_plan():
    doctor = make_staff('cp_doctor@nairobihospice.or.ke', RoleChoices.DOCTOR)
    patient = register_patient(first_name='Single', last_name='Active', created_by=doctor)
    create_care_plan(patient=patient, overall_goals='First plan', user=doctor)

    client = Client()
    client.force_login(doctor)
    response = client.post(f'/care/create/{patient.pk}/', {
        'title': 'Second Plan',
        'overall_goals': 'Replacement plan',
        'status': 'ACTIVE',
    })
    assert response.status_code == 302
    assert CarePlan.objects.filter(patient=patient, status=CarePlanStatusChoices.ACTIVE).count() == 1
    assert CarePlan.objects.filter(patient=patient, status=CarePlanStatusChoices.COMPLETED).count() == 1


@pytest.mark.django_db
def test_care_team_assignment_via_view_is_audited():
    doctor = make_staff('ct_doctor@nairobihospice.or.ke', RoleChoices.DOCTOR)
    assignee = make_staff('ct_assignee@nairobihospice.or.ke', RoleChoices.NURSE)
    patient = register_patient(first_name='Team', last_name='Audited', created_by=doctor)

    client = Client()
    client.force_login(doctor)
    response = client.post(f'/care/patient/{patient.pk}/care-team/', {
        'staff_member': str(assignee.staff_profile.pk),
        'role': CareTeamRoleChoices.PRIMARY_NURSE,
        'is_primary': 'on',
        'start_date': date.today().isoformat(),
    })
    assert response.status_code == 302
    assert AuditEvent.objects.filter(resource_type='CareTeam', user=doctor).exists()


# ---------------------------------------------------------------------------
# Fix 3 — MFA verification throttle + TOTP replay protection
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_mfa_verification_locks_out_after_repeated_failures():
    cache.clear()
    manager = make_staff('mfa_manager@nairobihospice.or.ke', RoleChoices.MANAGER)
    manager.mfa_secret = generate_secret()
    manager.is_mfa_enabled = True
    manager.save(update_fields=['mfa_secret', 'is_mfa_enabled'])

    client = Client()
    session = client.session
    session['mfa_pending_user_id'] = str(manager.pk)
    session.save()

    for _ in range(5):
        response = client.post('/accounts/mfa/verify/', {'token': '000000'})
        assert response.status_code == 400

    valid_token = generate_totp(manager.mfa_secret)
    response = client.post('/accounts/mfa/verify/', {'token': valid_token})
    assert response.status_code == 302
    assert '/accounts/login/' in response['Location']
    assert 'mfa_pending_user_id' not in client.session


@pytest.mark.django_db
def test_totp_code_cannot_be_replayed():
    from apps.accounts.mfa import encrypt_mfa_secret
    cache.clear()
    manager = make_staff('mfa_replay@nairobihospice.or.ke', RoleChoices.MANAGER)
    raw_secret = generate_secret()
    manager.mfa_secret = encrypt_mfa_secret(raw_secret)
    manager.is_mfa_enabled = True
    manager.save(update_fields=['mfa_secret', 'is_mfa_enabled'])
    token = generate_totp(raw_secret)

    first_client = Client()
    session = first_client.session
    session['mfa_pending_user_id'] = str(manager.pk)
    session.save()
    first = first_client.post('/accounts/mfa/verify/', {'token': token})
    assert first.status_code == 302
    assert '/accounts/login/' not in first['Location']

    second_client = Client()
    session = second_client.session
    session['mfa_pending_user_id'] = str(manager.pk)
    session.save()
    second = second_client.post('/accounts/mfa/verify/', {'token': token})
    assert second.status_code == 400


# ---------------------------------------------------------------------------
# Fix 4 — no fabricated dashboard data; correct encounter types and age bands
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_operations_dashboard_reports_zero_instead_of_simulated_spend():
    data = get_operations_dashboard_data()
    assert data['spend_amounts_json'] == json.dumps([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    assert json.loads(data['inv_chart_labels_json']) == []
    assert json.loads(data['inv_chart_data_json']) == []


@pytest.mark.django_db
def test_disease_analytics_counts_unknown_age_separately():
    make_staff('da_doctor@nairobihospice.or.ke', RoleChoices.DOCTOR)
    register_patient(first_name='Unknown', last_name='Age')

    data = get_disease_analytics_data()
    buckets = {entry['label']: entry['count'] for entry in data['age_groups_list']}
    assert buckets['Unknown'] == 1
    assert buckets['36 - 50 yrs'] == 0


@pytest.mark.django_db
def test_modality_counts_use_real_encounter_types():
    from django.utils import timezone

    from apps.encounters.models import Encounter

    make_staff('mod_doctor@nairobihospice.or.ke', RoleChoices.DOCTOR)
    patient = register_patient(first_name='Modality', last_name='Counts')
    Encounter.objects.create(
        patient=patient, reason='teleconsult', clinical_notes='n',
        encounter_type='TELEPHONE', encounter_date=timezone.now().date(),
    )

    data = get_operations_dashboard_data()
    assert data['phone_consults_count'] == 1
    assert 'Community / Outreach' in json.loads(data['modality_labels_json'])


# ---------------------------------------------------------------------------
# Fix 5 — chart JSON is script-safe
# ---------------------------------------------------------------------------

def test_chart_json_escapes_script_breakout_sequences():
    payload = ['</script><img src=x onerror=alert(1)>', 'a&b']
    rendered = chart_json(payload)
    assert '<' not in rendered and '>' not in rendered and '&' not in rendered
    assert json.loads(rendered) == payload


@pytest.mark.django_db
def test_patient_detail_chart_payload_is_script_safe():
    doctor = make_staff('xss_doctor@nairobihospice.or.ke', RoleChoices.DOCTOR)
    patient = register_patient(
        first_name='Script', last_name='Safe', primary_diagnosis='</script>', created_by=doctor
    )
    client = Client()
    client.force_login(doctor)
    response = client.get(f'/patients/{patient.pk}/')
    assert response.status_code == 200
    # The JSON produced for inline scripts must escape markup-significant bytes.
    assert chart_json(['</script>']) == '["\\u003c/script\\u003e"]'


# ---------------------------------------------------------------------------
# Fix 6b — referral service: audited create, idempotent conversion
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_referral_create_via_view_uses_service_and_audits():
    receptionist = make_staff('ref_rec@nairobihospice.or.ke', RoleChoices.RECEPTIONIST)
    client = Client()
    client.force_login(receptionist)
    response = client.post('/referrals/create/', {
        'patient_name': 'Referral Via View',
        'referring_facility': 'Kenyatta National Hospital',
        'primary_diagnosis': 'Ca Breast Stage IV',
        'reason_for_referral': 'Pain management',
        'referral_source': 'HOSPITAL',
        'priority': 'ROUTINE',
        'referral_date': date.today().isoformat(),
        'sex': 'F',
        'county': 'Nairobi',
    })
    assert response.status_code == 302
    assert AuditEvent.objects.filter(resource_type='Referral', action='CREATE').exists()


@pytest.mark.django_db
def test_referral_conversion_is_idempotent():
    doctor = make_staff('ref_conv@nairobihospice.or.ke', RoleChoices.DOCTOR)
    nurse = make_staff('ref_conv_nurse@nairobihospice.or.ke', RoleChoices.NURSE)
    referral = create_referral(
        patient_name='Idem Empotent',
        referring_facility='KNH',
        primary_diagnosis='Ca Cervix',
        reason_for_referral='End of life care',
        created_by=doctor,
    )
    referral.status = 'ACCEPTED'
    referral.save()

    first = convert_referral_to_patient(
        referral=referral,
        user=doctor,
        primary_nurse=nurse.staff_profile,
        primary_doctor=doctor.staff_profile,
    )
    second = convert_referral_to_patient(
        referral=referral,
        user=doctor,
        primary_nurse=nurse.staff_profile,
        primary_doctor=doctor.staff_profile,
    )
    assert first.pk == second.pk
    assert Patient.objects.filter(originating_referrals=referral).count() == 1


# ---------------------------------------------------------------------------
# Fix 7 — single medication authorization policy across web and API
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_nurse_can_record_medications_on_web_and_api():
    nurse = make_staff('med_nurse@nairobihospice.or.ke', RoleChoices.NURSE)
    patient = register_patient(first_name='Meds', last_name='ForNurse', created_by=nurse)

    web_client = Client()
    web_client.force_login(nurse)
    assert web_client.get(f'/medications/patient/{patient.pk}/create/').status_code == 200

    api_client = APIClient()
    api_client.force_authenticate(user=nurse)
    response = api_client.post('/api/v1/medications/', {
        'patient': str(patient.pk),
        'medication_name': 'Oral Morphine Solution',
        'dosage': '10 mg',
        'route': 'ORAL',
        'frequency': 'q4h',
        'start_date': date.today().isoformat(),
        'status': 'ACTIVE',
    })
    assert response.status_code == 201


@pytest.mark.django_db
def test_counsellor_cannot_record_medications_on_web_or_api():
    counsellor = make_staff('med_counsellor@nairobihospice.or.ke', RoleChoices.COUNSELLOR)
    doctor = make_staff('med_doc2@nairobihospice.or.ke', RoleChoices.DOCTOR)
    patient = register_patient(first_name='Meds', last_name='Blocked', created_by=doctor)

    web_client = Client()
    web_client.force_login(counsellor)
    assert web_client.get(f'/medications/patient/{patient.pk}/create/').status_code == 403

    api_client = APIClient()
    api_client.force_authenticate(user=counsellor)
    response = api_client.post('/api/v1/medications/', {
        'patient': str(patient.pk),
        'medication_name': 'Oral Morphine Solution',
        'dosage': '10 mg',
        'route': 'ORAL',
        'frequency': 'q4h',
        'start_date': date.today().isoformat(),
        'status': 'ACTIVE',
    })
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# Fix 8 — server-side clinical score validation
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_model_rejects_out_of_range_scores():
    doctor = make_staff('score_doc@nairobihospice.or.ke', RoleChoices.DOCTOR)
    patient = register_patient(first_name='Score', last_name='Bounds', created_by=doctor)

    for field, bad in [('pain_score', 11), ('pps_score', 101), ('ecog_score', 5)]:
        assessment = Assessment(patient=patient, clinical_summary='x', **{field: bad})
        with pytest.raises(ValidationError):
            assessment.full_clean()


@pytest.mark.django_db
def test_assessment_form_rejects_out_of_range_score():
    doctor = make_staff('score_doc2@nairobihospice.or.ke', RoleChoices.DOCTOR)
    patient = register_patient(first_name='Score', last_name='Form', created_by=doctor)

    client = Client()
    client.force_login(doctor)
    response = client.post(f'/assessments/patient/{patient.pk}/create/', {
        'assessment_type': 'PAIN',
        'assessment_date': date.today().isoformat(),
        'pain_score': 99,
        'clinical_summary': 'should fail',
    })
    assert response.status_code == 200
    assert not Assessment.objects.filter(patient=patient).exists()


@pytest.mark.django_db
def test_api_cannot_set_total_distress_score():
    doctor = make_staff('score_doc3@nairobihospice.or.ke', RoleChoices.DOCTOR)
    patient = register_patient(first_name='Score', last_name='Api', created_by=doctor)

    api_client = APIClient()
    api_client.force_authenticate(user=doctor)
    response = api_client.post('/api/v1/symptoms/', {
        'patient': str(patient.pk),
        'total_distress_score': 500,
        'clinical_notes': 'client-supplied total must be ignored',
    })
    assert response.status_code == 201
    assert response.json()['total_distress_score'] == 0


# ---------------------------------------------------------------------------
# Fix 9 — SQL aggregation and queryset-based low-stock filter
# ---------------------------------------------------------------------------

@pytest.mark.django_db
def test_invoice_totals_computed_by_aggregation():
    manager = make_staff('inv_manager@nairobihospice.or.ke', RoleChoices.MANAGER)
    vendor = Vendor.objects.create(name='Agg Vendor', code='VND-AGG-1', contact_person='x', phone_number='0')

    def make_invoice(total, paid):
        return Invoice.objects.create(
            invoice_type=InvoiceTypeChoices.SUPPLIER_PURCHASE,
            vendor=vendor,
            status=PaymentStatusChoices.PARTIALLY_PAID,
            total_amount_kes=Decimal(total),
            amount_paid_kes=Decimal(paid),
        )

    make_invoice('1000.00', '400.00')
    make_invoice('250.50', '250.50')

    client = Client()
    client.force_login(manager)
    response = client.get('/operations/invoices/')
    assert response.status_code == 200
    context = response.context
    assert context['total_invoices_count'] == 2
    assert context['total_billed_kes'] == Decimal('1250.50')
    assert context['total_collected_kes'] == Decimal('650.50')
    assert context['outstanding_balance_kes'] == Decimal('600.00')


@pytest.mark.django_db
def test_low_stock_filter_returns_paginated_queryset():
    manager = make_staff('stock_manager@nairobihospice.or.ke', RoleChoices.MANAGER)
    StockItem.objects.create(item_code='STK-LOW-1', name='Low Item', quantity_on_hand=2, minimum_reorder_level=5)
    StockItem.objects.create(item_code='STK-OK-1', name='Healthy Item', quantity_on_hand=50, minimum_reorder_level=5)

    client = Client()
    client.force_login(manager)
    response = client.get('/operations/inventory/', {'filter': 'low_stock'})
    assert response.status_code == 200
    object_list = response.context['stock_items']
    # Must stay a queryset (SQL filtering, SQL pagination), not a Python list.
    assert hasattr(object_list, 'query')
    assert object_list.count() == 1
    assert object_list.first().item_code == 'STK-LOW-1'
