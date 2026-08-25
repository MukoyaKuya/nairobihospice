from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views.generic import ListView, View

from apps.accounts.permissions import ClinicalStaffRequiredMixin, can_record_medications
from apps.patients.access import authorized_patient_queryset, get_authorized_patient_or_404

from .forms import MedicationStatementForm
from .models import MedicationStatement, MedicationStatusChoices
from .services import prescribe_medication, update_medication_status


class MedicationListView(LoginRequiredMixin, ListView):
    model = MedicationStatement
    template_name = 'medications/medication_list.html'
    context_object_name = 'medications'
    paginate_by = 30

    def get_queryset(self):
        user = self.request.user
        if not user.is_clinical and not user.is_manager and not user.is_administrator and not user.is_superuser and not getattr(user, 'is_pharmacist', False):
            return MedicationStatement.objects.none()
        
        queryset = MedicationStatement.objects.select_related('patient', 'prescriber').order_by('-start_date', '-created_at')
        if not (user.is_manager or user.is_administrator or user.is_superuser):
            auth_patients = authorized_patient_queryset(user)
            queryset = queryset.filter(patient__in=auth_patients)
        
        status = self.request.GET.get('status')
        if status:
            queryset = queryset.filter(status=status)
            
        search = self.request.GET.get('search')
        if search:
            from django.db.models import Q
            queryset = queryset.filter(
                Q(medication_name__icontains=search)
                | Q(patient__first_name__icontains=search)
                | Q(patient__last_name__icontains=search)
                | Q(patient__hospice_number__icontains=search)
                | Q(indication__icontains=search)
                | Q(prescriber_name__icontains=search)
            )
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user
        if user.is_manager or user.is_administrator or user.is_superuser:
            base_qs = MedicationStatement.objects.all()
        else:
            base_qs = MedicationStatement.objects.filter(patient__in=authorized_patient_queryset(user))
        context['total_count'] = base_qs.count()
        context['active_count'] = base_qs.filter(status='ACTIVE').count()
        context['stopped_count'] = base_qs.filter(status='STOPPED').count()
        context['on_hold_count'] = base_qs.filter(status='ON_HOLD').count()
        return context


class MedicationCreateView(ClinicalStaffRequiredMixin, View):
    def get(self, request, patient_id):
        if not can_record_medications(request.user):
            raise PermissionDenied("Only prescribers, nurses, and pharmacists may record medications.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        form = MedicationStatementForm()
        return render(request, 'medications/medication_form.html', {'form': form, 'patient': patient})

    def post(self, request, patient_id):
        if not can_record_medications(request.user):
            raise PermissionDenied("Only prescribers, nurses, and pharmacists may record medications.")
        patient = get_authorized_patient_or_404(request.user, patient_id)
        form = MedicationStatementForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            med = prescribe_medication(
                patient=patient,
                medication_name=cd['medication_name'],
                dosage=cd['dosage'],
                route=cd['route'],
                frequency=cd['frequency'],
                indication=cd.get('indication', ''),
                instructions_for_caregiver=cd.get('instructions_for_caregiver', ''),
                start_date=cd.get('start_date'),
                user=request.user,
            )
            messages.success(request, f"Medication {med.medication_name} added to {patient.full_name}'s record.")
            return redirect('patients:patient_detail', pk=patient.pk)
        return render(request, 'medications/medication_form.html', {'form': form, 'patient': patient})


class MedicationStatusUpdateView(ClinicalStaffRequiredMixin, View):
    def post(self, request, pk):
        if not can_record_medications(request.user):
            raise PermissionDenied("Only prescribers, nurses, and pharmacists may update medication status.")
        med = get_object_or_404(
            MedicationStatement.objects.filter(patient__in=authorized_patient_queryset(request.user)), pk=pk
        )
        new_status = request.POST.get('status')
        reason = request.POST.get('reason', '')
        if new_status in MedicationStatusChoices.values:
            update_medication_status(
                medication=med,
                status=new_status,
                reason=reason,
                user=request.user,
            )
            messages.success(request, f"Medication {med.medication_name} status updated to {med.get_status_display()}.")
        return redirect('patients:patient_detail', pk=med.patient.pk)
