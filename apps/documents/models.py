import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from apps.patients.models import Patient

from .storage import private_document_storage


class DocumentCategoryChoices(models.TextChoices):
    REFERRAL_LETTER = 'REFERRAL_LETTER', _('Referral Letter / Medical Transfer')
    CLINICAL_SUMMARY = 'CLINICAL_SUMMARY', _('Hospital Summary / Discharge Notes')
    CONSENT_FORM = 'CONSENT_FORM', _('Signed Consent / Advance Care Directive')
    LAB_REPORT = 'LAB_REPORT', _('Laboratory / Pathology Report')
    RADIOLOGY_REPORT = 'RADIOLOGY_REPORT', _('Radiology / Imaging Report (CT, MRI, X-Ray)')
    PRESCRIPTION = 'PRESCRIPTION', _('External Prescription / Pharmacy Order')
    OTHER = 'OTHER', _('Other Document')


class PatientDocument(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='documents')
    category = models.CharField(
        max_length=30,
        choices=DocumentCategoryChoices.choices,
        default=DocumentCategoryChoices.REFERRAL_LETTER
    )
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='%Y/%m/', storage=private_document_storage)
    file_size_bytes = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True)

    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _('Patient Document')
        verbose_name_plural = _('Patient Documents')
        ordering = ['-uploaded_at']
        indexes = [models.Index(fields=['patient', 'uploaded_at'], name='doc_patient_uploaded_idx')]

    def __str__(self):
        return f"{self.get_category_display()}: {self.title} - {self.patient.full_name}"
