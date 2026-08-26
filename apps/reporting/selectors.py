from datetime import date, timedelta

from django.db.models import Count
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.care.models import CarePlan, CarePlanStatusChoices
from apps.encounters.models import Encounter, EncounterTypeChoices
from apps.patients.models import Patient, PatientStatusChoices
from apps.referrals.models import Referral, ReferralStatusChoices
from apps.symptoms.models import SymptomAssessmentRecord


from apps.patients.access import (
    authorized_patient_queryset,
    can_conduct_clinical_encounters,
    can_manage_all_patients,
    is_operations_manager,
)


def get_clinical_dashboard_data(user):
    today = date.today()

    # Role identification
    is_rec = getattr(user, 'is_receptionist', False)
    is_nurse = getattr(user, 'is_nurse', False)
    is_doc = getattr(user, 'is_doctor', False) or getattr(user, 'is_clinical_officer', False)
    is_pharm = getattr(user, 'is_pharmacist', False)
    is_psy = getattr(user, 'is_social_worker', False) or getattr(user, 'is_counsellor', False)

    is_admin_or_mgr = can_manage_all_patients(user)
    auth_patients = authorized_patient_queryset(user)

    # Base common datasets
    today_appts = Appointment.objects.filter(
        scheduled_date=today
    ).select_related('patient', 'staff_member__user').order_by('scheduled_time')
    if not is_admin_or_mgr and not is_rec:
        from django.db.models import Q
        today_appts = today_appts.filter(Q(patient__in=auth_patients) | Q(staff_member__user=user))

    from apps.assessments.models import Assessment

    # Clinical Queries (skipped for Receptionist and Pharmacist)
    if is_rec or is_pharm:
        due_reviews = CarePlan.objects.none()
        pain_spikes_qs = Assessment.objects.none()
        pain_spikes_count = 0
        recent_high_distress = SymptomAssessmentRecord.objects.none()
        recent_encounters = Encounter.objects.none()
    else:
        due_reviews = CarePlan.objects.filter(
            status=CarePlanStatusChoices.ACTIVE,
            review_date__lte=today + timedelta(days=7)
        ).select_related('patient', 'created_by').order_by('review_date')
        if not is_admin_or_mgr:
            due_reviews = due_reviews.filter(patient__in=auth_patients)
        due_reviews = due_reviews[:10]

        pain_spikes_qs = Assessment.objects.filter(
            pain_score__gte=7
        ).select_related('patient', 'assessor').order_by('-assessment_date')
        if not is_admin_or_mgr:
            pain_spikes_qs = pain_spikes_qs.filter(patient__in=auth_patients)
        pain_spikes_count = pain_spikes_qs.count()

        recent_high_distress = SymptomAssessmentRecord.objects.filter(
            total_distress_score__gte=30
        ).select_related('patient', 'recorded_by').order_by('-total_distress_score')
        if not is_admin_or_mgr:
            recent_high_distress = recent_high_distress.filter(patient__in=auth_patients)
        recent_high_distress = recent_high_distress[:8]

        recent_encounters = Encounter.objects.select_related('patient', 'recorded_by').order_by('-encounter_date', '-created_at')
        if not is_admin_or_mgr:
            recent_encounters = recent_encounters.filter(patient__in=auth_patients)
        recent_encounters = recent_encounters[:8]

    from apps.referrals.access import referral_queryset_for_user
    pending_referrals = referral_queryset_for_user(user).filter(
        status__in=[ReferralStatusChoices.RECEIVED, ReferralStatusChoices.UNDER_REVIEW]
    ).order_by('priority', '-referral_date')[:6]

    # Specific datasets
    from apps.communications.models import CommunicationRecord
    from apps.medications.models import MedicationStatement, MedicationStatusChoices

    active_medications_qs = MedicationStatement.objects.filter(
        status=MedicationStatusChoices.ACTIVE
    ).select_related('patient', 'prescriber').order_by('-start_date')
    if not is_admin_or_mgr:
        active_medications_qs = active_medications_qs.filter(patient__in=auth_patients)

    # Controlled substance / opioid statements
    morphine_medications = active_medications_qs.filter(
        medication_name__icontains='morphine'
    )[:8]
    active_medications = active_medications_qs[:10]

    # Recent communication records
    recent_communications = CommunicationRecord.objects.select_related('patient', 'recorded_by').order_by('-created_at')
    if not is_admin_or_mgr:
        recent_communications = recent_communications.filter(patient__in=auth_patients)
    recent_communications = recent_communications[:8]

    # Appointments breakdown
    home_care_visits_today = today_appts.filter(appointment_type='HOME_VISIT')
    clinic_visits_today = today_appts.filter(appointment_type='CLINIC_VISIT')

    # Monthly additions
    month_start = today.replace(day=1)
    if is_admin_or_mgr or is_rec:
        new_registrations_month = Patient.objects.filter(registration_date__gte=month_start).count()
        active_cohort_count = Patient.objects.filter(status=PatientStatusChoices.ACTIVE).count()
    else:
        new_registrations_month = auth_patients.filter(registration_date__gte=month_start).count()
        active_cohort_count = auth_patients.filter(status=PatientStatusChoices.ACTIVE).count()

    # Bereavement cases (patients deceased in last 6 months for psychosocial follow-up)
    if is_admin_or_mgr or is_psy:
        bereavement_cases = Patient.objects.filter(
            status=PatientStatusChoices.DECEASED,
            date_of_death__gte=today - timedelta(days=180)
        ).order_by('-date_of_death')
        if not is_admin_or_mgr:
            bereavement_cases = bereavement_cases.filter(pk__in=auth_patients.values('pk'))
        bereavement_cases = bereavement_cases[:6]
    else:
        bereavement_cases = Patient.objects.none()

    # Pharmacy Metrics
    from apps.operations.models import MovementTypeChoices, StockMovement
    if is_admin_or_mgr:
        total_dispenses_count = StockMovement.objects.filter(movement_type=MovementTypeChoices.DISPENSE).count()
    elif is_pharm:
        total_dispenses_count = StockMovement.objects.filter(movement_type=MovementTypeChoices.DISPENSE, recorded_by=user).count()
    else:
        total_dispenses_count = 0

    return {
        'today': today,
        'today_appts': today_appts,
        'today_appts_count': today_appts.count(),
        'home_care_visits_today': home_care_visits_today,
        'clinic_visits_today': clinic_visits_today,
        'due_reviews': due_reviews,
        'due_reviews_count': due_reviews.count(),
        'pain_spikes_count': pain_spikes_count,
        'pain_spikes': pain_spikes_qs[:8],
        'recent_high_distress': recent_high_distress,
        'pending_referrals': pending_referrals,
        'pending_referrals_count': pending_referrals.count(),
        'recent_encounters': recent_encounters,
        'active_medications': active_medications,
        'morphine_medications': morphine_medications,
        'recent_communications': recent_communications,
        'new_registrations_month': new_registrations_month,
        'active_cohort_count': active_cohort_count,
        'bereavement_cases': bereavement_cases,
        'total_dispenses_count': total_dispenses_count,
        # Role flags for template partial selection
        'is_receptionist': is_rec,
        'is_nurse': is_nurse,
        'is_doctor': is_doc,
        'is_pharmacist': is_pharm,
        'is_social_worker': is_psy,
        'is_manager': is_operations_manager(user),
        'can_conduct_encounters': can_conduct_clinical_encounters(user),
    }


def get_management_dashboard_data():
    today = date.today()
    month_start = today.replace(day=1)

    # Patient counts
    total_active_patients = Patient.objects.filter(status=PatientStatusChoices.ACTIVE).count()
    new_patients_this_month = Patient.objects.filter(registration_date__gte=month_start).count()
    total_deceased = Patient.objects.filter(status=PatientStatusChoices.DECEASED).count()
    total_discharged = Patient.objects.filter(status=PatientStatusChoices.DISCHARGED).count()

    # Referrals breakdown
    total_referrals_month = Referral.objects.filter(referral_date__gte=month_start).count()
    converted_referrals_month = Referral.objects.filter(referral_date__gte=month_start, status=ReferralStatusChoices.CONVERTED).count()
    pending_referrals_total = Referral.objects.filter(status__in=[ReferralStatusChoices.RECEIVED, ReferralStatusChoices.UNDER_REVIEW]).count()

    # Encounters by type this month
    encounter_stats = Encounter.objects.filter(encounter_date__gte=month_start).values('encounter_type').annotate(count=Count('id'))
    encounter_counts = {item['encounter_type']: item['count'] for item in encounter_stats}

    home_visits_count = encounter_counts.get(EncounterTypeChoices.HOME_VISIT, 0)
    clinic_visits_count = encounter_counts.get(EncounterTypeChoices.CLINIC_VISIT, 0)
    phone_consults_count = encounter_counts.get(EncounterTypeChoices.TELEPHONE, 0)
    counselling_count = encounter_counts.get(EncounterTypeChoices.COUNSELLING, 0)
    total_encounters_month = sum(encounter_counts.values())

    # Patients by county
    county_distribution = list(Patient.objects.values('county').annotate(count=Count('id')).order_by('-count')[:6])

    # Top Palliative Diagnoses
    diagnosis_distribution = list(
        Patient.objects.exclude(primary_diagnosis='')
        .values('primary_diagnosis')
        .annotate(count=Count('id'))
        .order_by('-count')[:6]
    )

    return {
        'total_active_patients': total_active_patients,
        'new_patients_this_month': new_patients_this_month,
        'total_deceased': total_deceased,
        'total_discharged': total_discharged,
        'total_referrals_month': total_referrals_month,
        'converted_referrals_month': converted_referrals_month,
        'pending_referrals_total': pending_referrals_total,
        'home_visits_count': home_visits_count,
        'clinic_visits_count': clinic_visits_count,
        'phone_consults_count': phone_consults_count,
        'counselling_count': counselling_count,
        'total_encounters_month': total_encounters_month,
        'county_distribution': county_distribution,
        'diagnosis_distribution': diagnosis_distribution,
    }
