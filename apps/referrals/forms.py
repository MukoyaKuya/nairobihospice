from django import forms

from .models import Referral


class ReferralForm(forms.ModelForm):
    class Meta:
        model = Referral
        fields = [
            'patient_name', 'date_of_birth', 'approximate_age', 'sex',
            'phone_number', 'alternative_phone', 'address', 'county', 'sub_county', 'landmark',
            'referral_source', 'referring_facility', 'referring_clinician_name',
            'referring_clinician_phone', 'referring_clinician_email',
            'referral_date', 'priority', 'primary_diagnosis', 'reason_for_referral',
            'clinical_summary', 'current_medications'
        ]
        widgets = {
            'referral_date': forms.DateInput(attrs={'type': 'date'}),
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'reason_for_referral': forms.Textarea(attrs={'rows': 3}),
            'clinical_summary': forms.Textarea(attrs={'rows': 3}),
            'current_medications': forms.Textarea(attrs={'rows': 2}),
        }

    def __init__(self, *args, clinical_access: bool = True, **kwargs):
        super().__init__(*args, **kwargs)
        self.clinical_access = clinical_access
        if not clinical_access:
            self.fields['primary_diagnosis'].required = False
            self.fields['clinical_summary'].required = False
            self.fields['current_medications'].required = False

    def clean_primary_diagnosis(self):
        diag = self.cleaned_data.get('primary_diagnosis', '').strip()
        if not getattr(self, 'clinical_access', True) or not diag:
            return 'Pending Clinical Review'
        return diag

    def clean_reason_for_referral(self):
        if not getattr(self, 'clinical_access', True):
            return 'Palliative care intake evaluation requested.'
        reason = self.cleaned_data.get('reason_for_referral', '').strip()
        if not reason:
            raise forms.ValidationError('A reason for referral is required.')
        return reason


class ReferralReviewForm(forms.ModelForm):
    class Meta:
        model = Referral
        fields = ['status', 'assigned_reviewer', 'review_notes', 'rejection_reason']
        widgets = {
            'review_notes': forms.Textarea(attrs={'rows': 3}),
            'rejection_reason': forms.Textarea(attrs={'rows': 2}),
        }


class ReferralConvertForm(forms.Form):
    primary_nurse = forms.ModelChoiceField(
        queryset=None,
        required=True,
        empty_label="-- Select Primary Palliative Nurse --",
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-xl bg-white focus:ring-2 focus:ring-[#002D62] focus:outline-none font-semibold text-slate-900'})
    )
    primary_doctor = forms.ModelChoiceField(
        queryset=None,
        required=True,
        empty_label="-- Select Primary Doctor / CO --",
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-xl bg-white focus:ring-2 focus:ring-[#002D62] focus:outline-none font-semibold text-slate-900'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.accounts.models import RoleChoices, StaffProfile
        self.fields['primary_nurse'].queryset = StaffProfile.objects.filter(
            role=RoleChoices.NURSE, is_active_staff=True
        ).select_related('user')
        self.fields['primary_doctor'].queryset = StaffProfile.objects.filter(
            role__in=[RoleChoices.DOCTOR, RoleChoices.CLINICAL_OFFICER], is_active_staff=True
        ).select_related('user')
