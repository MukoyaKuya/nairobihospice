from django.db.models import QuerySet

from apps.patients.models import Patient

from .models import Encounter, EncounterTypeChoices


def get_patient_encounters(patient: Patient) -> QuerySet[Encounter]:
    return Encounter.objects.filter(patient=patient).select_related('recorded_by').order_by('-encounter_date', '-created_at')


def get_encounters_by_type(encounter_type: EncounterTypeChoices) -> QuerySet[Encounter]:
    return Encounter.objects.filter(encounter_type=encounter_type).select_related('patient', 'recorded_by').order_by('-encounter_date')


def get_recent_home_visits(limit: int = 20) -> QuerySet[Encounter]:
    return Encounter.objects.filter(encounter_type=EncounterTypeChoices.HOME_VISIT).select_related('patient', 'recorded_by').order_by('-encounter_date')[:limit]
