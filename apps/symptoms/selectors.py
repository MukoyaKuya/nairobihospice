from django.db.models import QuerySet

from apps.patients.models import Patient

from .models import SymptomAssessmentRecord


def get_patient_symptom_history(patient: Patient) -> QuerySet[SymptomAssessmentRecord]:
    return SymptomAssessmentRecord.objects.filter(patient=patient).prefetch_related('scores').select_related('recorded_by').order_by('-recorded_at')


def get_patient_symptom_trends(patient: Patient):
    """
    Returns structured list of chronological points for Chart.js / visual trend graph.
    """
    records = SymptomAssessmentRecord.objects.filter(patient=patient).prefetch_related('scores').order_by('recorded_at')

    dates = []
    pain_series = []
    fatigue_series = []
    breathlessness_series = []
    nausea_series = []
    wellbeing_series = []
    distress_series = []

    for r in records:
        dates.append(r.recorded_at.strftime('%d %b'))
        distress_series.append(r.total_distress_score)

        score_map = {s.symptom_type: s.score for s in r.scores.all()}
        pain_series.append(score_map.get('PAIN', 0))
        fatigue_series.append(score_map.get('TIREDNESS', 0))
        breathlessness_series.append(score_map.get('SHORTNESS_OF_BREATH', 0))
        nausea_series.append(score_map.get('NAUSEA', 0))
        wellbeing_series.append(score_map.get('WELLBEING', 0))

    return {
        'dates': dates,
        'pain': pain_series,
        'fatigue': fatigue_series,
        'breathlessness': breathlessness_series,
        'nausea': nausea_series,
        'wellbeing': wellbeing_series,
        'distress': distress_series,
    }
