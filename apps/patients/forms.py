from django import forms

from .models import (
    Caregiver,
    NextOfKin,
    Patient,
)


class PatientRegistrationForm(forms.ModelForm):
    # Additional Next of Kin fields
    nok_name = forms.CharField(label="Next of Kin Full Name", required=False)
    nok_relationship = forms.CharField(label="Relationship to Patient", required=False, initial="Spouse")
    nok_phone = forms.CharField(label="Next of Kin Phone", required=False)

    # Caregiver fields
    caregiver_name = forms.CharField(label="Primary Caregiver Name", required=False)
    caregiver_relationship = forms.CharField(label="Caregiver Relationship", required=False, initial="Family Caregiver")
    caregiver_phone = forms.CharField(label="Caregiver Phone", required=False)

    class Meta:
        model = Patient
        fields = [
            'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'is_approximate_dob', 'sex',
            'identification_type', 'identification_number',
            'phone_number', 'alternative_phone', 'email',
            'address', 'county', 'sub_county', 'ward', 'landmark',
            'preferred_language', 'marital_status', 'religion', 'occupation',
            'primary_diagnosis', 'allergies', 'blood_group', 'clinical_alerts', 'notes'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'allergies': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g., Penicillin (rash), Tramadol (severe nausea)'}),
            'clinical_alerts': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g., High fall risk, Difficulty swallowing, DNR discussion requested'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class PatientUpdateForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            'first_name', 'middle_name', 'last_name',
            'date_of_birth', 'is_approximate_dob', 'sex',
            'identification_type', 'identification_number',
            'phone_number', 'alternative_phone', 'email',
            'address', 'county', 'sub_county', 'ward', 'landmark',
            'preferred_language', 'marital_status', 'religion', 'occupation',
            'primary_diagnosis', 'allergies', 'blood_group', 'clinical_alerts', 'status', 'notes'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'clinical_alerts': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }


class NextOfKinForm(forms.ModelForm):
    class Meta:
        model = NextOfKin
        fields = ['name', 'relationship', 'phone_number', 'alternative_phone', 'email', 'address', 'is_primary']


class CaregiverForm(forms.ModelForm):
    class Meta:
        model = Caregiver
        fields = ['name', 'relationship', 'phone_number', 'email', 'address', 'availability', 'notes', 'is_primary']
