from django import forms

from .models import Assessment, AssessmentAmendment


class AssessmentForm(forms.ModelForm):
    # Optional structured fields for direct clinical entry
    pain_site = forms.CharField(
        label="Pain Anatomical Site(s)",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 focus:bg-white focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
            'placeholder': 'e.g., Lumbar spine radiating to right hip'
        })
    )
    pain_character = forms.CharField(
        label="Pain Character / Type",
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 focus:bg-white focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
            'placeholder': 'e.g., Burning / Sharp / Aching / Colicky'
        })
    )
    psychosocial_needs = forms.CharField(
        label="Psychosocial Concerns",
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 focus:bg-white focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
            'placeholder': 'Family acceptance, emotional distress, child caregiver concerns...'
        })
    )
    spiritual_concerns = forms.CharField(
        label="Spiritual / Pastoral Concerns",
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2,
            'class': 'w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 focus:bg-white focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
            'placeholder': 'Peace of mind, faith support, end-of-life wishes, existential concerns...'
        })
    )

    class Meta:
        model = Assessment
        fields = ['assessment_type', 'assessment_date', 'pain_score', 'pps_score', 'ecog_score', 'clinical_summary', 'next_review_date']
        widgets = {
            'assessment_type': forms.Select(attrs={
                'class': 'w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg text-slate-900 font-semibold focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition'
            }),
            'assessment_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg text-slate-900 font-medium focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition'
            }),
            'next_review_date': forms.DateInput(attrs={
                'type': 'date',
                'class': 'w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg text-slate-900 font-medium focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition'
            }),
            'pain_score': forms.NumberInput(attrs={
                'min': 0,
                'max': 10,
                'class': 'w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg text-slate-900 font-bold focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': '0 - 10'
            }),
            'pps_score': forms.NumberInput(attrs={
                'min': 10,
                'max': 100,
                'step': 10,
                'class': 'w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg text-slate-900 font-bold focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': '10 - 100%'
            }),
            'ecog_score': forms.NumberInput(attrs={
                'min': 0,
                'max': 4,
                'class': 'w-full px-3 py-2 text-xs bg-white border border-slate-300 rounded-lg text-slate-900 font-bold focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': '0 - 4'
            }),
            'clinical_summary': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 focus:bg-white focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': 'Holistic findings, physical examination, assessment synthesis, and agreed management plan...'
            }),
        }


class AssessmentAmendmentForm(forms.ModelForm):
    class Meta:
        model = AssessmentAmendment
        fields = ['reason_for_amendment', 'amended_notes']
        widgets = {
            'reason_for_amendment': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 focus:bg-white focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': 'Why is this clinical record being amended?'
            }),
            'amended_notes': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full px-3 py-2 text-xs bg-slate-50 border border-slate-300 rounded-lg text-slate-900 focus:bg-white focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none transition',
                'placeholder': 'Updated clinical summary note...'
            }),
        }
