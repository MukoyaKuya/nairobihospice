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
        help_text="Select a qualified clinician, palliative nurse, counsellor, or social worker.",
        widget=forms.Select(attrs={
            'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg text-slate-900 bg-white focus:ring-1 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'
        })
    )

    class Meta:
        model = Appointment
        fields = ['appointment_type', 'staff_member', 'scheduled_date', 'scheduled_time', 'duration_minutes', 'location', 'reason', 'notes']
        widgets = {
            'appointment_type': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg text-slate-900 bg-white focus:ring-1 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'
            }),
            'scheduled_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg text-slate-900 bg-white focus:ring-1 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'
            }),
            'scheduled_time': forms.TimeInput(attrs={
                'type': 'time',
                'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg text-slate-900 bg-white focus:ring-1 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'
            }),
            'duration_minutes': forms.NumberInput(attrs={
                'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg text-slate-900 bg-white focus:ring-1 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none',
                'min': 15,
                'max': 240,
                'step': 15
            }),
            'location': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg text-slate-900 bg-white focus:ring-1 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none',
                'placeholder': 'e.g. Nairobi Hospice Clinic, Home Visit Residence, Hospital Ward'
            }),
            'reason': forms.TextInput(attrs={
                'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg text-slate-900 bg-white focus:ring-1 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none',
                'placeholder': 'e.g. Monthly pain medication review, home wound dressing, caregiver counselling'
            }),
            'notes': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg text-slate-900 bg-white focus:ring-1 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none',
                'placeholder': 'Optional clinical notes or special instructions for visit...'
            }),
        }


class AppointmentStatusForm(forms.ModelForm):
    class Meta:
        model = Appointment
        fields = ['status', 'outcome_notes']
        widgets = {
            'outcome_notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Consultation outcome, follow-up required...'}),
        }

    def clean_status(self):
        from apps.appointments.models import AppointmentStatusChoices
        from django.utils import timezone
        status = self.cleaned_data.get('status')
        if status == AppointmentStatusChoices.COMPLETED and self.instance and self.instance.scheduled_date > timezone.now().date():
            raise forms.ValidationError("A future appointment cannot be marked as completed until the visit date.")
        return status
