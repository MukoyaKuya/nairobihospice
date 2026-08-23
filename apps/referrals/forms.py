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


class ReferralReviewForm(forms.ModelForm):
    class Meta:
        model = Referral
        fields = ['status', 'assigned_reviewer', 'review_notes', 'rejection_reason']
        widgets = {
            'review_notes': forms.Textarea(attrs={'rows': 3}),
            'rejection_reason': forms.Textarea(attrs={'rows': 2}),
        }
