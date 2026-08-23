from django.db.models import QuerySet

from apps.patients.models import Patient

from .models import MedicationStatement, MedicationStatusChoices


def get_active_medications(patient: Patient) -> QuerySet[MedicationStatement]:
    return MedicationStatement.objects.filter(patient=patient, status=MedicationStatusChoices.ACTIVE).order_by('-start_date')


def get_patient_medication_history(patient: Patient) -> QuerySet[MedicationStatement]:
    return MedicationStatement.objects.filter(patient=patient).order_by('-status', '-start_date')
