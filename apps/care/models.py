import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.accounts.models import StaffProfile
from apps.patients.models import Patient


class EpisodeStatusChoices(models.TextChoices):
    ACTIVE = 'ACTIVE', _('Active Palliative Episode')
    INACTIVE = 'INACTIVE', _('Inactive / Suspended')
    DISCHARGED = 'DISCHARGED', _('Discharged')
    DECEASED = 'DECEASED', _('Deceased')
    TRANSFERRED = 'TRANSFERRED', _('Transferred to Other Hospice/Hospital')


class CareTeamRoleChoices(models.TextChoices):
    PRIMARY_DOCTOR = 'PRIMARY_DOCTOR', _('Primary Palliative Doctor')
    PRIMARY_NURSE = 'PRIMARY_NURSE', _('Primary Palliative Nurse')
    CLINICAL_OFFICER = 'CLINICAL_OFFICER', _('Clinical Officer')
    SOCIAL_WORKER = 'SOCIAL_WORKER', _('Social Worker')
    COUNSELLOR = 'COUNSELLOR', _('Psychological Counsellor')
    PHARMACIST = 'PHARMACIST', _('Pharmacist')
    PHYSIOTHERAPIST = 'PHYSIOTHERAPIST', _('Physiotherapist')
    NUTRITIONIST = 'NUTRITIONIST', _('Nutritionist')
    SPIRITUAL_COUNSELLOR = 'SPIRITUAL_COUNSELLOR', _('Spiritual / Pastoral Leader')
    COMMUNITY_WORKER = 'COMMUNITY_WORKER', _('Community Health Promoter')
    CARE_COORDINATOR = 'CARE_COORDINATOR', _('Care Coordinator')


class CarePlanStatusChoices(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft')
    ACTIVE = 'ACTIVE', _('Active Care Plan')
    UNDER_REVIEW = 'UNDER_REVIEW', _('Under Multidisciplinary Review')
    COMPLETED = 'COMPLETED', _('Completed')
    CANCELLED = 'CANCELLED', _('Discontinued / Cancelled')


class NeedCategoryChoices(models.TextChoices):
    PHYSICAL = 'PHYSICAL', _('Physical / Symptom Burden')
    PSYCHOSOCIAL = 'PSYCHOSOCIAL', _('Psychosocial & Family')
    SPIRITUAL = 'SPIRITUAL', _('Spiritual & Existential')
    PRACTICAL = 'PRACTICAL', _('Practical & Financial')
    ETHICAL = 'ETHICAL', _('Advance Care Planning & Ethical')


class EpisodeOfCare(models.Model):
    """
    Longitudinal care period representing continuous palliative management.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='episodes')
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    reason_for_admission = models.TextField(blank=True)
    status = models.CharField(
        max_length=20,
        choices=EpisodeStatusChoices.choices,
        default=EpisodeStatusChoices.ACTIVE,
        db_index=True
    )
    discharge_summary = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='initiated_episodes'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Episode of Care')
        verbose_name_plural = _('Episodes of Care')
        ordering = ['-start_date']
        indexes = [models.Index(fields=['patient', 'status'], name='episode_patient_status_idx')]

    def __str__(self):
        return f"Episode for {self.patient.full_name} ({self.start_date.strftime('%b %Y')})"

    @property
    def is_active(self):
        return self.status == EpisodeStatusChoices.ACTIVE


class CareTeamMember(models.Model):
    """
    Multidisciplinary team assigned to a patient's palliative episode.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    episode = models.ForeignKey(EpisodeOfCare, on_delete=models.CASCADE, related_name='team_members')
    staff_member = models.ForeignKey(StaffProfile, on_delete=models.CASCADE, related_name='care_assignments')
    role = models.CharField(max_length=30, choices=CareTeamRoleChoices.choices)
    is_primary = models.BooleanField(default=False)
    start_date = models.DateField(default=timezone.now)
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Care Team Member')
        verbose_name_plural = _('Care Team Members')
        ordering = ['role', 'staff_member__user__first_name']
        indexes = [models.Index(fields=['episode', 'staff_member'], name='team_episode_staff_idx')]

    def __str__(self):
        return f"{self.staff_member.user.display_name} ({self.get_role_display()})"


class CarePlan(models.Model):
    """
    Coordinated Multidisciplinary Palliative Care Plan.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='care_plans')
    episode = models.ForeignKey(EpisodeOfCare, on_delete=models.SET_NULL, null=True, blank=True, related_name='care_plans')
    title = models.CharField(max_length=200, default='Individualized Palliative Care Plan')
    primary_diagnosis = models.CharField(max_length=255, blank=True)
    overall_goals = models.TextField(help_text=_('Patient-centred priorities and overarching goals of care'))
    resuscitation_preference = models.CharField(
        max_length=100,
        default='Allow Natural Death (AND) / Comfort Measures',
        help_text=_('Advance care directive preference')
    )
    status = models.CharField(
        max_length=20,
        choices=CarePlanStatusChoices.choices,
        default=CarePlanStatusChoices.ACTIVE,
        db_index=True
    )
    review_date = models.DateField(null=True, blank=True, help_text=_('Next multidisciplinary review date'))
    last_reviewed_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_care_plans'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Care Plan')
        verbose_name_plural = _('Care Plans')
        ordering = ['-created_at']
        indexes = [models.Index(fields=['patient', 'status'], name='careplan_patient_status_idx')]

    def __str__(self):
        return f"Care Plan: {self.patient.full_name} ({self.get_status_display()})"


class CarePlanNeed(models.Model):
    """
    Structured problem, goal, and intervention component in a Care Plan.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    care_plan = models.ForeignKey(CarePlan, on_delete=models.CASCADE, related_name='needs')
    category = models.CharField(
        max_length=20,
        choices=NeedCategoryChoices.choices,
        default=NeedCategoryChoices.PHYSICAL
    )
    problem_description = models.TextField(help_text=_('Identified issue or symptom'))
    goal = models.TextField(help_text=_('Desired measurable or subjective outcome'))
    interventions = models.TextField(help_text=_('Action steps and clinical interventions'))
    responsible_discipline = models.CharField(max_length=100, default='Nursing & Medical')
    target_date = models.DateField(null=True, blank=True)
    is_resolved = models.BooleanField(default=False)
    outcome_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Care Plan Need / Goal')
        verbose_name_plural = _('Care Plan Needs & Goals')
        ordering = ['is_resolved', 'category', 'created_at']

    def __str__(self):
        return f"[{self.get_category_display()}] {self.problem_description[:50]}"


class ClinicalAdvice(models.Model):
    """
    Standardized clinical procedure guidelines and patient care instructions
    from the Hospice knowledge base.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    procedure = models.CharField(max_length=150, db_index=True)
    heading = models.CharField(max_length=200, blank=True)
    advice_text = models.TextField()
    category = models.CharField(max_length=100, default='Procedural Care & Patient Advice')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Clinical Advice Guide')
        verbose_name_plural = _('Clinical Advice Guides')
        ordering = ['procedure']

    def __str__(self):
        return f"{self.procedure} - {self.heading or 'Clinical Advice'}"
