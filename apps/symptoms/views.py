from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import View

from apps.accounts.permissions import ClinicalStaffRequiredMixin
from apps.patients.access import get_authorized_patient_or_404

from .forms import ESASAssessmentForm
from .models import SymptomTypeChoices
from .selectors import get_patient_symptom_trends
from .services import record_esas_assessment


class SymptomCreateView(ClinicalStaffRequiredMixin, View):
    def get(self, request, patient_id):
        if request.user.is_receptionist:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Receptionists are not authorized to record ESAS symptom assessments.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        form = ESASAssessmentForm()
        return render(request, 'symptoms/symptom_form.html', {'form': form, 'patient': patient})

    def post(self, request, patient_id):
        if request.user.is_receptionist:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Receptionists are not authorized to record ESAS symptom assessments.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        form = ESASAssessmentForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            scores = {
                SymptomTypeChoices.PAIN: cd['pain'],
                SymptomTypeChoices.TIREDNESS: cd['tiredness'],
                SymptomTypeChoices.DROWSINESS: cd['drowsiness'],
                SymptomTypeChoices.NAUSEA: cd['nausea'],
                SymptomTypeChoices.LACK_OF_APPETITE: cd['appetite'],
                SymptomTypeChoices.SHORTNESS_OF_BREATH: cd['breathlessness'],
                SymptomTypeChoices.DEPRESSION: cd['depression'],
                SymptomTypeChoices.ANXIETY: cd['anxiety'],
                SymptomTypeChoices.WELLBEING: cd['wellbeing'],
                SymptomTypeChoices.CONSTIPATION: cd['constipation'],
            }
            rec = record_esas_assessment(
                patient=patient,
                symptom_scores=scores,
                clinical_notes=cd.get('clinical_notes', ''),
                user=request.user,
            )
            messages.success(request, f"ESAS Symptom evaluation recorded (Total Distress Score: {rec.total_distress_score}/100).")
            return redirect('patients:patient_detail', pk=patient.pk)
        return render(request, 'symptoms/symptom_form.html', {'form': form, 'patient': patient})


class SymptomTrendJsonView(ClinicalStaffRequiredMixin, View):
    def get(self, request, patient_id):
        patient = get_authorized_patient_or_404(request.user, patient_id)
        trends = get_patient_symptom_trends(patient)
        return JsonResponse(trends)
