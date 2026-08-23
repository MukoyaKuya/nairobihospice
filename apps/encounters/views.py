from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views.generic import DetailView, ListView, View

from apps.accounts.permissions import ClinicalStaffRequiredMixin
from apps.patients.access import authorized_patient_queryset, get_authorized_patient_or_404

from .forms import EncounterForm
from .models import Encounter, EncounterTypeChoices


class EncounterListView(LoginRequiredMixin, ListView):
    model = Encounter
    template_name = 'encounters/encounter_list.html'
    context_object_name = 'encounters'
    paginate_by = 20

    def get_queryset(self):
        qs = Encounter.objects.select_related('patient', 'recorded_by').order_by('-encounter_date', '-created_at')
        if not self.request.user.is_clinical and not self.request.user.is_manager:
            return qs.none()
        qs = qs.filter(patient__in=authorized_patient_queryset(self.request.user))
        enc_type = self.request.GET.get('type')
        if enc_type:
            qs = qs.filter(encounter_type=enc_type)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['type_choices'] = EncounterTypeChoices.choices
        context['selected_type'] = self.request.GET.get('type', '')
        return context


class EncounterDetailView(ClinicalStaffRequiredMixin, DetailView):
    model = Encounter
    template_name = 'encounters/encounter_detail.html'
    context_object_name = 'encounter'

    def get_queryset(self):
        return super().get_queryset().filter(patient__in=authorized_patient_queryset(self.request.user))


class EncounterCreateView(ClinicalStaffRequiredMixin, View):
    def get(self, request, patient_id):
        if request.user.is_receptionist:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Receptionists are not authorized to record clinical encounters.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        initial_type = request.GET.get('type', EncounterTypeChoices.CLINIC_VISIT)
        initial_loc = 'Nairobi Hospice Clinic' if initial_type == EncounterTypeChoices.CLINIC_VISIT else (patient.address or 'Home')
        form = EncounterForm(initial={'encounter_type': initial_type, 'location': initial_loc})
        return render(request, 'encounters/encounter_form.html', {'form': form, 'patient': patient})

    def post(self, request, patient_id):
        if request.user.is_receptionist:
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Receptionists are not authorized to record clinical encounters.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        form = EncounterForm(request.POST)
        if form.is_valid():
            encounter = form.save(commit=False)
            encounter.patient = patient
            encounter.recorded_by = request.user
            encounter.episode = patient.episodes.filter(status='ACTIVE').first()
            encounter.save()
            messages.success(request, f"{encounter.get_encounter_type_display()} recorded for {patient.full_name}.")
            return redirect('patients:patient_detail', pk=patient.pk)
        return render(request, 'encounters/encounter_form.html', {'form': form, 'patient': patient})
