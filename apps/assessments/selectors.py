from django.db.models import QuerySet

from apps.patients.models import Patient

from .models import Assessment, AssessmentTypeChoices


def get_patient_assessments(patient: Patient) -> QuerySet[Assessment]:
    return Assessment.objects.filter(patient=patient).select_related('assessor', 'encounter').prefetch_related('amendments').order_by('-assessment_date', '-created_at')


def get_assessments_by_type(assessment_type: AssessmentTypeChoices) -> QuerySet[Assessment]:
    return Assessment.objects.filter(assessment_type=assessment_type).select_related('patient', 'assessor').order_by('-assessment_date')
