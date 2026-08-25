from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import F, Q, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.generic import DetailView, ListView, View

from apps.accounts.permissions import ManagerRequiredMixin
from apps.audit.models import AuditAction
from apps.audit.services import log_audit_event
from apps.patients.models import Patient

from .forms import (
    InvoiceForm,
    InvoiceLineItemForm,
    InvoicePaymentForm,
    ProcurementOrderForm,
    StockDispenseForm,
    StockItemForm,
    StockReceiveForm,
    VendorForm,
)
from .models import (
    AppointmentDeletionRequest,
    DeletionRequestStatusChoices,
    Invoice,
    InvoiceLineItem,
    InvoiceTypeChoices,
    MovementTypeChoices,
    PatientDeletionRequest,
    PaymentStatusChoices,
    ProcurementOrder,
    StockItem,
    StockMovement,
    Vendor,
)
from .selectors import (
    get_disease_analytics_data,
    get_operations_dashboard_data,
)
from .services import record_stock_movement


class OperationsDashboardView(ManagerRequiredMixin, View):
    def get(self, request):
        data = get_operations_dashboard_data()
        return render(request, 'operations/operations_dashboard.html', data)


class VendorListView(ManagerRequiredMixin, ListView):
    model = Vendor
    template_name = 'operations/vendor_list.html'
    context_object_name = 'vendors'
    paginate_by = 15

    def get_queryset(self):
        qs = Vendor.objects.prefetch_related('supplied_items').order_by('name')
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category=category)
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(contact_person__icontains=search) | qs.filter(code__icontains=search)
        return qs


class VendorCreateView(ManagerRequiredMixin, View):
    def get(self, request):
        form = VendorForm()
        return render(request, 'operations/vendor_form.html', {'form': form})

    def post(self, request):
        form = VendorForm(request.POST)
        if form.is_valid():
            vendor = form.save()
            log_audit_event(
                action=AuditAction.CREATE,
                resource_type='Vendor',
                resource_id=str(vendor.id),
                summary=f"Added vendor {vendor.name} ({vendor.code})",
                user=request.user,
            )
            messages.success(request, f"Vendor {vendor.name} successfully registered.")
            return redirect('operations:vendor_detail', pk=vendor.pk)
        return render(request, 'operations/vendor_form.html', {'form': form})


class VendorDetailView(ManagerRequiredMixin, DetailView):
    model = Vendor
    template_name = 'operations/vendor_detail.html'
    context_object_name = 'vendor'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['supplied_items'] = self.object.supplied_items.all()
        context['orders'] = self.object.procurement_orders.order_by('-order_date')[:10]
        return context


class ProcurementOrderListView(ManagerRequiredMixin, ListView):
    model = ProcurementOrder
    template_name = 'operations/procurement_list.html'
    context_object_name = 'orders'
    paginate_by = 15

    def get_queryset(self):
        qs = ProcurementOrder.objects.select_related('vendor', 'requested_by').order_by('-order_date')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(po_number__icontains=search) | qs.filter(vendor__name__icontains=search)
        return qs


class ProcurementOrderCreateView(ManagerRequiredMixin, View):
    def get(self, request):
        form = ProcurementOrderForm()
        return render(request, 'operations/procurement_form.html', {'form': form})

    def post(self, request):
        form = ProcurementOrderForm(request.POST)
        if form.is_valid():
            order = form.save(commit=False)
            order.requested_by = request.user
            order.save()
            log_audit_event(
                action=AuditAction.CREATE,
                resource_type='ProcurementOrder',
                resource_id=str(order.id),
                summary=f"Created procurement order {order.po_number} for {order.vendor.name}",
                user=request.user,
            )
            messages.success(request, f"Procurement order {order.po_number} created successfully.")
            return redirect('operations:procurement_detail', pk=order.pk)
        return render(request, 'operations/procurement_form.html', {'form': form})


class ProcurementOrderDetailView(ManagerRequiredMixin, DetailView):
    model = ProcurementOrder
    template_name = 'operations/procurement_detail.html'
    context_object_name = 'order'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['items'] = self.object.items.select_related('stock_item')
        return context


class InventoryListView(ManagerRequiredMixin, ListView):
    model = StockItem
    template_name = 'operations/inventory_list.html'
    context_object_name = 'stock_items'
    paginate_by = 20

    def get_queryset(self):
        qs = StockItem.objects.select_related('preferred_vendor').order_by('name')
        category = self.request.GET.get('category')
        if category:
            qs = qs.filter(category=category)
        filter_type = self.request.GET.get('filter')
        if filter_type == 'low_stock':
            qs = qs.filter(quantity_on_hand__lte=F('minimum_reorder_level'))
        search = self.request.GET.get('search')
        if search:
            qs = qs.filter(name__icontains=search) | qs.filter(item_code__icontains=search)
        return qs


class StockItemCreateView(ManagerRequiredMixin, View):
    def get(self, request):
        form = StockItemForm()
        return render(request, 'operations/stock_item_form.html', {'form': form})

    def post(self, request):
        form = StockItemForm(request.POST)
        if form.is_valid():
            item = form.save()
            if item.quantity_on_hand > 0:
                StockMovement.objects.create(
                    stock_item=item,
                    movement_type=MovementTypeChoices.RECEIVE,
                    quantity=item.quantity_on_hand,
                    balance_after=item.quantity_on_hand,
                    reference_document="INITIAL_STOCK_COUNT",
                    notes="Initial stock quantity on catalog creation",
                    recorded_by=request.user,
                )
            messages.success(request, f"Stock item {item.name} ({item.item_code}) added to inventory.")
            return redirect('operations:inventory_list')
        return render(request, 'operations/stock_item_form.html', {'form': form})


class StockReceiveView(ManagerRequiredMixin, View):
    def get(self, request):
        po_id = request.GET.get('po_id')
        initial = {}
        purchase_order = None
        if po_id:
            purchase_order = ProcurementOrder.objects.prefetch_related('items__stock_item').filter(pk=po_id).first()
            if purchase_order:
                initial['reference_document'] = purchase_order.po_number
                if purchase_order.items.count() == 1:
                    initial['stock_item'] = purchase_order.items.first().stock_item_id
                    initial['quantity'] = purchase_order.items.first().quantity_requested
        form = StockReceiveForm(initial=initial)
        return render(request, 'operations/stock_receive_form.html', {
            'form': form,
            'purchase_order': purchase_order,
        })

    def post(self, request):
        form = StockReceiveForm(request.POST)
        if form.is_valid():
            stock_item = form.cleaned_data['stock_item']
            qty = form.cleaned_data['quantity']
            ref = form.cleaned_data['reference_document']
            notes = form.cleaned_data['notes']

            movement = record_stock_movement(
                stock_item=stock_item,
                movement_type=MovementTypeChoices.RECEIVE,
                quantity=qty,
                reference_document=ref,
                notes=notes,
                user=request.user,
            )
            messages.success(request, f"Received {qty} {stock_item.unit_of_measure} of {stock_item.name}. New Balance: {movement.balance_after}.")
            return redirect('operations:inventory_list')
        return render(request, 'operations/stock_receive_form.html', {'form': form})


class PharmacyDispenseView(LoginRequiredMixin, View):
    """
    Day-One Pharmacy Slice: Dispense stock directly to an active patient / medication statement,
    with controlled substance / opioid register highlighting and immutable stock movement logging.
    """
    def get(self, request):
        from apps.patients.access import can_manage_all_patients
        if not (request.user.is_pharmacist or request.user.is_clinical or can_manage_all_patients(request.user)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Only pharmacy, clinical, and management staff may dispense stock.")

        import json
        stock_item_id = request.GET.get('stock_item')
        patient_id = request.GET.get('patient')
        initial = {}
        if stock_item_id:
            initial['stock_item'] = stock_item_id
        if patient_id:
            initial['patient'] = patient_id

        form = StockDispenseForm(initial=initial)
        stock_items = list(StockItem.objects.all().order_by('name').values('id', 'name', 'item_code', 'quantity_on_hand', 'unit_of_measure', 'is_controlled_substance'))
        return render(request, 'operations/pharmacy_dispense.html', {
            'form': form,
            'stock_items_json': json.dumps([
                {**item, 'id': str(item['id'])} for item in stock_items
            ]),
            'recent_dispenses': StockMovement.objects.filter(movement_type=MovementTypeChoices.DISPENSE).select_related('stock_item', 'recorded_by')[:15],
        })

    def post(self, request):
        from apps.patients.access import can_manage_all_patients
        if not (request.user.is_pharmacist or request.user.is_clinical or can_manage_all_patients(request.user)):
            from django.core.exceptions import PermissionDenied
            raise PermissionDenied("Only pharmacy, clinical, and management staff may dispense stock.")

        import json
        form = StockDispenseForm(request.POST)
        if form.is_valid():
            stock_item = form.cleaned_data['stock_item']
            patient = form.cleaned_data['patient']
            quantity = form.cleaned_data['quantity']
            medication_statement = form.cleaned_data.get('medication_statement', '')
            notes = form.cleaned_data.get('notes', '')

            ref = f"Patient: {patient.full_name} ({patient.hospice_number})"
            if medication_statement:
                ref += f" | Med: {medication_statement.medication_name}"

            try:
                movement = record_stock_movement(
                    stock_item=stock_item,
                    movement_type=MovementTypeChoices.DISPENSE,
                    quantity=quantity,
                    reference_document=ref,
                    patient=patient,
                    medication_statement=medication_statement,
                    notes=notes,
                    user=request.user,
                )
                log_audit_event(
                    action=AuditAction.CREATE,
                    resource_type='StockDispense',
                    resource_id=str(movement.id),
                    summary=f"Dispensed {quantity} {stock_item.unit_of_measure} of {stock_item.name} to {patient.full_name} ({patient.hospice_number})",
                    user=request.user,
                    metadata={
                        'stock_item': stock_item.name,
                        'is_controlled_substance': stock_item.is_controlled_substance,
                        'patient': patient.hospice_number,
                        'patient_id': str(patient.id),
                        'quantity': quantity,
                    }
                )
                messages.success(
                    request,
                    f"Successfully dispensed {quantity} {stock_item.unit_of_measure} of {stock_item.name} to {patient.full_name} ({patient.hospice_number})."
                )
                return redirect('operations:pharmacy_dispense')
            except Exception as e:
                form.add_error(None, str(e))

        stock_items = list(StockItem.objects.all().order_by('name').values('id', 'name', 'item_code', 'quantity_on_hand', 'unit_of_measure', 'is_controlled_substance'))
        return render(request, 'operations/pharmacy_dispense.html', {
            'form': form,
            'stock_items_json': json.dumps([
                {**item, 'id': str(item['id'])} for item in stock_items
            ]),
            'recent_dispenses': StockMovement.objects.filter(movement_type=MovementTypeChoices.DISPENSE).select_related('stock_item', 'recorded_by', 'patient', 'medication_statement')[:15],
        })


class StockMovementListView(ManagerRequiredMixin, ListView):
    model = StockMovement
    template_name = 'operations/stock_movement_list.html'
    context_object_name = 'movements'
    paginate_by = 25

    def get_queryset(self):
        qs = StockMovement.objects.select_related('stock_item', 'recorded_by').order_by('-created_at')
        movement_type = self.request.GET.get('type')
        if movement_type:
            qs = qs.filter(movement_type=movement_type)
        return qs


class DiseaseAnalyticsView(ManagerRequiredMixin, View):
    def get(self, request):
        data = get_disease_analytics_data()
        return render(request, 'operations/disease_analytics.html', data)


# ==============================================================================
# INVOICING & FINANCIAL BILLING VIEWS
# ==============================================================================

class InvoiceListView(ManagerRequiredMixin, ListView):
    model = Invoice
    template_name = 'operations/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20

    def get_queryset(self):
        qs = Invoice.objects.select_related('vendor', 'patient', 'procurement_order', 'created_by').order_by('-issue_date', '-created_at')
        inv_type = self.request.GET.get('type')
        status = self.request.GET.get('status')
        query = self.request.GET.get('q')

        if inv_type:
            qs = qs.filter(invoice_type=inv_type)
        if status:
            qs = qs.filter(status=status)
        if query:
            qs = qs.filter(
                Q(invoice_number__icontains=query) |
                Q(vendor__name__icontains=query) |
                Q(patient__first_name__icontains=query) |
                Q(patient__last_name__icontains=query) |
                Q(patient__hospice_number__icontains=query)
            )
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # SQL-side aggregation; the invoice_paid_not_over_total constraint
        # guarantees billed - collected equals the sum of per-invoice balances.
        totals = Invoice.objects.aggregate(
            total_billed=Sum('total_amount_kes'),
            total_collected=Sum('amount_paid_kes'),
        )
        total_billed = totals['total_billed'] or Decimal('0.00')
        total_collected = totals['total_collected'] or Decimal('0.00')
        context['total_invoices_count'] = Invoice.objects.count()
        context['total_billed_kes'] = total_billed
        context['total_collected_kes'] = total_collected
        context['outstanding_balance_kes'] = total_billed - total_collected
        context['current_type'] = self.request.GET.get('type', '')
        context['current_status'] = self.request.GET.get('status', '')
        context['search_query'] = self.request.GET.get('q', '')
        return context


class InvoiceCreateView(ManagerRequiredMixin, View):
    def get(self, request):
        po_id = request.GET.get('po_id')
        patient_id = request.GET.get('patient_id')
        initial = {
            'invoice_number': '',
            'issue_date': timezone.now().date(),
        }
        if po_id:
            try:
                po = ProcurementOrder.objects.get(pk=po_id)
                initial['procurement_order'] = po
                initial['vendor'] = po.vendor
                initial['invoice_type'] = InvoiceTypeChoices.SUPPLIER_PURCHASE
                initial['total_amount_kes'] = po.total_amount_kes
                initial['subtotal_amount_kes'] = po.total_amount_kes
            except ProcurementOrder.DoesNotExist:
                pass
        elif patient_id:
            try:
                patient = Patient.objects.get(pk=patient_id)
                initial['patient'] = patient
                initial['invoice_type'] = InvoiceTypeChoices.PATIENT_SERVICE
            except Patient.DoesNotExist:
                pass

        form = InvoiceForm(initial=initial)
        return render(request, 'operations/invoice_form.html', {'form': form})

    def post(self, request):
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            invoice.created_by = request.user
            invoice.save()

            # If created from a PO, copy line items
            if invoice.procurement_order and invoice.procurement_order.items.exists():
                for po_item in invoice.procurement_order.items.all():
                    InvoiceLineItem.objects.create(
                        invoice=invoice,
                        stock_item=po_item.stock_item,
                        description=f"{po_item.stock_item.name} ({po_item.stock_item.item_code})",
                        quantity=po_item.quantity_requested,
                        unit_price_kes=po_item.unit_price_kes,
                        total_price_kes=po_item.total_price_kes,
                    )
            elif invoice.total_amount_kes > 0 and not invoice.items.exists():
                desc = invoice.notes or ("Supplier Procurement Requisition" if invoice.vendor else "Palliative Care Clinical Services")
                InvoiceLineItem.objects.create(
                    invoice=invoice,
                    description=desc,
                    quantity=1,
                    unit_price_kes=invoice.total_amount_kes,
                    total_price_kes=invoice.total_amount_kes,
                )

            messages.success(request, f"Invoice {invoice.invoice_number} created successfully.")
            return redirect('operations:invoice_detail', pk=invoice.pk)
        return render(request, 'operations/invoice_form.html', {'form': form})


class InvoiceDetailView(ManagerRequiredMixin, View):
    def get(self, request, pk):
        invoice = get_object_or_404(
            Invoice.objects.select_related('vendor', 'patient', 'procurement_order', 'created_by').prefetch_related('items'),
            pk=pk
        )
        payment_form = InvoicePaymentForm(instance=invoice)
        item_form = InvoiceLineItemForm()
        return render(request, 'operations/invoice_detail.html', {
            'invoice': invoice,
            'payment_form': payment_form,
            'item_form': item_form,
        })

    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        payment_form = InvoicePaymentForm(request.POST, instance=invoice)
        if payment_form.is_valid():
            with transaction.atomic():
                # Prevent two payment updates from overwriting each other.
                locked_invoice = Invoice.objects.select_for_update().get(pk=pk)
                payment_form = InvoicePaymentForm(request.POST, instance=locked_invoice)
                if not payment_form.is_valid():
                    return render(request, 'operations/invoice_detail.html', {
                        'invoice': locked_invoice,
                        'payment_form': payment_form,
                        'item_form': InvoiceLineItemForm(),
                    })
                inv = payment_form.save(commit=False)
                # A paid invoice must be financially reconciled as well as
                # visually marked paid. This keeps the detail page, list, and
                # generated PDF consistent when staff select the Paid status.
                if inv.status == PaymentStatusChoices.PAID and inv.total_amount_kes > 0:
                    inv.amount_paid_kes = inv.total_amount_kes
                if inv.amount_paid_kes >= inv.total_amount_kes and inv.total_amount_kes > 0:
                    inv.status = PaymentStatusChoices.PAID
                elif inv.amount_paid_kes > 0:
                    inv.status = PaymentStatusChoices.PARTIALLY_PAID
                inv.save()

            log_audit_event(
                user=request.user,
                action=AuditAction.UPDATE,
                resource_type='Invoice Payment',
                resource_id=str(inv.pk),
                summary=f"Recorded payment of KES {inv.amount_paid_kes:,.2f} for Invoice {inv.invoice_number} via {inv.payment_method} (Ref: {inv.payment_reference or 'N/A'})",
                metadata={
                    'invoice_number': inv.invoice_number,
                    'amount_paid_kes': str(inv.amount_paid_kes),
                    'payment_method': inv.payment_method,
                    'payment_reference': inv.payment_reference,
                    'status': inv.status,
                },
                request=request,
            )

            messages.success(request, f"Payment recorded for Invoice {inv.invoice_number}.")
            return redirect('operations:invoice_detail', pk=pk)
        item_form = InvoiceLineItemForm()
        return render(request, 'operations/invoice_detail.html', {
            'invoice': invoice,
            'payment_form': payment_form,
            'item_form': item_form,
        })


class InvoiceAddLineItemView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        invoice = get_object_or_404(Invoice, pk=pk)
        item_form = InvoiceLineItemForm(request.POST)
        if item_form.is_valid():
            with transaction.atomic():
                invoice = Invoice.objects.select_for_update().get(pk=pk)
                line_item = item_form.save(commit=False)
                line_item.invoice = invoice
                line_item.save()

                # Recalculate the invoice total while holding the invoice lock.
                items_total = sum(i.total_price_kes for i in invoice.items.all())
                invoice.subtotal_amount_kes = items_total
                invoice.total_amount_kes = max(Decimal('0.00'), items_total + invoice.tax_amount_kes - invoice.discount_amount_kes)
                invoice.save(update_fields=['subtotal_amount_kes', 'total_amount_kes', 'updated_at'])

            messages.success(request, f"Added line item: {line_item.description}")
        else:
            messages.error(request, "Failed to add line item. Check form fields.")
        return redirect('operations:invoice_detail', pk=pk)


class InvoicePdfView(ManagerRequiredMixin, View):
    def get(self, request, pk):
        from django.http import HttpResponse

        from .pdf_generator import generate_invoice_pdf

        invoice = get_object_or_404(
            Invoice.objects.select_related('vendor', 'patient', 'procurement_order', 'created_by').prefetch_related('items'),
            pk=pk
        )
        pdf_buffer = generate_invoice_pdf(invoice)
        response = HttpResponse(pdf_buffer.getvalue(), content_type='application/pdf')
        filename = f"Invoice_{invoice.invoice_number}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response


class PatientDeletionRequestListView(ManagerRequiredMixin, ListView):
    model = PatientDeletionRequest
    template_name = 'operations/deletion_requests_list.html'
    context_object_name = 'deletion_requests'
    paginate_by = 20

    def get_queryset(self):
        qs = PatientDeletionRequest.objects.select_related('requested_by', 'reviewed_by').order_by('-created_at')
        status = self.request.GET.get('status')
        if status:
            qs = qs.filter(status=status)
        return qs

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        status = self.request.GET.get('status')
        current_tab = self.request.GET.get('tab', 'patients')
        
        # Appointment deletion requests
        appt_qs = AppointmentDeletionRequest.objects.select_related('requested_by', 'reviewed_by').order_by('-created_at')
        if status:
            appt_qs = appt_qs.filter(status=status)
            
        context['appointment_deletion_requests'] = appt_qs
        context['current_tab'] = current_tab
        
        # Patient counts
        context['pending_count'] = PatientDeletionRequest.objects.filter(status=DeletionRequestStatusChoices.PENDING).count()
        context['approved_count'] = PatientDeletionRequest.objects.filter(status=DeletionRequestStatusChoices.APPROVED).count()
        context['rejected_count'] = PatientDeletionRequest.objects.filter(status=DeletionRequestStatusChoices.REJECTED).count()
        
        # Appointment counts
        context['appt_pending_count'] = AppointmentDeletionRequest.objects.filter(status=DeletionRequestStatusChoices.PENDING).count()
        context['appt_approved_count'] = AppointmentDeletionRequest.objects.filter(status=DeletionRequestStatusChoices.APPROVED).count()
        context['appt_rejected_count'] = AppointmentDeletionRequest.objects.filter(status=DeletionRequestStatusChoices.REJECTED).count()
        
        context['selected_status'] = self.request.GET.get('status', '')
        return context


class PatientDeletionRequestApproveView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        deletion_req = get_object_or_404(PatientDeletionRequest, pk=pk)
        
        if deletion_req.status != DeletionRequestStatusChoices.PENDING:
            messages.warning(request, f"This deletion request has already been {deletion_req.get_status_display().lower()}.")
            return redirect('operations:deletion_requests')

        review_notes = request.POST.get('review_notes', '').strip()

        with transaction.atomic():
            patient = deletion_req.patient
            patient_name = deletion_req.patient_name
            hospice_number = deletion_req.hospice_number

            deletion_req.status = DeletionRequestStatusChoices.APPROVED
            deletion_req.reviewed_by = request.user
            deletion_req.reviewed_at = timezone.now()
            deletion_req.review_notes = review_notes
            deletion_req.save()

            if patient:
                from apps.patients.models import PatientStatusChoices
                patient.status = PatientStatusChoices.CLOSED
                closure_note = f"File closed and archived via approved deletion request. Justification: {deletion_req.reason}. Reviewer notes: {review_notes}"
                patient.notes = f"{patient.notes}\n\n{closure_note}".strip() if patient.notes else closure_note
                patient.file_closed = "Yes"
                patient.closure_date = timezone.now().date()
                patient.save(update_fields=['status', 'notes', 'file_closed', 'closure_date', 'updated_at'])

                # Log audit trail
                log_audit_event(
                    action=AuditAction.DELETE,
                    resource_type='Patient',
                    resource_id=str(patient.id),
                    summary=f"Approved deletion request and closed/archived patient file for {patient_name} ({hospice_number}). Justification: {deletion_req.reason}. Reviewer notes: {review_notes}",
                    user=request.user,
                )

        messages.success(
            request,
            f"Patient record for {patient_name} ({hospice_number}) has been closed, archived, and updated in audit records."
        )
        return redirect('operations:deletion_requests')


class PatientDeletionRequestRejectView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        deletion_req = get_object_or_404(PatientDeletionRequest, pk=pk)
        
        if deletion_req.status != DeletionRequestStatusChoices.PENDING:
            messages.warning(request, f"This deletion request has already been {deletion_req.get_status_display().lower()}.")
            return redirect('operations:deletion_requests')

        review_notes = request.POST.get('review_notes', '').strip()

        deletion_req.status = DeletionRequestStatusChoices.REJECTED
        deletion_req.reviewed_by = request.user
        deletion_req.reviewed_at = timezone.now()
        deletion_req.review_notes = review_notes
        deletion_req.save()

        log_audit_event(
            action=AuditAction.UPDATE,
            resource_type='PatientDeletionRequest',
            resource_id=str(deletion_req.id),
            summary=f"Rejected deletion request for patient {deletion_req.patient_name} ({deletion_req.hospice_number}). Reason: {review_notes}",
            user=request.user,
        )

        messages.info(
            request,
            f"Deletion request for {deletion_req.patient_name} ({deletion_req.hospice_number}) has been rejected."
        )
        return redirect('operations:deletion_requests')


class AppointmentDeletionRequestApproveView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        deletion_req = get_object_or_404(AppointmentDeletionRequest, pk=pk)
        
        if deletion_req.status != DeletionRequestStatusChoices.PENDING:
            messages.warning(request, f"This deletion request has already been {deletion_req.get_status_display().lower()}.")
            return redirect(f"{redirect('operations:deletion_requests').url}?tab=appointments")

        review_notes = request.POST.get('review_notes', '').strip()

        with transaction.atomic():
            appt = deletion_req.appointment
            patient_name = deletion_req.patient_name
            sched_date = deletion_req.scheduled_date

            deletion_req.status = DeletionRequestStatusChoices.APPROVED
            deletion_req.reviewed_by = request.user
            deletion_req.reviewed_at = timezone.now()
            deletion_req.review_notes = review_notes
            deletion_req.save()

            if appt:
                from apps.appointments.models import AppointmentStatusChoices
                appt.status = AppointmentStatusChoices.CANCELLED
                cancellation_note = f"Cancelled via approved deletion request. Justification: {deletion_req.reason}. Reviewer notes: {review_notes}"
                appt.notes = f"{appt.notes}\n\n{cancellation_note}".strip() if appt.notes else cancellation_note
                appt.save(update_fields=['status', 'notes', 'updated_at'])

                # Log audit trail
                log_audit_event(
                    action=AuditAction.DELETE,
                    resource_type='Appointment',
                    resource_id=str(appt.id),
                    summary=f"Approved deletion request and cancelled appointment for {patient_name} scheduled on {sched_date}. Justification: {deletion_req.reason}. Reviewer notes: {review_notes}",
                    user=request.user,
                )

        messages.success(
            request,
            f"Appointment for {patient_name} on {sched_date} has been cancelled and archived in audit records."
        )
        return redirect(f"{redirect('operations:deletion_requests').url}?tab=appointments")


class AppointmentDeletionRequestRejectView(ManagerRequiredMixin, View):
    def post(self, request, pk):
        deletion_req = get_object_or_404(AppointmentDeletionRequest, pk=pk)
        
        if deletion_req.status != DeletionRequestStatusChoices.PENDING:
            messages.warning(request, f"This deletion request has already been {deletion_req.get_status_display().lower()}.")
            return redirect(f"{redirect('operations:deletion_requests').url}?tab=appointments")

        review_notes = request.POST.get('review_notes', '').strip()

        deletion_req.status = DeletionRequestStatusChoices.REJECTED
        deletion_req.reviewed_by = request.user
        deletion_req.reviewed_at = timezone.now()
        deletion_req.review_notes = review_notes
        deletion_req.save()

        log_audit_event(
            action=AuditAction.UPDATE,
            resource_type='AppointmentDeletionRequest',
            resource_id=str(deletion_req.id),
            summary=f"Rejected appointment deletion request for {deletion_req.patient_name} on {deletion_req.scheduled_date}. Reason: {review_notes}",
            user=request.user,
        )

        messages.info(
            request,
            f"Deletion request for {deletion_req.patient_name}'s appointment on {deletion_req.scheduled_date} has been rejected."
        )
        return redirect(f"{redirect('operations:deletion_requests').url}?tab=appointments")
