import uuid
from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .storage import private_patient_photo_storage


class SexChoices(models.TextChoices):
    FEMALE = 'F', _('Female')
    MALE = 'M', _('Male')
    OTHER = 'O', _('Other')
    UNKNOWN = 'U', _('Unknown')


class IdentificationTypeChoices(models.TextChoices):
    NATIONAL_ID = 'NATIONAL_ID', _('National ID (Kenya)')
    PASSPORT = 'PASSPORT', _('Passport')
    BIRTH_CERTIFICATE = 'BIRTH_CERT', _('Birth Certificate')
    ALIEN_ID = 'ALIEN_ID', _('Alien ID')
    MILITARY_ID = 'MILITARY_ID', _('Military ID')
    NONE = 'NONE', _('None / Not Available')


class MaritalStatusChoices(models.TextChoices):
    SINGLE = 'SINGLE', _('Single')
    MARRIED = 'MARRIED', _('Married')
    WIDOWED = 'WIDOWED', _('Widowed')
    DIVORCED = 'DIVORCED', _('Divorced')
    SEPARATED = 'SEPARATED', _('Separated')
    OTHER = 'OTHER', _('Other')


class PatientStatusChoices(models.TextChoices):
    ACTIVE = 'ACTIVE', _('Active')
    INACTIVE = 'INACTIVE', _('Inactive')
    CLOSED = 'CLOSED', _('Closed')
    DISCHARGED = 'DISCHARGED', _('Discharged')
    DECEASED = 'DECEASED', _('Deceased')


class SpecialRemarksChoices(models.TextChoices):
    ALIVE = 'Alive', _('Alive')
    DECEASED = 'Deceased', _('Deceased')
    UNKNOWN = 'Unknown', _('Unknown')


class Patient(models.Model):
    """
    Patient core master identity and demographics.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    hospice_number = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
        help_text=_('Unique Nairobi Hospice Identifier, e.g. NH-2026-0001')
    )
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    photo = models.ImageField(
        upload_to='%Y/%m/',
        storage=private_patient_photo_storage,
        blank=True,
        null=True,
        help_text=_('Patient identification photograph'),
    )

    date_of_birth = models.DateField(null=True, blank=True)
    is_approximate_dob = models.BooleanField(default=False)
    sex = models.CharField(max_length=2, choices=SexChoices.choices, default=SexChoices.FEMALE)

    ip_op_number = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        verbose_name=_('IP/OP Number'),
        help_text=_('Hospital Inpatient / Outpatient File Number (e.g. 081/21)')
    )
    daycare_number = models.CharField(
        max_length=50,
        blank=True,
        db_index=True,
        verbose_name=_('Daycare Number')
    )
    hiv_status = models.CharField(max_length=50, blank=True, verbose_name=_('HIV / RVD Status'))
    referred_by = models.CharField(max_length=150, blank=True, verbose_name=_('Referred By'))

    identification_type = models.CharField(
        max_length=30,
        choices=IdentificationTypeChoices.choices,
        default=IdentificationTypeChoices.NATIONAL_ID
    )
    identification_number = models.CharField(max_length=50, blank=True, db_index=True)

    phone_number = models.CharField(max_length=30, blank=True, db_index=True)
    alternative_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)

    address = models.CharField(max_length=255, blank=True, help_text=_('Estate / Village / Road / House Number'))
    county = models.CharField(max_length=100, default='Nairobi')
    sub_county = models.CharField(max_length=100, blank=True)
    ward = models.CharField(max_length=100, blank=True, help_text=_('Administrative / Electoral Ward'))
    landmark = models.CharField(max_length=255, blank=True, help_text=_('Closest Bus Stop / Matatu Stage / Landmark for home visits'))

    preferred_language = models.CharField(max_length=50, default='English')
    marital_status = models.CharField(
        max_length=20,
        choices=MaritalStatusChoices.choices,
        default=MaritalStatusChoices.MARRIED
    )
    religion = models.CharField(max_length=100, blank=True)
    occupation = models.CharField(max_length=100, blank=True)

    primary_diagnosis = models.CharField(max_length=255, blank=True, help_text=_('Main palliative diagnosis, e.g., Cervical Ca Stage IV, ESRD'))
    allergies = models.TextField(blank=True, help_text=_('Known medication, food, or latex allergies'))
    blood_group = models.CharField(max_length=10, blank=True)

    status = models.CharField(
        max_length=20,
        choices=PatientStatusChoices.choices,
        default=PatientStatusChoices.ACTIVE,
        db_index=True
    )
    registration_date = models.DateField(default=timezone.now)

    special_remarks = models.CharField(
        max_length=50,
        choices=SpecialRemarksChoices.choices,
        blank=True,
        verbose_name=_('Special Remarks'),
        help_text=_('Alive, Deceased, Unknown')
    )
    date_of_death = models.DateField(null=True, blank=True, verbose_name=_('Date of Death'))
    place_of_death = models.CharField(max_length=150, blank=True, help_text=_('Home, Hospital, Hospice Ward, etc.'))
    cause_of_death = models.TextField(blank=True, verbose_name=_('Cause of Death Notes'))

    closure_date = models.DateField(null=True, blank=True, verbose_name=_('Closure Date'))
    file_closed = models.CharField(max_length=50, blank=True, verbose_name=_('File Closed'))

    past_medical_history = models.TextField(blank=True, verbose_name=_('Past Medical History'))
    present_medical_notes = models.TextField(blank=True, verbose_name=_('Present Medical Notes'))
    other_medical_notes = models.TextField(blank=True, verbose_name=_('Other Medical Notes including allergies'))

    discharge_date = models.DateField(null=True, blank=True)
    discharge_reason = models.TextField(blank=True)

    clinical_alerts = models.TextField(blank=True, help_text=_('High-priority flags, e.g. Fall Risk, Severe Pain, High DNR Alert'))
    notes = models.TextField(blank=True)

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='registered_patients'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Patient')
        verbose_name_plural = _('Patients')
        ordering = ['-registration_date', 'last_name', 'first_name']

    def __str__(self):
        op_tag = f" [{self.ip_op_number}]" if self.ip_op_number else ""
        return f"{self.full_name} ({self.hospice_number}{op_tag})"

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join([p for p in parts if p]).strip()

    @property
    def age(self):
        if not self.date_of_birth:
            return None
        today = date.today()
        ref_date = self.date_of_death if (self.status == PatientStatusChoices.DECEASED and self.date_of_death) else today
        return ref_date.year - self.date_of_birth.year - (
            (ref_date.month, ref_date.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def is_active(self):
        return self.status == PatientStatusChoices.ACTIVE


class NextOfKin(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='next_of_kin')
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=100, help_text=_('Spouse, Child, Sibling, Parent, Guardian, etc.'))
    phone_number = models.CharField(max_length=30)
    alternative_phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    age = models.IntegerField(null=True, blank=True, verbose_name=_('Age'))
    gender = models.CharField(max_length=20, blank=True, verbose_name=_('Gender'))
    is_primary = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Next of Kin')
        verbose_name_plural = _('Next of Kin')

    def __str__(self):
        return f"{self.name} ({self.relationship}) - {self.patient.full_name}"


class Caregiver(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='caregivers')
    caregiver_number = models.CharField(max_length=50, blank=True, verbose_name=_('Caregiver Number'))
    name = models.CharField(max_length=150)
    relationship = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    address = models.CharField(max_length=255, blank=True)
    age = models.IntegerField(null=True, blank=True, verbose_name=_('Age'))
    gender = models.CharField(max_length=20, blank=True, verbose_name=_('Gender'))
    availability = models.CharField(max_length=100, blank=True, help_text=_('e.g., Full-time, Nights, Weekends'))
    is_primary = models.BooleanField(default=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Caregiver')
        verbose_name_plural = _('Caregivers')

    def __str__(self):
        return f"{self.name} (Caregiver for {self.patient.full_name})"
