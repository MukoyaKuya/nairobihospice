from django import forms

from apps.accounts.models import RoleChoices, StaffProfile

from .models import (
    Caregiver,
    NextOfKin,
    Patient,
)


class PatientRegistrationForm(forms.ModelForm):
    # Consultation & Registration Fee fields
    consultation_fee = forms.DecimalField(
        max_digits=10,
        decimal_places=2,
        initial=1200.00,
        required=True,
        label="Consultation Fee (KES)",
        widget=forms.NumberInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-xl bg-slate-100 font-mono font-bold text-slate-800 focus:outline-none', 'readonly': 'readonly'})
    )
    payment_method = forms.ChoiceField(
        choices=[
            ('M-PESA (Paybill 981234)', 'M-PESA (Paybill 981234)'),
            ('Bank Transfer (EFT / RTGS)', 'Bank Transfer (EFT / RTGS)'),
            ('Cash', 'Cash'),
            ('Cheque', 'Cheque'),
            ('DHA / SHA / Insurance', 'DHA / SHA / Insurance'),
        ],
        initial='M-PESA (Paybill 981234)',
        required=True,
        label="Payment Method / Channel",
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-xl bg-white focus:ring-2 focus:ring-[#002D62] focus:outline-none font-semibold text-slate-900'})
    )
    payment_reference = forms.CharField(
        max_length=100,
        required=True,
        label="M-PESA Code or Bank Transaction ID",
        widget=forms.TextInput(attrs={'placeholder': 'e.g. QHK8923KLM or FT2408269001', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-xl bg-white focus:ring-2 focus:ring-[#002D62] focus:outline-none font-mono font-bold uppercase'})
    )

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

        # Registration Consultation Payment validation
        payment_ref = (cleaned_data.get('payment_reference') or '').strip()
        if not payment_ref:
            self.add_error('payment_reference', 'A valid M-PESA Confirmation Code or Bank Transaction ID is required before completing registration.')
        fee = cleaned_data.get('consultation_fee')
        if fee is not None and fee < 0:
            self.add_error('consultation_fee', 'Consultation fee cannot be negative.')

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
    nok_age = forms.IntegerField(label="Next of Kin Age", required=False)
    nok_gender = forms.CharField(label="Next of Kin Gender", required=False)
    nok_county = forms.CharField(label="Next of Kin County", required=False, initial="Nairobi")
    nok_sub_county = forms.CharField(label="Next of Kin Sub-County", required=False)
    nok_ward = forms.CharField(label="Next of Kin Ward", required=False)
    nok_nearest_stage = forms.CharField(label="Next of Kin Nearest Bus Stop / Stage", required=False)
    nok_address = forms.CharField(label="Next of Kin Residence / Estate", required=False)

    # Caregiver fields
    caregiver_name = forms.CharField(label="Primary Caregiver Name", required=False)
    caregiver_relationship = forms.CharField(label="Caregiver Relationship", required=False, initial="Family Caregiver")
    caregiver_phone = forms.CharField(label="Caregiver Phone", required=False)
    caregiver_age = forms.IntegerField(label="Caregiver Age", required=False)
    caregiver_gender = forms.CharField(label="Caregiver Gender", required=False)
    caregiver_county = forms.CharField(label="Caregiver County", required=False, initial="Nairobi")
    caregiver_sub_county = forms.CharField(label="Caregiver Sub-County", required=False)
    caregiver_ward = forms.CharField(label="Caregiver Ward", required=False)
    caregiver_nearest_stage = forms.CharField(label="Caregiver Nearest Bus Stop / Stage", required=False)
    caregiver_address = forms.CharField(label="Caregiver Residence / Estate", required=False)
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


class PatientContactUpdateFormMixin(forms.Form):
    # Next of Kin fields
    nok_name = forms.CharField(label="Next of Kin Full Name", required=False)
    nok_relationship = forms.CharField(label="Relationship to Patient", required=False)
    nok_phone = forms.CharField(label="Next of Kin Phone", required=False)
    nok_age = forms.IntegerField(label="Next of Kin Age", required=False)
    nok_gender = forms.CharField(label="Next of Kin Gender", required=False)
    nok_county = forms.CharField(label="Next of Kin County", required=False)
    nok_sub_county = forms.CharField(label="Next of Kin Sub-County", required=False)
    nok_ward = forms.CharField(label="Next of Kin Ward", required=False)
    nok_nearest_stage = forms.CharField(label="Next of Kin Nearest Bus Stop / Stage", required=False)
    nok_address = forms.CharField(label="Next of Kin Residence / Estate", required=False)

    # Caregiver fields
    caregiver_name = forms.CharField(label="Primary Caregiver Name", required=False)
    caregiver_relationship = forms.CharField(label="Caregiver Relationship", required=False)
    caregiver_phone = forms.CharField(label="Caregiver Phone", required=False)
    caregiver_age = forms.IntegerField(label="Caregiver Age", required=False)
    caregiver_gender = forms.CharField(label="Caregiver Gender", required=False)
    caregiver_county = forms.CharField(label="Caregiver County", required=False)
    caregiver_sub_county = forms.CharField(label="Caregiver Sub-County", required=False)
    caregiver_ward = forms.CharField(label="Caregiver Ward", required=False)
    caregiver_nearest_stage = forms.CharField(label="Caregiver Nearest Bus Stop / Stage", required=False)
    caregiver_address = forms.CharField(label="Caregiver Residence / Estate", required=False)
    caregiver_notes = forms.CharField(label="Caregiver Notes", required=False, widget=forms.Textarea(attrs={'rows': 2}))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            nok = self.instance.next_of_kin.first()
            if nok:
                self.fields['nok_name'].initial = nok.name
                self.fields['nok_relationship'].initial = nok.relationship
                self.fields['nok_phone'].initial = nok.phone_number
                self.fields['nok_age'].initial = nok.age
                self.fields['nok_gender'].initial = nok.gender
                self.fields['nok_county'].initial = nok.county or 'Nairobi'
                self.fields['nok_sub_county'].initial = nok.sub_county
                self.fields['nok_ward'].initial = nok.ward
                self.fields['nok_nearest_stage'].initial = nok.nearest_stage
                self.fields['nok_address'].initial = nok.address

            cg = self.instance.caregivers.first()
            if cg:
                self.fields['caregiver_name'].initial = cg.name
                self.fields['caregiver_relationship'].initial = cg.relationship
                self.fields['caregiver_phone'].initial = cg.phone_number
                self.fields['caregiver_age'].initial = cg.age
                self.fields['caregiver_gender'].initial = cg.gender
                self.fields['caregiver_county'].initial = cg.county or 'Nairobi'
                self.fields['caregiver_sub_county'].initial = cg.sub_county
                self.fields['caregiver_ward'].initial = cg.ward
                self.fields['caregiver_nearest_stage'].initial = cg.nearest_stage
                self.fields['caregiver_address'].initial = cg.address
                self.fields['caregiver_notes'].initial = cg.notes

    def save(self, commit=True):
        patient = super().save(commit=commit)
        if commit:
            self.save_contacts(patient)
        return patient

    def save_contacts(self, patient):
        cd = self.cleaned_data
        nok_name = (cd.get('nok_name') or '').strip()
        if nok_name:
            nok = patient.next_of_kin.first()
            if not nok:
                nok = NextOfKin(patient=patient, is_primary=True)
            nok.name = nok_name
            nok.relationship = cd.get('nok_relationship') or 'Next of Kin'
            nok.phone_number = cd.get('nok_phone') or ''
            nok.age = cd.get('nok_age')
            nok.gender = cd.get('nok_gender') or ''
            nok.county = cd.get('nok_county') or 'Nairobi'
            nok.sub_county = cd.get('nok_sub_county') or ''
            nok.ward = cd.get('nok_ward') or ''
            nok.nearest_stage = cd.get('nok_nearest_stage') or ''
            nok.address = cd.get('nok_address') or ''
            nok.save()

        cg_name = (cd.get('caregiver_name') or '').strip()
        if cg_name:
            cg = patient.caregivers.first()
            if not cg:
                cg = Caregiver(patient=patient, is_primary=True)
            cg.name = cg_name
            cg.relationship = cd.get('caregiver_relationship') or 'Caregiver'
            cg.phone_number = cd.get('caregiver_phone') or ''
            cg.age = cd.get('caregiver_age')
            cg.gender = cd.get('caregiver_gender') or ''
            cg.county = cd.get('caregiver_county') or 'Nairobi'
            cg.sub_county = cd.get('caregiver_sub_county') or ''
            cg.ward = cd.get('caregiver_ward') or ''
            cg.nearest_stage = cd.get('caregiver_nearest_stage') or ''
            cg.address = cd.get('caregiver_address') or ''
            cg.notes = cd.get('caregiver_notes') or ''
            cg.save()


class PatientUpdateForm(PatientContactUpdateFormMixin, forms.ModelForm):
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


class ReceptionistPatientUpdateForm(PatientContactUpdateFormMixin, forms.ModelForm):
    """
    Restricted demographic and contact update form for front-desk receptionists.
    Excludes all clinical diagnoses, HIV status, allergies, alerts, and clinical notes.
    Allows editing next of kin and caregiver details.
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
