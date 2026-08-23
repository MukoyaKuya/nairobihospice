from django import forms

from .models import CommunicationRecord


class CommunicationRecordForm(forms.ModelForm):
    class Meta:
        model = CommunicationRecord
        fields = ['communication_type', 'contact_person', 'phone_or_email', 'summary', 'followup_required', 'followup_notes']
        widgets = {
            'contact_person': forms.TextInput(attrs={'placeholder': 'e.g. Caregiver Mary / Dr. Omwenga'}),
            'summary': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Discussion summary, advice provided, updates...'}),
            'followup_notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Follow-up actions needed...'}),
        }
