from django.db.models import Q, QuerySet

from .models import Referral, ReferralStatusChoices


def get_all_referrals() -> QuerySet[Referral]:
    return Referral.objects.all().select_related('assigned_reviewer', 'converted_patient').order_by('-referral_date')


def get_pending_referrals() -> QuerySet[Referral]:
    return Referral.objects.filter(status__in=[ReferralStatusChoices.RECEIVED, ReferralStatusChoices.UNDER_REVIEW]).select_related('assigned_reviewer').order_by('priority', '-referral_date')


def filter_referrals(query: str = '', status: str = '', priority: str = '') -> QuerySet[Referral]:
    qs = Referral.objects.all().select_related('assigned_reviewer', 'converted_patient').order_by('-referral_date')
    if query:
        qs = qs.filter(
            Q(referral_number__icontains=query) |
            Q(patient_name__icontains=query) |
            Q(referring_facility__icontains=query) |
            Q(primary_diagnosis__icontains=query)
        )
    if status:
        qs = qs.filter(status=status)
    if priority:
        qs = qs.filter(priority=priority)
    return qs
