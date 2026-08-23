from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import View

from apps.accounts.selectors import get_active_staff
from apps.patients.access import (
    authorized_appointment_queryset,
    authorized_patient_queryset,
    can_manage_all_patients,
    get_operational_patient_or_404,
)
from apps.patients.models import Patient

from .forms import AppointmentForm
from .models import AppointmentStatusChoices, AppointmentTypeChoices
from .selectors import (
    get_daily_appointments,
    get_upcoming_appointments,
    get_weekly_appointments,
    search_appointments,
)
from .services import schedule_appointment, update_appointment_status


class AppointmentCalendarView(LoginRequiredMixin, View):
    def get(self, request):
        today = timezone.now().date()
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

        all_appointments = search_appointments(
            query=query,
            status=status,
            staff_id=staff_id,
            appointment_type=appt_type,
            date_from=date_from,
            date_to=date_to,
        ).filter(pk__in=visible_appointments.values('pk'))

        active_staff = get_active_staff()

        from collections import defaultdict
        grouped_dict = defaultdict(list)
        for appt in upcoming:
            grouped_dict[appt.scheduled_date].append(appt)

        grouped_upcoming = []
        for d in sorted(grouped_dict.keys(), reverse=True):
            grouped_upcoming.append({
                'date': d,
                'is_today': (d == today),
                'is_tomorrow': (d == today + timezone.timedelta(days=1)),
                'appointments': grouped_dict[d]
            })

        recent_patients = Patient.objects.filter(status='ACTIVE')
        if request.user.is_clinical and not can_manage_all_patients(request.user):
            recent_patients = recent_patients.filter(pk__in=authorized_patient_queryset(request.user).values('pk'))
        recent_patients = recent_patients.order_by('-registration_date', 'last_name')[:40]

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
            'status_choices': AppointmentStatusChoices.choices,
            'type_choices': AppointmentTypeChoices.choices,
            'search_query': query,
            'selected_status': status,
            'selected_staff_id': staff_id,
            'selected_type': appt_type,
            'selected_date_from': date_from,
            'selected_date_to': date_to,
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
            update_appointment_status(
                appointment=appt,
                status=new_status,
                outcome_notes=outcome,
                user=request.user,
            )
            messages.success(request, f"Appointment for {appt.patient.full_name} updated to {appt.get_status_display()}.")
        return redirect('appointments:calendar')
