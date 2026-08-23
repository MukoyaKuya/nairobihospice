from django import forms

from .models import MedicationStatement


class MedicationStatementForm(forms.ModelForm):
    class Meta:
        model = MedicationStatement
        fields = ['medication_name', 'dosage', 'route', 'frequency', 'indication', 'start_date', 'instructions_for_caregiver']
        widgets = {
            'medication_name': forms.TextInput(attrs={'placeholder': 'e.g. Oral Morphine Solution 5mg/5ml'}),
            'dosage': forms.TextInput(attrs={'placeholder': 'e.g. 10 mg (10 ml)'}),
            'frequency': forms.TextInput(attrs={'placeholder': 'e.g. Every 4 hours (q4h) round the clock'}),
            'indication': forms.TextInput(attrs={'placeholder': 'e.g. Somatic and visceral cancer pain'}),
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'instructions_for_caregiver': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Take with water; do not skip doses; give breakthrough dose if pain >= 5/10'}),
        }


class MedicationStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = MedicationStatement
        fields = ['status', 'discontinuation_reason']
        widgets = {
            'discontinuation_reason': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Reason for changing, holding, or discontinuing medication...'}),
        }
