import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class NotificationTypeChoices(models.TextChoices):
    CARE_PLAN_DUE = 'CARE_PLAN_DUE', _('Care Plan Review Due')
    FOLLOWUP_OVERDUE = 'FOLLOWUP_OVERDUE', _('Overdue Follow-up Visit')
    PENDING_REFERRAL = 'PENDING_REFERRAL', _('High Priority Referral Pending')
    PATIENT_ASSIGNED = 'PATIENT_ASSIGNED', _('Assigned to Patient Care Team')
    MISSED_APPOINTMENT = 'MISSED_APPOINTMENT', _('Missed Clinic/Home Appointment')
    CLINICAL_ALERT = 'CLINICAL_ALERT', _('High Distress Symptom / Clinical Alert')
    NEW_PATIENT_REGISTERED = 'NEW_PATIENT_REGISTERED', _('New Patient Registered')
    NEW_APPOINTMENT_SCHEDULED = 'NEW_APPOINTMENT_SCHEDULED', _('New Appointment Scheduled')


class Notification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=30, choices=NotificationTypeChoices.choices)
    title = models.CharField(max_length=200)
    message = models.TextField()
    link_url = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('Notification')
        verbose_name_plural = _('Notifications')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} -> {self.recipient.email}"


class WebhookDelivery(models.Model):
    """Durable outbound event used to retry webhook delivery after process failure."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    event_name = models.CharField(max_length=100)
    url = models.URLField(max_length=2048)
    payload = models.JSONField()
    attempts = models.PositiveIntegerField(default=0)
    delivered_at = models.DateTimeField(null=True, blank=True)
    last_error = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=['delivered_at', 'created_at'], name='webhook_delivered_created_idx')]
