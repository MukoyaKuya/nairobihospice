from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import DetailView, ListView, View

from apps.accounts.permissions import ClinicalStaffRequiredMixin
from apps.patients.access import authorized_patient_queryset, get_authorized_patient_or_404

from .forms import AssessmentAmendmentForm, AssessmentForm
from .models import Assessment, AssessmentTypeChoices
from .services import amend_assessment


class AssessmentListView(LoginRequiredMixin, ListView):
    model = Assessment
    template_name = 'assessments/assessment_list.html'
    context_object_name = 'assessments'
    paginate_by = 20

    def get_queryset(self):
        qs = Assessment.objects.select_related('patient', 'assessor').order_by('-assessment_date', '-created_at')
        if not self.request.user.is_clinical and not self.request.user.is_manager:
            return qs.none()
        qs = qs.filter(patient__in=authorized_patient_queryset(self.request.user))
        ass_type = self.request.GET.get('type')
        if ass_type:
            qs = qs.filter(assessment_type=ass_type)
        return qs


class AssessmentDetailView(ClinicalStaffRequiredMixin, DetailView):
    model = Assessment
    template_name = 'assessments/assessment_detail.html'
    context_object_name = 'assessment'

    def get_queryset(self):
        return super().get_queryset().filter(patient__in=authorized_patient_queryset(self.request.user))

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['amendment_form'] = AssessmentAmendmentForm(initial={'amended_notes': self.object.clinical_summary})
        context['amendments'] = self.object.amendments.select_related('amended_by').order_by('-amended_at')
        return context


class AssessmentCreateView(ClinicalStaffRequiredMixin, View):
    def get(self, request, patient_id):
        if request.user.is_receptionist:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Receptionists are not authorized to record clinical assessments.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        ass_type = request.GET.get('type', AssessmentTypeChoices.INITIAL)
        form = AssessmentForm(initial={'assessment_type': ass_type})
        return render(request, 'assessments/assessment_form.html', {'form': form, 'patient': patient})

    def post(self, request, patient_id):
        if request.user.is_receptionist:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Receptionists are not authorized to record clinical assessments.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        form = AssessmentForm(request.POST)
        if form.is_valid():
            assessment = form.save(commit=False)
            assessment.patient = patient
            assessment.assessor = request.user
            structured = {
                'pain_site': form.cleaned_data.get('pain_site', ''),
                'pain_character': form.cleaned_data.get('pain_character', ''),
                'psychosocial_needs': form.cleaned_data.get('psychosocial_needs', ''),
                'spiritual_concerns': form.cleaned_data.get('spiritual_concerns', ''),
            }
            assessment.structured_data = structured
            assessment.save()
            messages.success(request, f"{assessment.get_assessment_type_display()} recorded for {patient.full_name}.")
            return redirect('patients:patient_detail', pk=patient.pk)
        return render(request, 'assessments/assessment_form.html', {'form': form, 'patient': patient})


class AssessmentAmendView(ClinicalStaffRequiredMixin, View):
    def post(self, request, pk):
        assessment = get_object_or_404(
            Assessment.objects.filter(patient__in=authorized_patient_queryset(request.user)), pk=pk
        )
        form = AssessmentAmendmentForm(request.POST)
        if form.is_valid():
            amend_assessment(
                assessment=assessment,
                reason_for_amendment=form.cleaned_data['reason_for_amendment'],
                updated_summary=form.cleaned_data['amended_notes'],
                user=request.user,
            )
            messages.success(request, "Assessment record successfully amended and logged.")
            return redirect('assessments:assessment_detail', pk=assessment.pk)
        return redirect('assessments:assessment_detail', pk=assessment.pk)
