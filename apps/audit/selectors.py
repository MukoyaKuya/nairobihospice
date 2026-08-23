from django.db.models import QuerySet

from .models import AuditEvent


def get_recent_audit_events(limit: int = 100) -> QuerySet[AuditEvent]:
    return AuditEvent.objects.all().order_by('-timestamp')[:limit]


def get_patient_audit_history(patient_id: str) -> QuerySet[AuditEvent]:
    return AuditEvent.objects.filter(resource_type__in=['Patient', 'Assessment', 'Encounter', 'CarePlan', 'Medication'], resource_id=str(patient_id)).order_by('-timestamp')
