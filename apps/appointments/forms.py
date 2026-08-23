from django import forms

from apps.accounts.models import StaffProfile

from .models import Appointment


class AppointmentForm(forms.ModelForm):
    staff_member = forms.ModelChoiceField(
        queryset=StaffProfile.objects.filter(is_active_staff=True).select_related('user'),
        label="Assigned Clinician / Team Member"
    )

    class Meta:
        model = Appointment
        fields = ['appointment_type', 'staff_member', 'scheduled_date', 'scheduled_time', 'duration_minutes', 'location', 'reason', 'notes']
        widgets = {
            'scheduled_date': forms.DateInput(attrs={'type': 'date'}),
            'scheduled_time': forms.TimeInput(attrs={'type': 'time'}),
            'reason': forms.TextInput(attrs={'placeholder': 'e.g. Monthly pain medication review, home wound dressing'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class AppointmentStatusForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['status', 'outcome_notes']
        widgets = {
            'outcome_notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Consultation outcome, follow-up required...'}),
        }
