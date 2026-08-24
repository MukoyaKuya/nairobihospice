from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.generic import ListView, View

from apps.accounts.permissions import ClinicalStaffRequiredMixin
from apps.patients.access import authorized_patient_queryset, get_authorized_patient_or_404

from .forms import ESASAssessmentForm
from .models import SymptomAssessmentRecord, SymptomScore, SymptomTypeChoices
from .selectors import get_patient_symptom_trends
from .services import record_esas_assessment


class SymptomListView(LoginRequiredMixin, ListView):
    """
    Registry & Tracking of Edmonton Symptom Assessment System (ESAS) distress evaluations.
    """
    model = SymptomAssessmentRecord
    template_name = 'symptoms/symptom_list.html'
    context_object_name = 'symptom_records'
    paginate_by = 20

    def get_queryset(self):
        if not self.request.user.is_clinical and not self.request.user.is_manager:
            return SymptomAssessmentRecord.objects.none()

        qs = SymptomAssessmentRecord.objects.select_related(
            'patient', 'recorded_by'
        ).prefetch_related('scores').order_by('-recorded_at')

        qs = qs.filter(patient__in=authorized_patient_queryset(self.request.user))

        # Search filter
        q = self.request.GET.get('q', '').strip()
        if q:
            qs = qs.filter(
                Q(patient__first_name__icontains=q)
                | Q(patient__last_name__icontains=q)
                | Q(patient__middle_name__icontains=q)
                | Q(patient__hospice_number__icontains=q)
                | Q(clinical_notes__icontains=q)
            )

        # Filter by severity
        filter_type = self.request.GET.get('filter', '').strip()
        if filter_type in ['acute_distress', 'severe']:
            qs = qs.filter(total_distress_score__gte=30)
        elif filter_type == 'pain_spikes':
            qs = qs.filter(scores__symptom_type=SymptomTypeChoices.PAIN, scores__score__gte=7).distinct()

        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        base_qs = SymptomAssessmentRecord.objects.filter(
            patient__in=authorized_patient_queryset(self.request.user)
        )
        context['total_count'] = base_qs.count()
        context['acute_distress_count'] = base_qs.filter(total_distress_score__gte=30).count()
        context['pain_spikes_count'] = base_qs.filter(scores__symptom_type=SymptomTypeChoices.PAIN, scores__score__gte=7).distinct().count()
        context['current_filter'] = self.request.GET.get('filter', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


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
