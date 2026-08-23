from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.views.generic import View

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.patients.access import get_authorized_patient_or_404

from .forms import CommunicationRecordForm


class CommunicationCreateView(LoginRequiredMixin, View):
    def get(self, request, patient_id):
        patient = get_authorized_patient_or_404(request.user, patient_id)
        form = CommunicationRecordForm()
        return render(request, 'communications/communication_form.html', {'form': form, 'patient': patient})

    def post(self, request, patient_id):
        patient = get_authorized_patient_or_404(request.user, patient_id)
        form = CommunicationRecordForm(request.POST)
        if form.is_valid():
            comm = form.save(commit=False)
            comm.patient = patient
            comm.recorded_by = request.user
            comm.save()

            log_audit_event(
                action=AuditAction.CREATE,
                resource_type='Communication',
                resource_id=str(comm.id),
                summary=f"Logged {comm.get_communication_type_display()} with {comm.contact_person} for {patient.full_name}",
                user=request.user,
            )
            messages.success(request, "Communication log saved.")
            return redirect('patients:patient_detail', pk=patient.pk)
        return render(request, 'communications/communication_form.html', {'form': form, 'patient': patient})
