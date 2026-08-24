import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils.translation import gettext_lazy as _


class RoleChoices(models.TextChoices):
    DOCTOR = 'DOCTOR', _('Palliative Care Doctor')
    NURSE = 'NURSE', _('Palliative Care Nurse')
    CLINICAL_OFFICER = 'CLINICAL_OFFICER', _('Clinical Officer')
    SOCIAL_WORKER = 'SOCIAL_WORKER', _('Social Worker')
    COUNSELLOR = 'COUNSELLOR', _('Counsellor / Psychologist')
    PHARMACIST = 'PHARMACIST', _('Pharmacist / Medication Staff')
    RECEPTIONIST = 'RECEPTIONIST', _('Reception / Registration Staff')
    MANAGER = 'MANAGER', _('Program / Operations Manager')
    ADMINISTRATOR = 'ADMINISTRATOR', _('System Administrator')


class User(AbstractUser):
    """
    Custom user model for Nairobi Hospice PCMS.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(_('email address'), unique=True)
    phone_number = models.CharField(max_length=20, blank=True)
    is_mfa_enabled = models.BooleanField(default=False)
    mfa_secret = models.CharField(max_length=64, blank=True, editable=False)
    mfa_recovery_codes = models.JSONField(default=list, blank=True, editable=False)
    mfa_enrolled_at = models.DateTimeField(null=True, blank=True, editable=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']

    class Meta:
        verbose_name = _('User')
        verbose_name_plural = _('Users')
        ordering = ['first_name', 'last_name']

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.email})"

    @property
    def display_name(self):
        full = self.get_full_name().strip()
        return full if full else self.username

    @property
    def profile(self):
        return getattr(self, 'staff_profile', None)

    @property
    def role(self):
        if hasattr(self, 'staff_profile') and self.staff_profile:
            return self.staff_profile.role
        if self.is_superuser:
            return RoleChoices.ADMINISTRATOR
        return None

    @property
    def is_clinical(self):
        return self.role in [
            RoleChoices.DOCTOR,
            RoleChoices.NURSE,
            RoleChoices.CLINICAL_OFFICER,
            RoleChoices.SOCIAL_WORKER,
            RoleChoices.COUNSELLOR,
            RoleChoices.PHARMACIST,
        ]

    @property
    def is_doctor(self):
        return self.role == RoleChoices.DOCTOR

    @property
    def is_clinical_officer(self):
        return self.role == RoleChoices.CLINICAL_OFFICER

    @property
    def is_nurse(self):
        return self.role == RoleChoices.NURSE

    @property
    def is_social_worker(self):
        return self.role == RoleChoices.SOCIAL_WORKER

    @property
    def is_counsellor(self):
        return self.role == RoleChoices.COUNSELLOR

    @property
    def is_receptionist(self):
        return self.role == RoleChoices.RECEPTIONIST

    @property
    def is_pharmacist(self):
        return self.role == RoleChoices.PHARMACIST

    @property
    def is_administrator(self):
        return self.role == RoleChoices.ADMINISTRATOR or self.is_superuser

    @property
    def is_manager(self):
        # Deliberately excludes is_staff: Django-admin access must not grant
        # application-level management powers. Roles are the source of truth.
        return self.role in [RoleChoices.MANAGER, RoleChoices.ADMINISTRATOR] or self.is_superuser


class StaffProfile(models.Model):
    """
    Staff Profile linking identity, role, qualifications, and department.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='staff_profile')
    role = models.CharField(max_length=30, choices=RoleChoices.choices, default=RoleChoices.NURSE)
    license_number = models.CharField(max_length=50, blank=True, help_text=_('Professional registration/license number'))
    department = models.CharField(max_length=100, default='Palliative Care Unit')
    qualifications = models.CharField(max_length=255, blank=True)
    profile_picture = models.ImageField(upload_to='staff_avatars/', blank=True, null=True, help_text=_('Staff profile photograph'))
    is_active_staff = models.BooleanField(default=True)
    can_conduct_home_visits = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Staff Profile')
        verbose_name_plural = _('Staff Profiles')
        ordering = ['role', 'user__first_name']

    def __str__(self):
        return f"{self.user.display_name} - {self.get_role_display()}"
