from django import forms

from apps.accounts.models import RoleChoices, StaffProfile

from .models import (
    Caregiver,
    NextOfKin,
    Patient,
)


class PatientRegistrationForm(forms.ModelForm):
    # Mandatory Primary Care Team
    primary_nurse = forms.ModelChoiceField(
        queryset=None,
        label="Primary Assigned Nurse",
        required=True,
        empty_label="-- Select Primary Nurse --",
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-xl bg-white focus:ring-2 focus:ring-[#002D62] focus:outline-none font-semibold text-slate-900'})
    )
    primary_doctor = forms.ModelChoiceField(
        queryset=None,
        label="Primary Assigned Doctor / CO",
        required=True,
        empty_label="-- Select Primary Doctor --",
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-xl bg-white focus:ring-2 focus:ring-[#002D62] focus:outline-none font-semibold text-slate-900'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['primary_nurse'].queryset = StaffProfile.objects.filter(
            role=RoleChoices.NURSE, is_active_staff=True
        ).select_related('user')
        self.fields['primary_doctor'].queryset = StaffProfile.objects.filter(
            role__in=[RoleChoices.DOCTOR, RoleChoices.CLINICAL_OFFICER], is_active_staff=True
        ).select_related('user')

        if not self.is_bound and not self.initial.get('ip_op_number'):
            from .services import generate_next_ip_op_number
            self.initial['ip_op_number'] = generate_next_ip_op_number()

    def clean(self):
        cleaned_data = super().clean()
        nurses_exist = StaffProfile.objects.filter(role=RoleChoices.NURSE, is_active_staff=True).exists()
        doctors_exist = StaffProfile.objects.filter(role__in=[RoleChoices.DOCTOR, RoleChoices.CLINICAL_OFFICER], is_active_staff=True).exists()

        if nurses_exist and not cleaned_data.get('primary_nurse'):
            self.add_error('primary_nurse', 'A primary palliative nurse must be assigned upon patient registration.')
        if doctors_exist and not cleaned_data.get('primary_doctor'):
            self.add_error('primary_doctor', 'A primary doctor or clinical officer must be assigned upon patient registration.')

        # Duplicate registration guard
        first_name = (cleaned_data.get('first_name') or '').strip()
        last_name = (cleaned_data.get('last_name') or '').strip()
        id_number = (cleaned_data.get('identification_number') or '').strip()
        ip_op_number = (cleaned_data.get('ip_op_number') or '').strip()
        phone_number = (cleaned_data.get('phone_number') or '').strip()
        date_of_birth = cleaned_data.get('date_of_birth')
        exclude_pk = self.instance.pk if (self.instance and self.instance.pk) else None

        if id_number:
            existing = Patient.objects.filter(identification_number__iexact=id_number)
            if exclude_pk:
                existing = existing.exclude(pk=exclude_pk)
            existing = existing.first()
            if existing:
                self.add_error('identification_number', f"A patient with Identification Number '{id_number}' is already registered: {existing.full_name} ({existing.hospice_number}).")

        if ip_op_number:
            existing = Patient.objects.filter(ip_op_number__iexact=ip_op_number)
            if exclude_pk:
                existing = existing.exclude(pk=exclude_pk)
            existing = existing.first()
            if existing:
                self.add_error('ip_op_number', f"A patient with Hospital IP/OP Number '{ip_op_number}' is already registered: {existing.full_name} ({existing.hospice_number}).")

        if first_name and last_name:
            if phone_number:
                existing = Patient.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name, phone_number__iexact=phone_number)
                if exclude_pk:
                    existing = existing.exclude(pk=exclude_pk)
                existing = existing.first()
                if existing:
                    raise forms.ValidationError(f"Duplicate registration detected: '{first_name} {last_name}' with phone '{phone_number}' is already registered under Hospice ID {existing.hospice_number}.")
            if date_of_birth:
                existing = Patient.objects.filter(first_name__iexact=first_name, last_name__iexact=last_name, date_of_birth=date_of_birth)
                if exclude_pk:
                    existing = existing.exclude(pk=exclude_pk)
                existing = existing.first()
                if existing:
                    raise forms.ValidationError(f"Duplicate registration detected: '{first_name} {last_name}' born {date_of_birth} is already registered under Hospice ID {existing.hospice_number}.")

        return cleaned_data
    # Additional Next of Kin fields
    nok_name = forms.CharField(label="Next of Kin Full Name", required=False)
    nok_relationship = forms.CharField(label="Relationship to Patient", required=False, initial="Spouse")
    nok_phone = forms.CharField(label="Next of Kin Phone", required=False)
    nok_address = forms.CharField(label="Next of Kin Residence", required=False)
    nok_age = forms.IntegerField(label="Next of Kin Age", required=False)
    nok_gender = forms.CharField(label="Next of Kin Gender", required=False)

    # Caregiver fields
    caregiver_name = forms.CharField(label="Primary Caregiver Name", required=False)
    caregiver_relationship = forms.CharField(label="Caregiver Relationship", required=False, initial="Family Caregiver")
    caregiver_phone = forms.CharField(label="Caregiver Phone", required=False)
    caregiver_address = forms.CharField(label="Caregiver Residence", required=False)
    caregiver_age = forms.IntegerField(label="Caregiver Age", required=False)
    caregiver_gender = forms.CharField(label="Caregiver Gender", required=False)
    caregiver_notes = forms.CharField(label="Caregiver Notes", required=False, widget=forms.Textarea(attrs={'rows': 2}))

    # Detailed Medical History Fields
    chief_complaint = forms.CharField(label="Chief Complaint / Presenting Symptoms", required=False, widget=forms.Textarea(attrs={'rows': 2}))
    past_medical_history = forms.CharField(label="Past Medical & Surgical History", required=False, widget=forms.Textarea(attrs={'rows': 2}))
    family_history = forms.CharField(label="Family Medical History", required=False, widget=forms.Textarea(attrs={'rows': 2}))
    drug_history = forms.CharField(label="Past & Current Drug History", required=False, widget=forms.Textarea(attrs={'rows': 2}))

    class Meta:
        model = Patient
        fields = [
            'first_name', 'middle_name', 'last_name',
            'ip_op_number', 'daycare_number', 'hiv_status', 'referred_by',
            'date_of_birth', 'is_approximate_dob', 'sex',
            'identification_type', 'identification_number',
            'phone_number', 'alternative_phone', 'email',
            'address', 'county', 'sub_county', 'ward', 'landmark',
            'preferred_language', 'marital_status', 'religion', 'occupation',
            'primary_diagnosis', 'allergies', 'blood_group', 'clinical_alerts',
            'status', 'special_remarks', 'date_of_death', 'cause_of_death',
            'closure_date', 'file_closed', 'past_medical_history', 'present_medical_notes', 'other_medical_notes', 'notes'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'date_of_death': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'closure_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-input'}),
            'allergies': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g., Penicillin (rash), Tramadol (severe nausea)'}),
            'clinical_alerts': forms.Textarea(attrs={'rows': 2, 'placeholder': 'e.g., High fall risk, Difficulty swallowing, DNR discussion requested'}),
            'past_medical_history': forms.Textarea(attrs={'rows': 2}),
            'present_medical_notes': forms.Textarea(attrs={'rows': 2}),
            'other_medical_notes': forms.Textarea(attrs={'rows': 2}),
            'cause_of_death': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            from apps.documents.malware import scan_uploaded_file
            scan_uploaded_file(photo)
        return photo


class PatientUpdateForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = [
            'first_name', 'middle_name', 'last_name',
            'ip_op_number', 'daycare_number', 'hiv_status', 'referred_by',
            'date_of_birth', 'is_approximate_dob', 'sex',
            'identification_type', 'identification_number',
            'phone_number', 'alternative_phone', 'email',
            'address', 'county', 'sub_county', 'ward', 'landmark',
            'preferred_language', 'marital_status', 'religion', 'occupation',
            'primary_diagnosis', 'allergies', 'blood_group', 'clinical_alerts',
            'status', 'special_remarks', 'date_of_death', 'cause_of_death',
            'closure_date', 'file_closed', 'past_medical_history', 'present_medical_notes', 'other_medical_notes', 'notes'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'date_of_death': forms.DateInput(attrs={'type': 'date'}),
            'closure_date': forms.DateInput(attrs={'type': 'date'}),
            'allergies': forms.Textarea(attrs={'rows': 2}),
            'clinical_alerts': forms.Textarea(attrs={'rows': 2}),
            'past_medical_history': forms.Textarea(attrs={'rows': 2}),
            'present_medical_notes': forms.Textarea(attrs={'rows': 2}),
            'other_medical_notes': forms.Textarea(attrs={'rows': 2}),
            'cause_of_death': forms.Textarea(attrs={'rows': 2}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean_photo(self):
        photo = self.cleaned_data.get('photo')
        if photo:
            from apps.documents.malware import scan_uploaded_file
            scan_uploaded_file(photo)
        return photo


class ReceptionistPatientUpdateForm(forms.ModelForm):
    """
    Restricted demographic and contact update form for front-desk receptionists.
    Excludes all clinical diagnoses, HIV status, allergies, alerts, and clinical notes.
    """
    class Meta:
        model = Patient
        fields = [
            'first_name', 'middle_name', 'last_name',
            'ip_op_number', 'daycare_number', 'referred_by',
            'date_of_birth', 'is_approximate_dob', 'sex',
            'identification_type', 'identification_number',
            'phone_number', 'alternative_phone', 'email',
            'address', 'county', 'sub_county', 'ward', 'landmark',
            'preferred_language', 'marital_status', 'religion', 'occupation',
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
        }


class NextOfKinForm(forms.ModelForm):
    class Meta:
        model = NextOfKin
        fields = ['name', 'relationship', 'phone_number', 'alternative_phone', 'email', 'address', 'is_primary']


class CaregiverForm(forms.ModelForm):
    class Meta:
        model = Caregiver
        fields = ['name', 'relationship', 'phone_number', 'email', 'address', 'availability', 'notes', 'is_primary']
