import uuid
from decimal import Decimal

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class DeletionRequestStatusChoices(models.TextChoices):
    PENDING = 'PENDING', _('Pending Operations Approval')
    APPROVED = 'APPROVED', _('Approved & Closed / Archived')
    REJECTED = 'REJECTED', _('Rejected')


class PatientDeletionRequest(models.Model):
    """
    Formal deletion request submitted by front desk or clinicians,
    requiring Operations Manager / Admin authorization before purging patient records.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deletion_requests'
    )
    patient_id_copy = models.UUIDField(null=True, blank=True)
    patient_name = models.CharField(max_length=200)
    hospice_number = models.CharField(max_length=50)
    ip_op_number = models.CharField(max_length=50, blank=True)
    
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='requested_deletions'
    )
    reason = models.TextField(help_text=_('Reason why this patient file should be deleted (duplicate, test, error, etc.)'))
    
    status = models.CharField(
        max_length=20,
        choices=DeletionRequestStatusChoices.choices,
        default=DeletionRequestStatusChoices.PENDING,
        db_index=True
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_deletions'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Patient Deletion Request')
        verbose_name_plural = _('Patient Deletion Requests')
        ordering = ['-created_at']

    def __str__(self):
        return f"Deletion Request: {self.patient_name} ({self.hospice_number}) - {self.get_status_display()}"


class AppointmentDeletionRequest(models.Model):
    """
    Formal deletion request for completed, cancelled, or obsolete appointments/tasks,
    requiring Operations Manager / Admin authorization before purging.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(
        'appointments.Appointment',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='deletion_requests'
    )
    appointment_id_copy = models.UUIDField(null=True, blank=True)
    patient_name = models.CharField(max_length=200)
    hospice_number = models.CharField(max_length=50)
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField(null=True, blank=True)
    appointment_type = models.CharField(max_length=50)
    appointment_status = models.CharField(max_length=50)
    clinician_name = models.CharField(max_length=200, blank=True)
    
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='requested_appointment_deletions'
    )
    reason = models.TextField(help_text=_('Reason why this appointment/task should be deleted (completed, duplicate, cancelled, error, etc.)'))
    
    status = models.CharField(
        max_length=20,
        choices=DeletionRequestStatusChoices.choices,
        default=DeletionRequestStatusChoices.PENDING,
        db_index=True
    )
    
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_appointment_deletions'
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_notes = models.TextField(blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Appointment Deletion Request')
        verbose_name_plural = _('Appointment Deletion Requests')
        ordering = ['-created_at']

    def __str__(self):
        return f"Appointment Deletion: {self.patient_name} ({self.scheduled_date}) - {self.get_status_display()}"


class VendorCategoryChoices(models.TextChoices):
    PHARMACEUTICAL = 'PHARMACEUTICAL', _('Pharmaceutical & Essential Meds')
    CONSUMABLES = 'CONSUMABLES', _('Medical Consumables & Wound Care')
    OXYGEN_EQUIPMENT = 'OXYGEN_EQUIPMENT', _('Oxygen & Medical Equipment')
    PPE_SANITATION = 'PPE_SANITATION', _('Infection Control & PPE')
    NUTRITION = 'NUTRITION', _('Clinical Nutrition & Supplements')
    GENERAL_SERVICES = 'GENERAL_SERVICES', _('Facility, Logistics & IT Services')


class VendorStatusChoices(models.TextChoices):
    ACTIVE = 'ACTIVE', _('Active Supplier')
    PREFERRED = 'PREFERRED', _('Preferred Hospice Partner')
    UNDER_REVIEW = 'UNDER_REVIEW', _('Under Review / Audit')
    INACTIVE = 'INACTIVE', _('Inactive / Suspended')


class Vendor(models.Model):
    """
    Suppliers, distributors, and partners providing medications and hospital consumables.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, db_index=True)
    code = models.CharField(max_length=50, unique=True)
    category = models.CharField(
        max_length=30,
        choices=VendorCategoryChoices.choices,
        default=VendorCategoryChoices.PHARMACEUTICAL
    )
    contact_person = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=30)
    email = models.EmailField(blank=True)
    kra_pin = models.CharField(max_length=50, blank=True, verbose_name="KRA PIN")
    physical_address = models.TextField(blank=True)
    payment_terms = models.CharField(max_length=100, default="30 Days Net")
    status = models.CharField(
        max_length=20,
        choices=VendorStatusChoices.choices,
        default=VendorStatusChoices.ACTIVE,
        db_index=True
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Vendor')
        verbose_name_plural = _('Vendors')
        ordering = ['name']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"


class StockCategoryChoices(models.TextChoices):
    ESSENTIAL_MEDICINE = 'ESSENTIAL_MEDICINE', _('Essential Palliative Medications')
    CONTROLLED_OPIOID = 'CONTROLLED_OPIOID', _('Controlled Opioids (Oral Morphine / Fentanyl)')
    WOUND_CARE = 'WOUND_CARE', _('Palliative Wound Care & Dressings')
    OXYGEN_EQUIPMENT = 'OXYGEN_EQUIPMENT', _('Oxygen & Medical Equipment')
    PPE_SANITATION = 'PPE_SANITATION', _('Infection Control & PPE')
    NUTRITIONAL_FEED = 'NUTRITIONAL_FEED', _('Enteral & Nutritional Supplements')
    DIAGNOSTIC = 'DIAGNOSTIC', _('Diagnostic & Lab Reagents')


class StockItem(models.Model):
    """
    Inventory and supply catalog items tracked across pharmacy and storage.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    item_code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=200, db_index=True)
    category = models.CharField(
        max_length=30,
        choices=StockCategoryChoices.choices,
        default=StockCategoryChoices.ESSENTIAL_MEDICINE,
        db_index=True
    )
    unit_of_measure = models.CharField(max_length=50, default="Units", help_text=_("e.g. Bottles, Boxes, Packs, Vials"))
    quantity_on_hand = models.IntegerField(default=0)
    minimum_reorder_level = models.IntegerField(default=10)
    unit_cost_kes = models.DecimalField(max_digits=12, decimal_places=2, default=0.00, verbose_name="Unit Cost (KES)")
    preferred_vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supplied_items'
    )
    location_bin = models.CharField(max_length=100, blank=True, help_text=_("e.g. Pharmacy Main Rack A3, Cold Storage 2"))
    is_controlled_substance = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Stock Item')
        verbose_name_plural = _('Stock Items')
        ordering = ['name']
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_on_hand__gte=0), name='stock_quantity_non_negative'),
            models.CheckConstraint(condition=models.Q(minimum_reorder_level__gte=0), name='stock_reorder_level_non_negative'),
            models.CheckConstraint(condition=models.Q(unit_cost_kes__gte=0), name='stock_unit_cost_non_negative'),
        ]

    def __str__(self):
        return f"{self.item_code} - {self.name} ({self.quantity_on_hand} {self.unit_of_measure})"

    @property
    def is_low_stock(self):
        return self.quantity_on_hand <= self.minimum_reorder_level

    @property
    def total_valuation_kes(self):
        return self.quantity_on_hand * self.unit_cost_kes


class ProcurementStatusChoices(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft Requisition')
    PENDING_APPROVAL = 'PENDING_APPROVAL', _('Pending Management Approval')
    APPROVED = 'APPROVED', _('Approved & Issued to Vendor')
    PARTIALLY_DELIVERED = 'PARTIALLY_DELIVERED', _('Partially Delivered')
    COMPLETED = 'COMPLETED', _('Completed / In Stock')
    CANCELLED = 'CANCELLED', _('Cancelled')


class ProcurementOrder(models.Model):
    """
    Formal procurement purchase order and inventory acquisition requisitions.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    po_number = models.CharField(max_length=50, unique=True, db_index=True)
    vendor = models.ForeignKey(Vendor, on_delete=models.PROTECT, related_name='procurement_orders')
    order_date = models.DateField(default=timezone.now, db_index=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    actual_delivery_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=30,
        choices=ProcurementStatusChoices.choices,
        default=ProcurementStatusChoices.PENDING_APPROVAL,
        db_index=True
    )
    total_amount_kes = models.DecimalField(max_digits=14, decimal_places=2, default=0.00, verbose_name="Total Amount (KES)")
    invoice_number = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='requested_orders'
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_orders'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Procurement Order')
        verbose_name_plural = _('Procurement Orders')
        ordering = ['-order_date', '-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(total_amount_kes__gte=0), name='po_total_amount_non_negative'),
        ]

    def __str__(self):
        return f"{self.po_number} - {self.vendor.name} (KES {self.total_amount_kes:,.2f})"


class ProcurementOrderItem(models.Model):
    """
    Line item inside a procurement order.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(ProcurementOrder, on_delete=models.PROTECT, related_name='items')
    stock_item = models.ForeignKey(StockItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='order_items')
    quantity_requested = models.IntegerField(default=1)
    quantity_received = models.IntegerField(default=0)
    unit_price_kes = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_price_kes = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = _('Procurement Order Item')
        verbose_name_plural = _('Procurement Order Items')
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity_requested__gt=0), name='po_item_requested_positive'),
            models.CheckConstraint(condition=models.Q(quantity_received__gte=0), name='po_item_received_non_negative'),
            models.CheckConstraint(condition=models.Q(quantity_received__lte=models.F('quantity_requested')), name='po_item_received_not_over_requested'),
            models.CheckConstraint(condition=models.Q(unit_price_kes__gte=0), name='po_item_unit_price_non_negative'),
            models.CheckConstraint(condition=models.Q(total_price_kes__gte=0), name='po_item_total_price_non_negative'),
        ]

    def save(self, *args, **kwargs):
        self.total_price_kes = self.quantity_requested * self.unit_price_kes
        super().save(*args, **kwargs)


class MovementTypeChoices(models.TextChoices):
    RECEIVE = 'RECEIVE', _('Stock Received (PO Delivery)')
    DISPENSE = 'DISPENSE', _('Dispensed to Patient')
    TRANSFER = 'TRANSFER', _('Transfer to Home Care Kits')
    ADJUSTMENT = 'ADJUSTMENT', _('Physical Count Audit Adjustment')
    WASTAGE = 'WASTAGE', _('Wastage / Expired / Damaged')


class StockMovement(models.Model):
    """
    Immutable audit ledger of inventory inflows, outflows, and adjustments.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stock_item = models.ForeignKey(StockItem, on_delete=models.PROTECT, related_name='movements')
    movement_type = models.CharField(max_length=20, choices=MovementTypeChoices.choices, db_index=True)
    quantity = models.IntegerField(help_text=_("Positive for inbound, negative for outbound"))
    balance_after = models.IntegerField()
    reference_document = models.CharField(max_length=100, blank=True, help_text=_("e.g. PO Number, Patient ID, or Audit ID"))
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        help_text=_("Linked patient record for dispensed medications/supplies")
    )
    medication_statement = models.ForeignKey(
        'medications.MedicationStatement',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements',
        help_text=_("Linked medication prescription/statement if applicable")
    )
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='stock_movements'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        verbose_name = _('Stock Movement')
        verbose_name_plural = _('Stock Movements')
        ordering = ['-created_at']
        constraints = [
            models.CheckConstraint(condition=~models.Q(quantity=0), name='movement_quantity_nonzero'),
            models.CheckConstraint(
                condition=~models.Q(movement_type='DISPENSE') | (
                    models.Q(patient__isnull=False) & models.Q(medication_statement__isnull=False)
                ),
                name='dispense_requires_patient_and_rx'
            ),
        ]

    def clean(self):
        super().clean()
        from django.core.exceptions import ValidationError
        if self.movement_type == MovementTypeChoices.DISPENSE:
            if self.patient is None:
                raise ValidationError({'patient': 'A patient is required for all medication dispenses.'})
            if self.medication_statement is None:
                raise ValidationError({'medication_statement': 'A linked active medication statement is required for all patient dispenses.'})
            if self.medication_statement.patient_id != self.patient_id:
                raise ValidationError({'medication_statement': 'The selected prescription does not belong to the dispensed patient.'})

    def save(self, *args, **kwargs):
        # The movement ledger is an append-only record (controlled substances
        # compliance). Corrections are new ADJUSTMENT movements, never edits.
        if not self._state.adding:
            raise RuntimeError('Stock movements are immutable and cannot be updated.')
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise RuntimeError('Stock movements are immutable and cannot be deleted.')


class InvoiceTypeChoices(models.TextChoices):
    SUPPLIER_PURCHASE = 'SUPPLIER_PURCHASE', _('Supplier / Vendor Purchase Invoice (Payable)')
    PATIENT_SERVICE = 'PATIENT_SERVICE', _('Patient Clinical & Pharmacy Invoice (Receivable)')
    DONOR_SUBSIDY = 'DONOR_SUBSIDY', _('Institutional Donor / Subsidy Requisition')


class PaymentStatusChoices(models.TextChoices):
    DRAFT = 'DRAFT', _('Draft Invoice')
    ISSUED = 'ISSUED', _('Issued / Awaiting Payment')
    PARTIALLY_PAID = 'PARTIALLY_PAID', _('Partially Paid')
    PAID = 'PAID', _('Paid & Reconciled')
    CANCELLED = 'CANCELLED', _('Cancelled / Void')


class PaymentMethodChoices(models.TextChoices):
    CASH = 'Cash', _('Cash')
    BANK_TRANSFER = 'Bank Transfer (EFT / RTGS)', _('Bank Transfer (EFT / RTGS)')
    MPESA = 'M-PESA (Paybill 981234)', _('M-PESA (Paybill 981234)')
    CHEQUE = 'Cheque', _('Cheque')
    DHA_SHA_INSURANCE = 'DHA / SHA / Insurance', _('DHA / SHA / Insurance')


class InvoiceNumberSequence(models.Model):
    """Database-backed counter for concurrency-safe invoice numbering."""
    year = models.PositiveIntegerField()
    prefix = models.CharField(max_length=3)
    next_number = models.PositiveIntegerField(default=1)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['year', 'prefix'], name='invoice_sequence_year_prefix_unique'),
        ]


class Invoice(models.Model):
    """
    Formal tax invoice and financial billing document for suppliers, patients, and donors.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice_number = models.CharField(max_length=50, unique=True, db_index=True)
    invoice_type = models.CharField(
        max_length=30,
        choices=InvoiceTypeChoices.choices,
        default=InvoiceTypeChoices.SUPPLIER_PURCHASE,
        db_index=True
    )
    vendor = models.ForeignKey(
        Vendor,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices'
    )
    patient = models.ForeignKey(
        'patients.Patient',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices'
    )
    procurement_order = models.ForeignKey(
        ProcurementOrder,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='invoices'
    )
    issue_date = models.DateField(default=timezone.now, db_index=True)
    due_date = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=PaymentStatusChoices.choices,
        default=PaymentStatusChoices.ISSUED,
        db_index=True
    )
    subtotal_amount_kes = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    tax_amount_kes = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    discount_amount_kes = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_amount_kes = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    amount_paid_kes = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    payment_method = models.CharField(
        max_length=100,
        choices=PaymentMethodChoices.choices,
        default=PaymentMethodChoices.CASH
    )
    payment_reference = models.CharField(max_length=100, blank=True)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_invoices'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Invoice')
        verbose_name_plural = _('Invoices')
        ordering = ['-issue_date', '-created_at']
        constraints = [
            models.CheckConstraint(condition=models.Q(subtotal_amount_kes__gte=0), name='invoice_subtotal_non_negative'),
            models.CheckConstraint(condition=models.Q(tax_amount_kes__gte=0), name='invoice_tax_non_negative'),
            models.CheckConstraint(condition=models.Q(discount_amount_kes__gte=0), name='invoice_discount_non_negative'),
            models.CheckConstraint(condition=models.Q(total_amount_kes__gte=0), name='invoice_total_non_negative'),
            models.CheckConstraint(condition=models.Q(amount_paid_kes__gte=0), name='invoice_paid_non_negative'),
            models.CheckConstraint(
                condition=models.Q(amount_paid_kes__lte=models.F('total_amount_kes')),
                name='invoice_paid_not_over_total',
            ),
        ]

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            year = (self.issue_date or timezone.now().date()).year
            prefix = "INV" if self.invoice_type == InvoiceTypeChoices.PATIENT_SERVICE else ("VOU" if self.invoice_type == InvoiceTypeChoices.SUPPLIER_PURCHASE else "DON")
            with transaction.atomic():
                sequence, _ = InvoiceNumberSequence.objects.get_or_create(year=year, prefix=prefix)
                sequence = InvoiceNumberSequence.objects.select_for_update().get(pk=sequence.pk)
                self.invoice_number = f"{prefix}-{year}-{sequence.next_number:04d}"
                sequence.next_number += 1
                sequence.save(update_fields=['next_number'])
                super().save(*args, **kwargs)
            return
        super().save(*args, **kwargs)

    def __str__(self):
        recipient = self.vendor.name if self.vendor else (self.patient.full_name if self.patient else "General Recipient")
        return f"{self.invoice_number} - {recipient} (KES {self.total_amount_kes:,.2f})"

    @property
    def balance_due_kes(self):
        return max(Decimal('0.00'), self.total_amount_kes - self.amount_paid_kes)

    @property
    def is_fully_paid(self):
        return self.status == PaymentStatusChoices.PAID or (self.total_amount_kes > 0 and self.amount_paid_kes >= self.total_amount_kes)


class InvoiceLineItem(models.Model):
    """
    Individual billable line item in an invoice.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='items')
    stock_item = models.ForeignKey(StockItem, on_delete=models.SET_NULL, null=True, blank=True, related_name='invoice_items')
    description = models.CharField(max_length=255)
    quantity = models.IntegerField(default=1)
    unit_price_kes = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    total_price_kes = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)

    class Meta:
        verbose_name = _('Invoice Line Item')
        verbose_name_plural = _('Invoice Line Items')
        constraints = [
            models.CheckConstraint(condition=models.Q(quantity__gt=0), name='invoice_line_quantity_positive'),
            models.CheckConstraint(condition=models.Q(unit_price_kes__gte=0), name='invoice_line_unit_price_non_negative'),
            models.CheckConstraint(condition=models.Q(total_price_kes__gte=0), name='invoice_line_total_non_negative'),
        ]

    def save(self, *args, **kwargs):
        self.total_price_kes = self.quantity * self.unit_price_kes
        super().save(*args, **kwargs)
