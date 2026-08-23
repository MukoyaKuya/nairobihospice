import csv

from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.generic import View

from apps.accounts.permissions import ManagerRequiredMixin
from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.encounters.models import Encounter
from apps.patients.models import Patient

from .selectors import get_clinical_dashboard_data, get_management_dashboard_data


class IndexRedirectView(View):
    def get(self, request):
        if not request.user.is_authenticated:
            return render(request, 'landing.html')
        if request.user.is_administrator or request.user.is_superuser:
            return redirect('admin:index')
        if request.user.is_manager:
            return redirect('reporting:management_dashboard')
        return redirect('reporting:clinical_dashboard')


class ClinicalDashboardView(LoginRequiredMixin, View):
    def get(self, request):
        data = get_clinical_dashboard_data(request.user)
        return render(request, 'reporting/clinical_dashboard.html', data)


class ManagementDashboardView(ManagerRequiredMixin, View):
    def get(self, request):
        data = get_management_dashboard_data()
        return render(request, 'reporting/management_dashboard.html', data)


class ExportPatientsCsvView(ManagerRequiredMixin, View):
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        filename = f"nairobi_hospice_patients_{timezone.now().strftime('%Y%m%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Hospice Number', 'Full Name', 'Sex', 'Age', 'Status', 'County', 'Sub County', 'Primary Diagnosis', 'Registration Date'])

        patients = Patient.objects.all().order_by('-registration_date')
        for p in patients:
            writer.writerow([
                p.hospice_number,
                p.full_name,
                p.get_sex_display(),
                p.age or 'N/A',
                p.get_status_display(),
                p.county,
                p.sub_county,
                p.primary_diagnosis,
                p.registration_date.strftime('%Y-%m-%d') if p.registration_date else ''
            ])

        log_audit_event(
            action=AuditAction.EXPORT,
            resource_type='PatientDataExport',
            summary="Exported full patient registry CSV",
            user=request.user,
        )
        return response


class ExportEncountersCsvView(ManagerRequiredMixin, View):
    def get(self, request):
        response = HttpResponse(content_type='text/csv')
        filename = f"nairobi_hospice_encounters_{timezone.now().strftime('%Y%m%d')}.csv"
        response['Content-Disposition'] = f'attachment; filename="{filename}"'

        writer = csv.writer(response)
        writer.writerow(['Date', 'Type', 'Patient ID', 'Patient Name', 'Location', 'Reason', 'Staff Member'])

        encounters = Encounter.objects.select_related('patient', 'recorded_by').order_by('-encounter_date')
        for e in encounters:
            writer.writerow([
                e.encounter_date.strftime('%Y-%m-%d'),
                e.get_encounter_type_display(),
                e.patient.hospice_number,
                e.patient.full_name,
                e.location,
                e.reason,
                e.recorded_by.display_name if e.recorded_by else 'N/A'
            ])

        log_audit_event(
            action=AuditAction.EXPORT,
            resource_type='EncounterDataExport',
            summary="Exported encounter history CSV",
            user=request.user,
        )
        return response
