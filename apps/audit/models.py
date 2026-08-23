import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _


class AuditAction(models.TextChoices):
    LOGIN = 'LOGIN', _('User Sign In')
    LOGOUT = 'LOGOUT', _('User Sign Out')
    VIEW = 'VIEW', _('Record Viewed')
    CREATE = 'CREATE', _('Record Created')
    UPDATE = 'UPDATE', _('Record Updated')
    AMEND = 'AMEND', _('Clinical Record Amended')
    DELETE = 'DELETE', _('Record Deleted')
    EXPORT = 'EXPORT', _('Data Exported')
    PERMISSION_CHANGE = 'PERMISSION_CHANGE', _('Permissions Changed')


class AuditEvent(models.Model):
    """
    Immutable audit event trail for clinical compliance and security monitoring.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_events'
    )
    user_email = models.CharField(max_length=255, blank=True)
    user_role = models.CharField(max_length=50, blank=True)
    action = models.CharField(max_length=50, choices=AuditAction.choices, db_index=True)
    resource_type = models.CharField(max_length=100, db_index=True)
    resource_id = models.CharField(max_length=100, blank=True, db_index=True)
    summary = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        verbose_name = _('Audit Event')
        verbose_name_plural = _('Audit Events')
        ordering = ['-timestamp']

    def __str__(self):
        user_str = self.user_email or (self.user.email if self.user else 'System')
        return f"[{self.timestamp.strftime('%Y-%m-%d %H:%M:%S')}] {user_str} - {self.action} on {self.resource_type}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise RuntimeError('Audit events are immutable and cannot be updated.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError('Audit events are immutable and cannot be deleted.')
