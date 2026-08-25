from django import forms

from apps.accounts.models import RoleChoices, StaffProfile

from .models import Appointment

CLINICAL_STAFF_ROLES = [
    RoleChoices.DOCTOR,
    RoleChoices.CLINICAL_OFFICER,
    RoleChoices.NURSE,
    RoleChoices.COUNSELLOR,
    RoleChoices.SOCIAL_WORKER,
    RoleChoices.PHARMACIST,
]


class AppointmentForm(forms.ModelForm):
    staff_member = forms.ModelChoiceField(
        queryset=StaffProfile.objects.filter(
            is_active_staff=True,
            role__in=CLINICAL_STAFF_ROLES,
        ).select_related('user').order_by('user__first_name', 'user__last_name'),
        label="Assigned Clinician / Care Team Member",
        help_text="Select a qualified clinician, palliative nurse, counsellor, or social worker."
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
