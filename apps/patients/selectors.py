from django.db.models import Q, QuerySet

from .models import Patient, PatientStatusChoices


def get_patient_by_id(patient_id) -> Patient:
    return Patient.objects.prefetch_related('next_of_kin', 'caregivers').get(id=patient_id)


def get_patient_by_hospice_number(hospice_number: str) -> Patient:
    return Patient.objects.prefetch_related('next_of_kin', 'caregivers').get(hospice_number=hospice_number)


def get_active_patients() -> QuerySet[Patient]:
    return Patient.objects.filter(status=PatientStatusChoices.ACTIVE).order_by('-registration_date')


def search_patients(
    query: str = '',
    status: str = '',
    county: str = '',
    sex: str = '',
    date_from=None,
    date_to=None,
    year: str = '',
    age_group: str = '',
) -> QuerySet[Patient]:
    qs = Patient.objects.all().order_by('-registration_date', '-created_at')

    if query:
        q = query.strip()
        qs = qs.filter(
            Q(hospice_number__icontains=q) |
            Q(first_name__icontains=q) |
            Q(middle_name__icontains=q) |
            Q(last_name__icontains=q) |
            Q(phone_number__icontains=q) |
            Q(identification_number__icontains=q) |
            Q(primary_diagnosis__icontains=q)
        )

    if status:
        qs = qs.filter(status=status)
    if county:
        qs = qs.filter(county__icontains=county)
    if sex:
        qs = qs.filter(sex=sex)
    if date_from:
        qs = qs.filter(registration_date__gte=date_from)
    if date_to:
        qs = qs.filter(registration_date__lte=date_to)
    if year:
        try:
            yr = int(year)
            qs = qs.filter(registration_date__year=yr)
        except (ValueError, TypeError):
            pass

    if age_group:
        from datetime import date
        today = date.today()
        if age_group == 'pediatric':  # 0-17
            cutoff = today.replace(year=today.year - 18)
            qs = qs.filter(date_of_birth__gt=cutoff)
        elif age_group == 'youth':  # 18-35
            max_cutoff = today.replace(year=today.year - 18)
            min_cutoff = today.replace(year=today.year - 36)
            qs = qs.filter(date_of_birth__lte=max_cutoff, date_of_birth__gt=min_cutoff)
        elif age_group == 'adult':  # 36-59
            max_cutoff = today.replace(year=today.year - 36)
            min_cutoff = today.replace(year=today.year - 60)
            qs = qs.filter(date_of_birth__lte=max_cutoff, date_of_birth__gt=min_cutoff)
        elif age_group == 'senior':  # 60+
            cutoff = today.replace(year=today.year - 60)
            qs = qs.filter(date_of_birth__lte=cutoff)

    return qs
