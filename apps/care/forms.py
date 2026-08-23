from django import forms

from apps.accounts.models import StaffProfile
from apps.patients.models import Patient

from .models import (
    CarePlan,
    CarePlanNeed,
    CareTeamMember,
    EpisodeOfCare,
)


class EpisodeOfCareForm(forms.ModelForm):
    class Meta:
        model = EpisodeOfCare
        fields = ['start_date', 'reason_for_admission', 'status', 'discharge_summary']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'reason_for_admission': forms.Textarea(attrs={'rows': 3}),
            'discharge_summary': forms.Textarea(attrs={'rows': 3}),
        }


class CareTeamMemberForm(forms.ModelForm):
    staff_member = forms.ModelChoiceField(
        queryset=StaffProfile.objects.filter(is_active_staff=True).select_related('user'),
        label="Staff Member"
    )

    class Meta:
        model = CareTeamMember
        fields = ['staff_member', 'role', 'is_primary', 'start_date', 'notes']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }


class CarePlanForm(forms.ModelForm):
    patient = forms.ModelChoiceField(
        queryset=Patient.objects.filter(status='ACTIVE').order_by('first_name', 'last_name'),
        required=False,
        label="Patient"
    )

    class Meta:
        model = CarePlan
        fields = ['patient', 'title', 'primary_diagnosis', 'overall_goals', 'resuscitation_preference', 'review_date', 'status']
        widgets = {
            'title': forms.TextInput(attrs={'placeholder': 'e.g. Individualized Palliative Care Plan'}),
            'primary_diagnosis': forms.TextInput(attrs={'placeholder': 'e.g. Stage IV Breast Carcinoma with bone metastasis'}),
            'overall_goals': forms.Textarea(attrs={'rows': 3, 'placeholder': 'e.g., Maintain comfort, relieve breakthrough pain, support family with home nursing guidance'}),
            'resuscitation_preference': forms.TextInput(attrs={'placeholder': 'Allow Natural Death (AND) / Comfort Measures'}),
            'review_date': forms.DateInput(attrs={'type': 'date'}),
            'status': forms.Select(),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['status'].required = False
        if not self.initial.get('status'):
            self.fields['status'].initial = 'ACTIVE'
        self.fields['resuscitation_preference'].required = False
        if not self.initial.get('resuscitation_preference'):
            self.fields['resuscitation_preference'].initial = 'Allow Natural Death (AND) / Comfort Measures'
        self.fields['title'].required = True
        if not self.initial.get('title'):
            self.fields['title'].initial = 'Individualized Palliative Care Plan'
        self.fields['primary_diagnosis'].required = False
        self.fields['overall_goals'].required = True


class CarePlanNeedForm(forms.ModelForm):
    class Meta:
        model = CarePlanNeed
        fields = ['category', 'problem_description', 'goal', 'interventions', 'responsible_discipline', 'target_date']
        widgets = {
            'problem_description': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g., Uncontrolled continuous nociceptive pain in lower back 8/10'}),
            'goal': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g., Reduce pain score to <= 3/10 without excessive drowsiness'}),
            'interventions': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g., Titrate oral Morphine solution 10mg q4h, Laxatives, repositioning education'}),
            'target_date': forms.DateInput(attrs={'type': 'date'}),
        }
