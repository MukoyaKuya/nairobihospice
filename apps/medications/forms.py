from django import forms

from .models import MedicationStatement


class MedicationStatementForm(forms.ModelForm):
    class Meta:
        model = MedicationStatement
        fields = ['medication_name', 'dosage', 'route', 'frequency', 'indication', 'start_date', 'instructions_for_caregiver']
        widgets = {
            'medication_name': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2 text-xs bg-white border border-slate-300 rounded-xl text-slate-900 font-semibold focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': 'Select from drug catalog or type custom medication...',
                'autocomplete': 'off',
            }),
            'dosage': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2 text-xs bg-white border border-slate-300 rounded-xl text-slate-900 font-semibold focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': 'e.g. 10 mg (10 ml), 1+1+1',
                'autocomplete': 'off',
            }),
            'route': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-xl text-slate-800 font-semibold focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
            }),
            'frequency': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2 text-xs bg-white border border-slate-300 rounded-xl text-slate-900 font-semibold focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': 'e.g. Every 4 hours (q4h) round the clock',
                'autocomplete': 'off',
            }),
            'indication': forms.TextInput(attrs={
                'class': 'w-full px-3.5 py-2 text-xs bg-white border border-slate-300 rounded-xl text-slate-900 font-semibold focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': 'e.g. Somatic and visceral cancer pain, dyspnea, nausea',
                'autocomplete': 'off',
            }),
            'start_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-xl text-slate-800 font-semibold focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
            }),
            'instructions_for_caregiver': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full px-3.5 py-2 text-xs bg-white border border-slate-300 rounded-xl text-slate-900 font-medium focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': 'e.g. Take with water; do not skip doses; give breakthrough dose if pain >= 5/10',
            }),
        }


class MedicationStatusUpdateForm(forms.ModelForm):
    class Meta:
        model = MedicationStatement
        fields = ['status', 'discontinuation_reason']
        widgets = {
            'discontinuation_reason': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Reason for changing, holding, or discontinuing medication...'}),
        }
