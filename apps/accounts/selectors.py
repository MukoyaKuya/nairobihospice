from django.db.models import QuerySet

from .models import RoleChoices, StaffProfile


def get_active_staff() -> QuerySet[StaffProfile]:
    return StaffProfile.objects.filter(is_active_staff=True).select_related('user')


def get_staff_by_role(role: RoleChoices) -> QuerySet[StaffProfile]:
    return StaffProfile.objects.filter(role=role, is_active_staff=True).select_related('user')


def get_doctors() -> QuerySet[StaffProfile]:
    return get_staff_by_role(RoleChoices.DOCTOR)


def get_nurses() -> QuerySet[StaffProfile]:
    return get_staff_by_role(RoleChoices.NURSE)


def get_social_workers() -> QuerySet[StaffProfile]:
    return get_staff_by_role(RoleChoices.SOCIAL_WORKER)


def get_counsellors() -> QuerySet[StaffProfile]:
    return get_staff_by_role(RoleChoices.COUNSELLOR)
