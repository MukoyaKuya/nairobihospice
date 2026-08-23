from datetime import date, timedelta

from django.db.models import Count
from django.utils import timezone

from apps.appointments.models import Appointment
from apps.care.models import CarePlan, CarePlanStatusChoices
from apps.encounters.models import Encounter, EncounterTypeChoices
from apps.patients.models import Patient, PatientStatusChoices
from apps.referrals.models import Referral, ReferralStatusChoices
from apps.symptoms.models import SymptomAssessmentRecord


def get_clinical_dashboard_data(user):
    today = date.today()

    # Role identification
    is_rec = getattr(user, 'is_receptionist', False)
    is_nurse = getattr(user, 'is_nurse', False)
    is_doc = getattr(user, 'is_doctor', False) or getattr(user, 'is_clinical_officer', False)
    is_pharm = getattr(user, 'is_pharmacist', False)
    is_psy = getattr(user, 'is_social_worker', False) or getattr(user, 'is_counsellor', False)

    # Base common datasets
    today_appts = Appointment.objects.filter(
        scheduled_date=today
    ).select_related('patient', 'staff_member__user').order_by('scheduled_time')

    due_reviews = CarePlan.objects.filter(
        status=CarePlanStatusChoices.ACTIVE,
        review_date__lte=today + timedelta(days=7)
    ).select_related('patient', 'created_by').order_by('review_date')[:10]

    recent_high_distress = SymptomAssessmentRecord.objects.filter(
        recorded_at__gte=timezone.now() - timedelta(days=7),
        total_distress_score__gte=35
    ).select_related('patient', 'recorded_by').order_by('-total_distress_score')[:8]

    pending_referrals = Referral.objects.filter(
        status__in=[ReferralStatusChoices.RECEIVED, ReferralStatusChoices.UNDER_REVIEW]
    ).order_by('priority', '-referral_date')[:6]

    recent_encounters = Encounter.objects.select_related('patient', 'recorded_by').order_by('-encounter_date', '-created_at')[:8]

    # Specific datasets
    from apps.communications.models import CommunicationRecord
    from apps.medications.models import MedicationStatement, MedicationStatusChoices

    active_medications_qs = MedicationStatement.objects.filter(
        status=MedicationStatusChoices.ACTIVE
    ).select_related('patient', 'prescriber').order_by('-start_date')

    # Controlled substance / opioid statements
    morphine_medications = active_medications_qs.filter(
        medication_name__icontains='morphine'
    )[:8]
    active_medications = active_medications_qs[:10]

    # Recent communication records
    recent_communications = CommunicationRecord.objects.select_related('patient', 'recorded_by').order_by('-created_at')[:8]

    # Appointments breakdown
    home_care_visits_today = today_appts.filter(appointment_type='HOME_VISIT')
    clinic_visits_today = today_appts.filter(appointment_type='CLINIC_VISIT')

    # Monthly additions
    month_start = today.replace(day=1)
    new_registrations_month = Patient.objects.filter(registration_date__gte=month_start).count()
    active_cohort_count = Patient.objects.filter(status=PatientStatusChoices.ACTIVE).count()

    # Bereavement cases (patients deceased in last 6 months for psychosocial follow-up)
    bereavement_cases = Patient.objects.filter(
        status=PatientStatusChoices.DECEASED,
        date_of_death__gte=today - timedelta(days=180)
    ).order_by('-date_of_death')[:6]

    return {
        'today': today,
        'today_appts': today_appts,
        'today_appts_count': today_appts.count(),
        'home_care_visits_today': home_care_visits_today,
        'clinic_visits_today': clinic_visits_today,
        'due_reviews': due_reviews,
        'due_reviews_count': due_reviews.count(),
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
        # Role flags for template partial selection
        'is_receptionist': is_rec,
        'is_nurse': is_nurse,
        'is_doctor': is_doc,
        'is_pharmacist': is_pharm,
        'is_social_worker': is_psy,
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
