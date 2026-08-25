from django import forms

from .models import (
    Invoice,
    InvoiceLineItem,
    ProcurementOrder,
    StockItem,
    Vendor,
)


class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = ['name', 'code', 'category', 'contact_person', 'phone_number', 'email', 'kra_pin', 'physical_address', 'payment_terms', 'status', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. Kenya Medical Supplies Authority (KEMSA)'}),
            'code': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. VND-KEMSA-01'}),
            'category': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'contact_person': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Key Account Manager'}),
            'phone_number': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': '+254 720 000 000'}),
            'email': forms.EmailInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'orders@supplier.co.ke'}),
            'kra_pin': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'P051234567Z'}),
            'physical_address': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Industrial Area, Commercial Street, Nairobi'}),
            'payment_terms': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. 30 Days Net'}),
            'status': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Special discount agreements, delivery terms...'}),
        }


class StockItemForm(forms.ModelForm):
    class Meta:
        model = StockItem
        fields = ['item_code', 'name', 'category', 'unit_of_measure', 'quantity_on_hand', 'minimum_reorder_level', 'unit_cost_kes', 'preferred_vendor', 'location_bin', 'is_controlled_substance']
        widgets = {
            'item_code': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. STK-MED-042'}),
            'name': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. Oral Morphine Solution 10mg/5ml (500ml)'}),
            'category': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'unit_of_measure': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. Bottles, Boxes, Vials, Packs'}),
            'quantity_on_hand': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'minimum_reorder_level': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'unit_cost_kes': forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'preferred_vendor': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'location_bin': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. Pharmacy Cold Room Shelf B'}),
            'is_controlled_substance': forms.CheckboxInput(attrs={'class': 'rounded border-slate-300 text-[#002D62] focus:ring-[#002D62] h-4 w-4'}),
        }


class ProcurementOrderForm(forms.ModelForm):
    class Meta:
        model = ProcurementOrder
        fields = ['po_number', 'vendor', 'order_date', 'expected_delivery_date', 'status', 'total_amount_kes', 'invoice_number', 'notes']
        widgets = {
            'po_number': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. PO-2026-0089'}),
            'vendor': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'order_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'expected_delivery_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'status': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'total_amount_kes': forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'invoice_number': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Supplier Invoice #'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Delivery instructions, grant funding code...'}),
        }

    def clean_total_amount_kes(self):
        amount = self.cleaned_data['total_amount_kes']
        if amount < 0:
            raise forms.ValidationError('Procurement total cannot be negative.')
        return amount


class StockReceiveForm(forms.Form):
    stock_item = forms.ModelChoiceField(
        queryset=StockItem.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'})
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Units received'})
    )
    reference_document = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. PO-2026-0042 / Delivery Note #'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Batch number, expiration date, inspection remarks...'})
    )


class StockDispenseForm(forms.Form):
    stock_item = forms.ModelChoiceField(
        queryset=StockItem.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white', 'id': 'id_dispense_stock_item'})
    )
    patient = forms.ModelChoiceField(
        queryset=None,
        required=True,
        widget=forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'})
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Units / Doses to dispense'})
    )
    medication_statement = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Optional: Medication Statement Ref / Prescription #'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Dispensing remarks, dosage instructions, or opioid register entry...'})
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from apps.patients.models import Patient
        self.fields['patient'].queryset = Patient.objects.filter(status='ACTIVE').order_by('first_name', 'last_name')


class InvoiceForm(forms.ModelForm):
    invoice_number = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg bg-slate-50 text-slate-600 font-mono focus:outline-none',
            'placeholder': 'Auto-Generated upon saving (e.g. INV-2026-0115 / VOU-2026-0042)',
            'readonly': 'readonly'
        })
    )

    class Meta:
        model = Invoice
        fields = [
            'invoice_number', 'invoice_type', 'vendor', 'patient', 'procurement_order',
            'issue_date', 'due_date', 'status', 'subtotal_amount_kes', 'tax_amount_kes',
            'discount_amount_kes', 'total_amount_kes', 'amount_paid_kes', 'payment_method',
            'payment_reference', 'notes'
        ]
        widgets = {
            'invoice_number': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. INV-2026-0104'}),
            'invoice_type': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'vendor': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'patient': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'procurement_order': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'issue_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'status': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'subtotal_amount_kes': forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'tax_amount_kes': forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'discount_amount_kes': forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'total_amount_kes': forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'amount_paid_kes': forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'payment_method': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'payment_reference': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Transaction ID / Cheque #'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Terms, subsidy notes, grant billing code...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        total = cleaned_data.get('total_amount_kes')
        paid = cleaned_data.get('amount_paid_kes')
        if total is not None and total < 0:
            self.add_error('total_amount_kes', 'Invoice total cannot be negative.')
        if paid is not None and paid < 0:
            self.add_error('amount_paid_kes', 'Payment amount cannot be negative.')
        if total is not None and paid is not None and paid > total:
            self.add_error('amount_paid_kes', 'Payment cannot exceed the invoice total.')
        return cleaned_data


class InvoicePaymentForm(forms.ModelForm):
    class Meta:
        model = Invoice
        fields = ['amount_paid_kes', 'status', 'payment_method', 'payment_reference', 'notes']
        widgets = {
            'amount_paid_kes': forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'status': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'payment_method': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
            'payment_reference': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'e.g. M-Pesa Ref QK881290'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Payment receipt notes...'}),
        }

    def clean_amount_paid_kes(self):
        amount = self.cleaned_data['amount_paid_kes']
        if amount < 0:
            raise forms.ValidationError('Payment amount cannot be negative.')
        if self.instance and amount > self.instance.total_amount_kes:
            raise forms.ValidationError('Payment cannot exceed the invoice total.')
        return amount


class InvoiceLineItemForm(forms.ModelForm):
    quantity = forms.IntegerField(min_value=1)
    unit_price_kes = forms.DecimalField(min_value=0, max_digits=12, decimal_places=2)

    class Meta:
        model = InvoiceLineItem
        fields = ['description', 'quantity', 'unit_price_kes', 'stock_item']
        widgets = {
            'description': forms.TextInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none', 'placeholder': 'Item description / service name'}),
            'quantity': forms.NumberInput(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'unit_price_kes': forms.NumberInput(attrs={'step': '0.01', 'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none'}),
            'stock_item': forms.Select(attrs={'class': 'w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:ring-2 focus:ring-[#002D62] focus:border-[#002D62] focus:outline-none bg-white'}),
        }
