from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import View

from apps.accounts.selectors import get_active_staff
from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.operations.models import AppointmentDeletionRequest, DeletionRequestStatusChoices
from apps.patients.access import (
    authorized_appointment_queryset,
    authorized_patient_queryset,
    can_manage_all_patients,
    get_operational_patient_or_404,
)
from apps.patients.models import Patient

from .forms import AppointmentForm
from .models import Appointment, AppointmentStatusChoices, AppointmentTypeChoices
from .selectors import (
    get_daily_appointments,
    get_upcoming_appointments,
    get_weekly_appointments,
    search_appointments,
)
from .services import schedule_appointment, update_appointment_status


class AppointmentCalendarView(LoginRequiredMixin, View):
    def get(self, request):
        today = timezone.localdate()
        date_str = request.GET.get('date')
        if date_str:
            try:
                selected_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                selected_date = today
        else:
            selected_date = today

        visible_appointments = authorized_appointment_queryset(request.user)
        daily = get_daily_appointments(selected_date).filter(pk__in=visible_appointments.values('pk'))
        upcoming = get_upcoming_appointments(today, limit=100, queryset=visible_appointments)
        weekly = get_weekly_appointments(today).filter(pk__in=visible_appointments.values('pk'))

        # Multi-parameter Search & Filter
        query = request.GET.get('q', '')
        status = request.GET.get('status', '')
        staff_id = request.GET.get('staff_id', '')
        appt_type = request.GET.get('type', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')

        clinical_search = bool(getattr(request.user, 'is_clinical', False) or can_manage_all_patients(request.user))
        all_appointments = search_appointments(
            query=query,
            status=status,
            staff_id=staff_id,
            appointment_type=appt_type,
            date_from=date_from,
            date_to=date_to,
            is_clinical=clinical_search,
        ).filter(pk__in=visible_appointments.values('pk'))

        active_staff = get_active_staff()

        from collections import defaultdict
        grouped_dict = defaultdict(list)
        for appt in upcoming:
            grouped_dict[appt.scheduled_date].append(appt)

        grouped_upcoming = []
        for d in sorted(grouped_dict.keys()):
            grouped_upcoming.append({
                'date': d,
                'is_today': (d == today),
                'is_tomorrow': (d == today + timezone.timedelta(days=1)),
                'appointments': sorted(grouped_dict[d], key=lambda a: (a.scheduled_time or timezone.datetime.min.time()))
            })

        recent_patients = Patient.objects.filter(status='ACTIVE')
        if not (getattr(request.user, 'is_receptionist', False) or can_manage_all_patients(request.user)):
            recent_patients = recent_patients.filter(pk__in=authorized_patient_queryset(request.user).values('pk'))
        recent_patients = recent_patients.order_by('-registration_date', 'last_name')[:40]

        pending_deletion_appt_ids = set(
            AppointmentDeletionRequest.objects.filter(
                status=DeletionRequestStatusChoices.PENDING
            ).values_list('appointment_id', flat=True)
        )

        return render(request, 'appointments/appointment_calendar.html', {
            'today': today,
            'selected_date': selected_date,
            'daily_appointments': daily,
            'upcoming_appointments': upcoming,
            'grouped_upcoming': grouped_upcoming,
            'weekly_appointments': weekly,
            'all_appointments': all_appointments,
            'active_staff': active_staff,
            'recent_patients': recent_patients,
            'pending_deletion_appt_ids': pending_deletion_appt_ids,
            'status_choices': AppointmentStatusChoices.choices,
            'type_choices': AppointmentTypeChoices.choices,
            'search_query': query,
            'selected_status': status,
            'selected_staff_id': staff_id,
            'selected_type': appt_type,
            'selected_date_from': date_from,
            'selected_date_to': date_to,
            'clinical_access': bool(getattr(request.user, 'is_clinical', False) or can_manage_all_patients(request.user)),
            'is_pharmacist': getattr(request.user, 'is_pharmacist', False),
        })


class AppointmentCreateView(LoginRequiredMixin, View):
    def get(self, request, patient_id):
        patient = get_operational_patient_or_404(request.user, patient_id)
        initial_date = timezone.now().date()
        initial_type = request.GET.get('type', AppointmentTypeChoices.CLINIC_VISIT)
        initial_loc = 'Nairobi Hospice' if initial_type == AppointmentTypeChoices.CLINIC_VISIT else (patient.address or 'Home')
        form = AppointmentForm(initial={
            'appointment_type': initial_type,
            'scheduled_date': initial_date,
            'location': initial_loc,
        })
        return render(request, 'appointments/appointment_form.html', {'form': form, 'patient': patient})

    def post(self, request, patient_id):
        patient = get_operational_patient_or_404(request.user, patient_id)
        form = AppointmentForm(request.POST)
        if form.is_valid():
            cd = form.cleaned_data
            appt = schedule_appointment(
                patient=patient,
                staff_member=cd['staff_member'],
                appointment_type=cd['appointment_type'],
                scheduled_date=cd['scheduled_date'],
                scheduled_time=cd['scheduled_time'],
                duration_minutes=cd.get('duration_minutes', 45),
                location=cd.get('location', ''),
                reason=cd.get('reason', ''),
                notes=cd.get('notes', ''),
                user=request.user,
            )
            messages.success(
                request,
                f"Appointment scheduled for {patient.full_name} on {appt.scheduled_date} with {appt.staff_member.user.display_name}."
            )
            return redirect('appointments:calendar')
        return render(request, 'appointments/appointment_form.html', {'form': form, 'patient': patient})


class AppointmentStatusUpdateView(LoginRequiredMixin, View):
    def post(self, request, pk):
        appt = get_object_or_404(authorized_appointment_queryset(request.user), pk=pk)
        new_status = request.POST.get('status')
        outcome = request.POST.get('outcome_notes', '') if (request.user.is_clinical or request.user.is_manager) else ''
        if new_status in AppointmentStatusChoices.values:
            from django.core.exceptions import ValidationError
            try:
                update_appointment_status(
                    appointment=appt,
                    status=new_status,
                    outcome_notes=outcome,
                    user=request.user,
                )
                messages.success(request, f"Appointment status for {appt.patient.full_name} updated to {appt.get_status_display()}.")
            except ValidationError as exc:
                messages.error(request, str(exc.message if hasattr(exc, 'message') else exc))
        
        next_url = request.POST.get('next') or request.GET.get('next')
        from django.utils.http import url_has_allowed_host_and_scheme
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('appointments:calendar')


class AppointmentDeletionRequestCreateView(LoginRequiredMixin, View):
    """
    Submits a deletion request for a completed, cancelled, or obsolete appointment/task,
    which must be reviewed and approved by Operations/Management before deletion.
    """
    def post(self, request, pk):
        appt = get_object_or_404(authorized_appointment_queryset(request.user), pk=pk)
        
        # Check if already has a pending deletion request
        existing = AppointmentDeletionRequest.objects.filter(
            appointment=appt, status=DeletionRequestStatusChoices.PENDING
        ).first()
        if existing:
            messages.warning(request, f"A deletion request for this appointment is already pending Operations approval.")
            return redirect('appointments:calendar')
            
        reason = request.POST.get('reason', '').strip()
        if not reason:
            reason = "Completed task/visit marked for deletion by clinical/front desk staff."
            
        deletion_req = AppointmentDeletionRequest.objects.create(
            appointment=appt,
            appointment_id_copy=appt.id,
            patient_name=appt.patient.full_name,
            hospice_number=appt.patient.hospice_number,
            scheduled_date=appt.scheduled_date,
            scheduled_time=appt.scheduled_time,
            appointment_type=appt.get_appointment_type_display(),
            appointment_status=appt.get_status_display(),
            clinician_name=appt.staff_member.user.display_name if (appt.staff_member and appt.staff_member.user) else '',
            requested_by=request.user,
            reason=reason,
            status=DeletionRequestStatusChoices.PENDING,
        )
        
        log_audit_event(
            action=AuditAction.CREATE,
            resource_type='AppointmentDeletionRequest',
            resource_id=str(deletion_req.id),
            summary=f"Requested deletion of appointment for {appt.patient.full_name} on {appt.scheduled_date}. Reason: {reason}",
            user=request.user,
        )

        from apps.notifications.services import notify_operations_of_deletion_request
        notify_operations_of_deletion_request(deletion_req=deletion_req, request_type='appointment')

        messages.success(
            request, 
            f"Deletion request for {appt.patient.full_name}'s appointment on {appt.scheduled_date} has been submitted for Operations approval."
        )
        
        next_url = request.POST.get('next') or request.GET.get('next')
        from django.utils.http import url_has_allowed_host_and_scheme
        if next_url and url_has_allowed_host_and_scheme(next_url, allowed_hosts={request.get_host()}):
            return redirect(next_url)
        return redirect('appointments:calendar')


class HomeRouteLogisticsView(LoginRequiredMixin, View):
    """
    Dedicated field logistics, patient residence, and navigational route dispatch workspace
    for Palliative Care Nurses, Clinical Officers, and home outreach teams.
    """
    def get(self, request):
        from apps.patients.access import can_manage_all_patients
        if not (request.user.is_clinical or can_manage_all_patients(request.user)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Home visit route logistics are restricted to clinical care and management teams.")

        today = timezone.localdate()
        date_str = request.GET.get('date')
        if date_str:
            try:
                selected_date = timezone.datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                selected_date = today
        else:
            selected_date = today

        prev_date = selected_date - timezone.timedelta(days=1)
        next_date = selected_date + timezone.timedelta(days=1)

        visible_appointments = authorized_appointment_queryset(request.user)
        home_visits = (
            Appointment.objects.filter(
                appointment_type=AppointmentTypeChoices.HOME_VISIT,
                scheduled_date=selected_date,
            )
            .filter(pk__in=visible_appointments.values('pk'))
            .select_related('patient', 'staff_member__user')
            .order_by('scheduled_time', 'patient__sub_county', 'patient__last_name')
        )

        total_stops = home_visits.count()
        completed_stops = home_visits.filter(status=AppointmentStatusChoices.COMPLETED).count()
        pending_stops = home_visits.filter(status=AppointmentStatusChoices.SCHEDULED).count()

        # Extract unique areas / sub-counties and assigned nurses
        areas = sorted(list(set([v.patient.sub_county or v.patient.county for v in home_visits if (v.patient.sub_county or v.patient.county)])))
        assigned_staff = sorted(list(set([v.staff_member.user.display_name for v in home_visits if (v.staff_member and v.staff_member.user)])))

        return render(request, 'appointments/home_routes.html', {
            'today': today,
            'selected_date': selected_date,
            'prev_date': prev_date,
            'next_date': next_date,
            'home_visits': home_visits,
            'total_stops': total_stops,
            'completed_stops': completed_stops,
            'pending_stops': pending_stops,
            'areas': areas,
            'assigned_staff': assigned_staff,
            'status_choices': AppointmentStatusChoices.choices,
        })
