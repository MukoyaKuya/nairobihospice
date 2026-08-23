from django.db.models import QuerySet

from apps.patients.models import Patient

from .models import (
    CarePlan,
    CarePlanStatusChoices,
    CareTeamMember,
    EpisodeOfCare,
    EpisodeStatusChoices,
)


def get_active_episode(patient: Patient) -> EpisodeOfCare:
    return EpisodeOfCare.objects.filter(patient=patient, status=EpisodeStatusChoices.ACTIVE).first()


def get_care_team(episode: EpisodeOfCare) -> QuerySet[CareTeamMember]:
    return CareTeamMember.objects.filter(episode=episode).select_related('staff_member__user')


def get_active_care_plan(patient: Patient) -> CarePlan:
    return CarePlan.objects.filter(patient=patient, status=CarePlanStatusChoices.ACTIVE).prefetch_related('needs').first()


def get_care_plans_due_for_review(days_ahead: int = 7) -> QuerySet[CarePlan]:
    from datetime import timedelta

    from django.utils import timezone
    cutoff = timezone.now().date() + timedelta(days=days_ahead)
    return CarePlan.objects.filter(
        status=CarePlanStatusChoices.ACTIVE,
        review_date__lte=cutoff
    ).select_related('patient', 'created_by').order_by('review_date')
