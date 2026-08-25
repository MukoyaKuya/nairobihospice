import pytest
from django.test import Client

from apps.accounts.models import RoleChoices
from apps.accounts.services import create_staff_user
from apps.operations.models import (
    Invoice,
    InvoiceTypeChoices,
    MovementTypeChoices,
    PaymentMethodChoices,
    PaymentStatusChoices,
    StockItem,
    StockMovement,
    Vendor,
)
from apps.operations.services import record_stock_movement
from apps.patients.services import register_patient


@pytest.mark.django_db
class TestOperationsSuite:
    def setup_method(self):
        self.manager = create_staff_user(
            email='mgr_test@nairobihospice.or.ke',
            username='mgr_test',
            first_name='Operations',
            last_name='Manager',
            password='Pass!',
            role=RoleChoices.MANAGER,
        )
        self.receptionist = create_staff_user(
            email='rec_test@nairobihospice.or.ke',
            username='rec_test',
            first_name='Front',
            last_name='Desk',
            password='Pass!',
            role=RoleChoices.RECEPTIONIST,
        )
        self.client_manager = Client()
        self.client_manager.force_login(self.manager)

        self.client_receptionist = Client()
        self.client_receptionist.force_login(self.receptionist)

    def test_manager_can_access_operations_dashboard(self):
        response = self.client_manager.get('/operations/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Operations Management &amp; Supply Command' in content or 'Operations Management & Supply Command' in content
        assert 'Stock Reorder Alerts' in content

    def test_receptionist_denied_operations_dashboard(self):
        response = self.client_receptionist.get('/operations/')
        assert response.status_code == 403

    def test_vendor_and_procurement_workflow(self):
        # 1. Create Vendor
        v_response = self.client_manager.post('/operations/vendors/create/', {
            'name': 'Med Supply Kenya',
            'code': 'VND-MED-99',
            'category': 'PHARMACEUTICAL',
            'contact_person': 'Jane Doe',
            'phone_number': '+254 700 111 222',
            'email': 'sales@medsupply.ke',
            'kra_pin': 'P059999999Z',
            'payment_terms': '30 Days Net',
            'status': 'ACTIVE',
            'physical_address': 'Industrial Area',
        })
        assert v_response.status_code == 302
        assert Vendor.objects.filter(code='VND-MED-99').exists()
        vendor = Vendor.objects.get(code='VND-MED-99')

        # 2. Create Stock Item
        s_response = self.client_manager.post('/operations/inventory/create/', {
            'item_code': 'STK-AMIT-25',
            'name': 'Amitriptyline Tablets 25mg',
            'category': 'ESSENTIAL_MEDICINE',
            'unit_of_measure': 'Packs of 100',
            'quantity_on_hand': 20,
            'minimum_reorder_level': 5,
            'unit_cost_kes': '450.00',
            'preferred_vendor': str(vendor.id),
            'location_bin': 'Rack B1',
        })
        assert s_response.status_code == 302
        assert StockItem.objects.filter(item_code='STK-AMIT-25').exists()
        item = StockItem.objects.get(item_code='STK-AMIT-25')
        assert item.quantity_on_hand == 20

        # 3. Record Stock Receive
        rcv_response = self.client_manager.post('/operations/inventory/receive/', {
            'stock_item': str(item.id),
            'quantity': 30,
            'reference_document': 'DELIVERY-NOTE-001',
            'notes': 'Quarterly restock',
        })
        assert rcv_response.status_code == 302
        item.refresh_from_db()
        assert item.quantity_on_hand == 50

    def test_stock_movement_ledger_integrity(self):
        vendor = Vendor.objects.create(name='Test V', code='VND-T1', contact_person='C', phone_number='0700')
        item = StockItem.objects.create(
            item_code='STK-TEST-01',
            name='Test Gauze 10m',
            unit_of_measure='Rolls',
            quantity_on_hand=10,
            minimum_reorder_level=3,
            unit_cost_kes=100.00,
            preferred_vendor=vendor
        )

        from apps.patients.services import register_patient
        from apps.medications.models import MedicationStatement, MedicationStatusChoices
        patient = register_patient(first_name='Ledger', last_name='Patient', created_by=self.manager)
        med = MedicationStatement.objects.create(
            patient=patient,
            medication_name='Test Gauze 10m',
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.manager,
        )

        # Dispense 4 units
        mov = record_stock_movement(
            stock_item=item,
            movement_type=MovementTypeChoices.DISPENSE,
            quantity=4,
            reference_document='PATIENT-001',
            patient=patient,
            medication_statement=med,
            user=self.manager,
        )
        assert mov.balance_after == 6
        item.refresh_from_db()
        assert item.quantity_on_hand == 6

    def test_pharmacy_dispense_screen_creates_movement_and_audit(self):
        vendor = Vendor.objects.create(name='Pharma V', code='VND-P1', contact_person='C', phone_number='0700')
        morphine = StockItem.objects.create(
            item_code='STK-MPH-10',
            name='Oral Morphine Solution 10mg/5ml',
            unit_of_measure='Bottles',
            quantity_on_hand=25,
            minimum_reorder_level=5,
            unit_cost_kes=650.00,
            preferred_vendor=vendor,
            is_controlled_substance=True,
        )
        patient = register_patient(
            first_name='Faith',
            last_name='Wambui',
            county='Nairobi',
            created_by=self.manager,
        )
        from apps.medications.models import MedicationStatement, MedicationStatusChoices
        med = MedicationStatement.objects.create(
            patient=patient,
            medication_name='Oral Morphine Solution 10mg/5ml',
            dosage='5mg',
            route='ORAL',
            frequency='q4h',
            status=MedicationStatusChoices.ACTIVE,
            prescriber=self.manager,
        )

        response = self.client_manager.post('/operations/pharmacy/dispense/', {
            'stock_item': str(morphine.id),
            'patient': str(patient.id),
            'medication_statement': str(med.id),
            'quantity': 3,
            'notes': 'Severe pain flare protocol',
        })
        assert response.status_code == 302
        morphine.refresh_from_db()
        assert morphine.quantity_on_hand == 22

        mov = StockMovement.objects.filter(stock_item=morphine, movement_type=MovementTypeChoices.DISPENSE).first()
        assert mov is not None
        assert mov.quantity == 3
        assert mov.patient == patient
        assert mov.medication_statement == med
        assert mov.recorded_by == self.manager
        assert 'Faith Wambui' in mov.reference_document

    def test_disease_analytics_view_aggregates_data(self):
        register_patient(
            first_name='Amina',
            last_name='Hassan',
            primary_diagnosis='Cervical Carcinoma Stage IV',
            county='Nairobi',
            created_by=self.manager,
        )
        register_patient(
            first_name='Patrick',
            last_name='Njoroge',
            primary_diagnosis='Prostate Carcinoma',
            county='Kiambu',
            created_by=self.manager,
        )

        response = self.client_manager.get('/operations/disease-analytics/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Cross-Platform Disease &amp; Oncology' in content or 'Cross-Platform Disease & Oncology' in content
        assert 'Cervical Carcinoma' in content or 'Prostate Carcinoma' in content

    def test_invoice_create_get_view(self):
        response = self.client_manager.get('/operations/invoices/create/')
        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert 'Issue New Financial Invoice' in content

    def test_invoice_creation_and_payment_recording(self):
        from apps.operations.models import PaymentMethodChoices
        vendor = Vendor.objects.create(name='Pharma Supplies KE', code='VND-PH-01', contact_person='Jane', phone_number='0711')
        inv_response = self.client_manager.post('/operations/invoices/create/', {
            'invoice_number': 'INV-TEST-0001',
            'invoice_type': 'SUPPLIER_PURCHASE',
            'vendor': str(vendor.id),
            'issue_date': '2026-08-21',
            'status': 'ISSUED',
            'subtotal_amount_kes': '25000.00',
            'tax_amount_kes': '0.00',
            'discount_amount_kes': '0.00',
            'total_amount_kes': '25000.00',
            'amount_paid_kes': '0.00',
            'payment_method': PaymentMethodChoices.BANK_TRANSFER,
            'payment_reference': '',
            'notes': 'Test batch invoice',
        })
        assert inv_response.status_code == 302
        from apps.operations.models import Invoice
        assert Invoice.objects.filter(invoice_number='INV-TEST-0001').exists()
        inv = Invoice.objects.get(invoice_number='INV-TEST-0001')
        assert inv.balance_due_kes == 25000.00

        # Record payment
        pay_response = self.client_manager.post(f'/operations/invoices/{inv.pk}/', {
            'amount_paid_kes': '25000.00',
            'status': 'PAID',
            'payment_method': PaymentMethodChoices.BANK_TRANSFER,
            'payment_reference': 'TX-998811',
            'notes': 'Paid in full',
        })
        assert pay_response.status_code == 302
        inv.refresh_from_db()
        assert inv.status == 'PAID'
        assert inv.amount_paid_kes == inv.total_amount_kes

    def test_paid_status_reconciles_full_invoice_amount(self):
        vendor = Vendor.objects.create(
            name='Paid Status Vendor',
            code='VND-PAID-01',
            contact_person='Accounts Desk',
            phone_number='0700000000',
        )
        invoice = Invoice.objects.create(
            invoice_number='INV-PAID-STATUS',
            invoice_type=InvoiceTypeChoices.SUPPLIER_PURCHASE,
            vendor=vendor,
            total_amount_kes=68500.00,
            amount_paid_kes=0.00,
            status=PaymentStatusChoices.ISSUED,
            created_by=self.manager,
        )

        response = self.client_manager.post(f'/operations/invoices/{invoice.pk}/', {
            'amount_paid_kes': '0.00',
            'status': PaymentStatusChoices.PAID,
            'payment_method': PaymentMethodChoices.CASH,
            'payment_reference': 'CASH-PAID-001',
            'notes': 'Settled in full.',
        })

        assert response.status_code == 302
        invoice.refresh_from_db()
        assert invoice.status == PaymentStatusChoices.PAID
        assert invoice.amount_paid_kes == invoice.total_amount_kes
        assert invoice.balance_due_kes == 0

    def test_invoice_pdf_generation_response(self):
        from apps.operations.models import Invoice, InvoiceLineItem, InvoiceTypeChoices

        # 1. Test Patient Clinical Invoice PDF
        patient = register_patient(
            first_name='Zainab',
            last_name='Ali',
            primary_diagnosis='Oesophageal Carcinoma',
            created_by=self.manager
        )
        p_inv = Invoice.objects.create(
            invoice_number='INV-PATIENT-PDF',
            invoice_type=InvoiceTypeChoices.PATIENT_SERVICE,
            patient=patient,
            total_amount_kes=5000.00,
            amount_paid_kes=5000.00,
            status='PAID',
            created_by=self.manager,
        )
        InvoiceLineItem.objects.create(
            invoice=p_inv,
            description='Comprehensive MDT Palliative Consultation',
            quantity=1,
            unit_price_kes=5000.00,
            total_price_kes=5000.00,
        )
        p_pdf = self.client_manager.get(f'/operations/invoices/{p_inv.pk}/pdf/')
        assert p_pdf.status_code == 200
        assert p_pdf['Content-Type'] == 'application/pdf'
        assert b'%PDF' in p_pdf.content[:10]

        # 2. Test Supplier Purchase Voucher PDF
        vendor = Vendor.objects.create(name='Harleys Ltd', code='VND-HARL-01', contact_person='Moses', phone_number='0722')
        s_inv = Invoice.objects.create(
            invoice_number='VOUCHER-SUPPLIER-PDF',
            invoice_type=InvoiceTypeChoices.SUPPLIER_PURCHASE,
            vendor=vendor,
            total_amount_kes=45000.00,
            amount_paid_kes=0.00,
            status='ISSUED',
            created_by=self.manager,
        )
        InvoiceLineItem.objects.create(
            invoice=s_inv,
            description='Oral Morphine 10mg/5ml Syrup (500ml) x 50',
            quantity=50,
            unit_price_kes=900.00,
            total_price_kes=45000.00,
        )
        s_pdf = self.client_manager.get(f'/operations/invoices/{s_inv.pk}/pdf/')
        assert s_pdf.status_code == 200
        assert s_pdf['Content-Type'] == 'application/pdf'
        assert b'%PDF' in s_pdf.content[:10]
        assert s_pdf['Cache-Control'] == 'private, no-store, max-age=0, must-revalidate'
        assert s_pdf['X-Content-Type-Options'] == 'nosniff'

    def test_controlled_substances_register_export_endpoint(self):
        """Controlled substance export streams a valid PPB-compliant CSV ledger with patient and Rx FKs."""
        from apps.medications.models import MedicationStatement, MedicationStatusChoices
        from apps.patients.services import register_patient

        doctor = create_staff_user(
            email='doc_export@nairobihospice.or.ke',
            username='doc_export',
            first_name='Dr',
            last_name='Export',
            password='Pass!',
            role=RoleChoices.DOCTOR,
        )
        patient = register_patient(first_name='Mary', last_name='Export', created_by=doctor)
        med = MedicationStatement.objects.create(
            patient=patient,
            medication_name="Oral Morphine 10mg/5ml",
            status=MedicationStatusChoices.ACTIVE,
            prescriber=doctor,
        )
        stock_item = StockItem.objects.create(
            name="Oral Morphine 10mg/5ml",
            item_code="STK-OPIOID-EXPORT",
            quantity_on_hand=50,
            unit_of_measure="bottle",
            is_controlled_substance=True,
        )
        record_stock_movement(
            stock_item=stock_item,
            movement_type=MovementTypeChoices.DISPENSE,
            quantity=2,
            patient=patient,
            medication_statement=med,
            user=doctor,
            notes="Dispensed for breakthrough pain",
        )

        resp = self.client_manager.get('/operations/pharmacy/controlled-register/export/')
        assert resp.status_code == 200
        assert resp['Content-Type'] == 'text/csv'
        assert 'attachment; filename="ppb_controlled_substances_register_' in resp['Content-Disposition']
        content = resp.content.decode('utf-8')
        assert 'Controlled Substance Name' in content
        assert 'STK-OPIOID-EXPORT' in content
        assert 'Mary Export' in content
        assert 'Oral Morphine 10mg/5ml' in content
