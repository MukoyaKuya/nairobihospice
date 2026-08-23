from django import forms

from .models import Encounter


class EncounterForm(forms.ModelForm):
    class Meta:
        model = Encounter
        fields = [
            'encounter_type', 'encounter_date', 'location',
            'reason', 'clinical_notes', 'interventions_performed',
            'next_followup_date', 'next_followup_plan'
        ]
        widgets = {
            'encounter_date': forms.DateInput(attrs={'type': 'date'}),
            'next_followup_date': forms.DateInput(attrs={'type': 'date'}),
            'clinical_notes': forms.Textarea(attrs={
                'rows': 5,
                'placeholder': 'Subjective findings, patient reports, examination, pain state, psychosocial observations...'
            }),
            'interventions_performed': forms.Textarea(attrs={
                'rows': 3,
                'placeholder': 'Medication adjustments, wound care, counseling provided, family education...'
            }),
            'next_followup_plan': forms.Textarea(attrs={
                'rows': 2,
                'placeholder': 'Plan for next visit or telephone review...'
            }),
        }
