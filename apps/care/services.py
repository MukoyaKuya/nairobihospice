from datetime import date

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import StaffProfile
from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.patients.models import Patient

from .models import (
    CarePlan,
    CarePlanNeed,
    CarePlanStatusChoices,
    CareTeamMember,
    CareTeamRoleChoices,
    EpisodeOfCare,
    EpisodeStatusChoices,
    NeedCategoryChoices,
)


@transaction.atomic
def start_episode_of_care(*, patient: Patient, reason_for_admission: str = '', start_date: date = None, user=None) -> EpisodeOfCare:
    episode = EpisodeOfCare.objects.create(
        patient=patient,
        start_date=start_date or timezone.now().date(),
        reason_for_admission=reason_for_admission,
        status=EpisodeStatusChoices.ACTIVE,
        created_by=user,
    )
    log_audit_event(
        action=AuditAction.CREATE,
        resource_type='EpisodeOfCare',
        resource_id=str(episode.id),
        summary=f"Opened active palliative care episode for {patient.full_name}",
        user=user,
    )
    return episode


@transaction.atomic
def assign_care_team_member(*, episode: EpisodeOfCare, staff_member: StaffProfile, role: CareTeamRoleChoices, is_primary: bool = False, notes: str = '', user=None) -> CareTeamMember:
    # If is_primary doctor or nurse, unset previous primary for this role
    if is_primary:
        CareTeamMember.objects.filter(episode=episode, role=role, is_primary=True).update(is_primary=False)

    member = CareTeamMember.objects.create(
        episode=episode,
        staff_member=staff_member,
        role=role,
        is_primary=is_primary,
        notes=notes,
    )
    log_audit_event(
        action=AuditAction.UPDATE,
        resource_type='CareTeam',
        resource_id=str(episode.patient.id),
        summary=f"Assigned {staff_member.user.display_name} ({member.get_role_display()}) to care team for {episode.patient.full_name}",
        user=user,
    )
    return member


@transaction.atomic
def create_care_plan(*, patient: Patient, overall_goals: str, episode: EpisodeOfCare = None, primary_diagnosis: str = '', resuscitation_preference: str = '', title: str = 'Individualized Palliative Care Plan', review_date: date = None, status: CarePlanStatusChoices = CarePlanStatusChoices.ACTIVE, user=None) -> CarePlan:
    # A patient may only have one ACTIVE care plan at a time.
    if status == CarePlanStatusChoices.ACTIVE:
        CarePlan.objects.filter(patient=patient, status=CarePlanStatusChoices.ACTIVE).update(status=CarePlanStatusChoices.COMPLETED)

    care_plan = CarePlan.objects.create(
        patient=patient,
        episode=episode or patient.episodes.filter(status=EpisodeStatusChoices.ACTIVE).first(),
        title=title,
        primary_diagnosis=primary_diagnosis or patient.primary_diagnosis,
        overall_goals=overall_goals,
        resuscitation_preference=resuscitation_preference or 'Allow Natural Death (AND) / Comfort Measures',
        review_date=review_date,
        status=status,
        created_by=user,
    )

    log_audit_event(
        action=AuditAction.CREATE,
        resource_type='CarePlan',
        resource_id=str(care_plan.id),
        summary=f"Created active care plan '{care_plan.title}' for {patient.full_name}",
        user=user,
    )
    return care_plan


@transaction.atomic
def add_care_plan_need(*, care_plan: CarePlan, category: NeedCategoryChoices, problem_description: str, goal: str, interventions: str, responsible_discipline: str = 'Nursing & Medical', target_date: date = None) -> CarePlanNeed:
    return CarePlanNeed.objects.create(
        care_plan=care_plan,
        category=category,
        problem_description=problem_description,
        goal=goal,
        interventions=interventions,
        responsible_discipline=responsible_discipline,
        target_date=target_date,
    )


@transaction.atomic
def review_care_plan(*, care_plan: CarePlan, next_review_date: date, user=None) -> CarePlan:
    care_plan.last_reviewed_at = timezone.now()
    care_plan.review_date = next_review_date
    care_plan.status = CarePlanStatusChoices.ACTIVE
    care_plan.save()

    log_audit_event(
        action=AuditAction.UPDATE,
        resource_type='CarePlan',
        resource_id=str(care_plan.id),
        summary=f"Reviewed care plan for {care_plan.patient.full_name}. Next review scheduled for {next_review_date}",
        user=user,
    )
    return care_plan
