from pathlib import Path

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.http import FileResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import View

from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.patients.access import authorized_patient_queryset, can_manage_all_patients, get_authorized_patient_or_404

from .forms import PatientDocumentForm
from .models import PatientDocument


class DocumentUploadView(LoginRequiredMixin, View):
    def get(self, request, patient_id):
        if not request.user.is_clinical and not request.user.is_manager:
            raise PermissionDenied("Receptionists are not authorized to upload clinical documents.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        form = PatientDocumentForm()
        return render(request, 'documents/document_form.html', {'form': form, 'patient': patient})

    def post(self, request, patient_id):
        if not request.user.is_clinical and not request.user.is_manager:
            raise PermissionDenied("Receptionists are not authorized to upload clinical documents.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        form = PatientDocumentForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.patient = patient
            doc.uploaded_by = request.user
            if 'file' in request.FILES:
                doc.file_size_bytes = request.FILES['file'].size
            doc.save()

            log_audit_event(
                action=AuditAction.CREATE,
                resource_type='Document',
                resource_id=str(doc.id),
                summary=f"Uploaded clinical document '{doc.title}' ({doc.get_category_display()}) for {patient.full_name}",
                user=request.user,
            )
            messages.success(request, f"Document '{doc.title}' uploaded securely.")
            return redirect('patients:patient_detail', pk=patient.pk)
        return render(request, 'documents/document_form.html', {'form': form, 'patient': patient})


class DocumentDownloadView(LoginRequiredMixin, View):
    """Serve a clinical document only after Django authorization succeeds."""

    def get(self, request, pk):
        if not request.user.is_clinical and not request.user.is_manager:
            raise PermissionDenied('You are not authorized to download clinical documents.')

        # A clinical role is not sufficient by itself: documents must follow
        # the same patient-level access boundary as the rest of the chart.
        document_queryset = PatientDocument.objects.select_related('patient', 'uploaded_by')
        if not can_manage_all_patients(request.user):
            document_queryset = document_queryset.filter(
                patient__in=authorized_patient_queryset(request.user).values('pk')
            )
        document = get_object_or_404(document_queryset, pk=pk)
        if not document.file:
            raise PermissionDenied('This document has no available file.')
        log_audit_event(
            action=AuditAction.VIEW,
            resource_type='Document',
            resource_id=str(document.id),
            summary=f"Downloaded clinical document '{document.title}' for {document.patient.full_name}",
            user=request.user,
        )
        return FileResponse(
            document.file.open('rb'),
            as_attachment=True,
            filename=Path(document.file.name).name,
        )
