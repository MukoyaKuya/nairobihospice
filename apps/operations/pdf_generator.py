import io
import os

from django.conf import settings
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import (
    Image as RLImage,
)


def _get_hospice_logo():
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'hospice_symbol.png')
    if os.path.exists(logo_path):
        return RLImage(logo_path, width=22 * mm, height=19.5 * mm)
    return None


def generate_patient_invoice_pdf(invoice) -> io.BytesIO:
    """
    Renders a warm, clinical, and empathetic Patient Tax Invoice & Official Receipt.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
    )

    navy_color = colors.HexColor('#002D62')
    burgundy_color = colors.HexColor('#991B1B')
    slate_dark = colors.HexColor('#0F172A')
    slate_body = colors.HexColor('#334155')
    slate_muted = colors.HexColor('#64748B')
    slate_light = colors.HexColor('#F8FAFC')
    border_color = colors.HexColor('#E2E8F0')

    title_style = ParagraphStyle('PatientDocTitle', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=navy_color)
    motto_style = ParagraphStyle('PatientMotto', fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=burgundy_color)
    contact_text = ParagraphStyle('PatientContact', fontName='Helvetica', fontSize=7.5, leading=10.5, textColor=slate_muted)

    doc_heading = ParagraphStyle('PatientDocHeading', fontName='Helvetica-Bold', fontSize=12, leading=15, alignment=TA_RIGHT, textColor=navy_color)
    doc_number = ParagraphStyle('PatientDocNo', fontName='Helvetica-Bold', fontSize=10.5, leading=13, alignment=TA_RIGHT, textColor=navy_color)
    header_meta = ParagraphStyle('PatientHeaderMeta', fontName='Helvetica', fontSize=8, leading=11.5, alignment=TA_RIGHT, textColor=slate_body)

    section_heading = ParagraphStyle('PatientSecHead', fontName='Helvetica-Bold', fontSize=8.5, leading=12, textColor=navy_color)
    card_label = ParagraphStyle('PatientCardLabel', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=slate_dark)
    card_text = ParagraphStyle('PatientCardText', fontName='Helvetica', fontSize=8, leading=11, textColor=slate_body)

    table_header = ParagraphStyle('PatientTH', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white)
    table_cell = ParagraphStyle('PatientTC', fontName='Helvetica', fontSize=8, leading=11, textColor=slate_dark)
    table_cell_center = ParagraphStyle('PatientTCC', fontName='Helvetica', fontSize=8, leading=11, alignment=TA_CENTER, textColor=slate_dark)
    table_cell_right = ParagraphStyle('PatientTCR', fontName='Helvetica', fontSize=8, leading=11, alignment=TA_RIGHT, textColor=slate_body)
    table_cell_bold_right = ParagraphStyle('PatientTCBR', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_RIGHT, textColor=slate_dark)

    total_label = ParagraphStyle('PatientTL', fontName='Helvetica', fontSize=8.5, leading=12, alignment=TA_RIGHT, textColor=slate_body)
    total_val = ParagraphStyle('PatientTV', fontName='Helvetica-Bold', fontSize=8.5, leading=12, alignment=TA_RIGHT, textColor=slate_dark)
    grand_label = ParagraphStyle('PatientGL', fontName='Helvetica-Bold', fontSize=10, leading=14, alignment=TA_RIGHT, textColor=navy_color)
    grand_val = ParagraphStyle('PatientGV', fontName='Helvetica-Bold', fontSize=10, leading=14, alignment=TA_RIGHT, textColor=navy_color)
    bal_label = ParagraphStyle('PatientBL', fontName='Helvetica-Bold', fontSize=9, leading=13, alignment=TA_RIGHT, textColor=burgundy_color)
    bal_val = ParagraphStyle('PatientBV', fontName='Helvetica-Bold', fontSize=9, leading=13, alignment=TA_RIGHT, textColor=burgundy_color)

    elements = []

    # 1. Header with Logo
    logo_img = _get_hospice_logo() or Paragraph("<b>[NH]</b>", title_style)
    hospice_details = [
        Paragraph("NAIROBI HOSPICE", title_style),
        Paragraph('"Put life into their days, not just days into their life"', motto_style),
        Spacer(1, 1.5 * mm),
        Paragraph("P.O. Box 48290 - 00100, Nairobi &bull; KNH Grounds | Tel: +254 20 2712383", contact_text),
        Paragraph("Email: info@nairobihospice.or.ke &bull; PIN: P051100234K", contact_text),
    ]

    header_brand = Table([[logo_img, hospice_details]], colWidths=[23 * mm, 85 * mm])
    header_brand.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('PADDING', (0, 0), (-1, -1), 0)]))

    status_str = invoice.get_status_display().upper()
    status_hex = '#059669' if invoice.status == 'PAID' else ('#D97706' if invoice.status == 'ISSUED' else '#991B1B')

    header_meta_content = [
        Paragraph("PATIENT CLINICAL TAX INVOICE", doc_heading),
        Paragraph(f"Receipt / Inv #: {invoice.invoice_number}", doc_number),
        Spacer(1, 1.5 * mm),
        Paragraph(f"<b>Issue Date:</b> {invoice.issue_date.strftime('%d %b %Y')}", header_meta),
        Paragraph(f"<b>Payment Status:</b> <font color='{status_hex}'><b>{status_str}</b></font>", header_meta),
    ]

    master_header = Table([[header_brand, header_meta_content]], colWidths=[110 * mm, 72 * mm])
    master_header.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('PADDING', (0, 0), (-1, -1), 0)]))
    elements.append(master_header)
    elements.append(Spacer(1, 3 * mm))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=navy_color, spaceAfter=4 * mm))

    # 2. Patient Dossier Box
    if invoice.patient:
        patient_info = [
            Paragraph("PATIENT DOSSIER & RECIPIENT", section_heading),
            Spacer(1, 1 * mm),
            Paragraph(f"<b>Patient Name:</b> {invoice.patient.full_name}", card_label),
            Paragraph(f"<b>Hospice Number:</b> <font color='#002D62'><b>{invoice.patient.hospice_number}</b></font> &bull; Age: {invoice.patient.age or '-'} yrs ({invoice.patient.get_sex_display()})", card_text),
            Paragraph(f"<b>Primary Diagnosis:</b> {invoice.patient.primary_diagnosis or 'Palliative Care'}", card_text),
            Paragraph(f"<b>Contact:</b> {invoice.patient.phone_number} &bull; <b>County:</b> {invoice.patient.county or 'Nairobi'}", card_text),
        ]
    else:
        patient_info = [
            Paragraph("PATIENT / CLIENT", section_heading),
            Paragraph("General Outpatient Palliative Care Recipient", card_label),
        ]

    billing_info = [
        Paragraph("PAYMENT & SETTLEMENT SPECIFICATIONS", section_heading),
        Spacer(1, 1 * mm),
        Paragraph(f"<b>Payment Channel:</b> {invoice.payment_method or 'M-PESA / Cash'}", card_text),
        Paragraph(f"<b>Transaction / Receipt Ref:</b> {invoice.payment_reference or 'Settled / Pending'}", card_text),
        Paragraph(f"<b>Attending / Issued By:</b> {invoice.created_by.display_name if invoice.created_by else 'Clinical Accounts Officer'}", card_text),
        Paragraph(f"<b>Palliative Subsidy:</b> KES {invoice.discount_amount_kes:,.2f} applied", card_text),
    ]

    patient_grid = Table([[patient_info, billing_info]], colWidths=[91 * mm, 91 * mm])
    patient_grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), slate_light),
        ('BOX', (0, 0), (-1, -1), 0.75, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.75, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(patient_grid)
    elements.append(Spacer(1, 5 * mm))

    # 3. Clinical Services & Medicines Table
    table_data = [
        [
            Paragraph("<b>#</b>", table_header),
            Paragraph("<b>Clinical Service / Prescribed Palliative Medicine</b>", table_header),
            Paragraph("<b>Qty</b>", ParagraphStyle('THPC', parent=table_header, alignment=TA_CENTER)),
            Paragraph("<b>Unit Fee (KES)</b>", ParagraphStyle('THPR', parent=table_header, alignment=TA_RIGHT)),
            Paragraph("<b>Total (KES)</b>", ParagraphStyle('THPR2', parent=table_header, alignment=TA_RIGHT)),
        ]
    ]

    items = invoice.items.all()
    if items.exists():
        for idx, itm in enumerate(items, 1):
            table_data.append([
                Paragraph(str(idx), table_cell_center),
                Paragraph(itm.description, table_cell),
                Paragraph(str(itm.quantity), table_cell_center),
                Paragraph(f"{itm.unit_price_kes:,.2f}", table_cell_right),
                Paragraph(f"{itm.total_price_kes:,.2f}", table_cell_bold_right),
            ])
    else:
        desc = invoice.notes or "Palliative Clinical Consultation, Symptom Management & Medications Package"
        table_data.append([
            Paragraph("1", table_cell_center),
            Paragraph(desc, table_cell),
            Paragraph("1", table_cell_center),
            Paragraph(f"{invoice.total_amount_kes:,.2f}", table_cell_right),
            Paragraph(f"{invoice.total_amount_kes:,.2f}", table_cell_bold_right),
        ])

    items_table = Table(table_data, colWidths=[10 * mm, 94 * mm, 16 * mm, 30 * mm, 32 * mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 5.5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5.5),
        ('TOPPADDING', (0, 1), (-1, -1), 5.5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, slate_light]),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 4 * mm))

    # 4. Totals Block
    subtotal_val = invoice.subtotal_amount_kes if invoice.subtotal_amount_kes > 0 else invoice.total_amount_kes
    totals_data = [
        [Paragraph("Gross Clinical Charge:", total_label), Paragraph(f"KES {subtotal_val:,.2f}", total_val)],
        [Paragraph("Palliative Care Subsidy / Waiver:", total_label), Paragraph(f"- KES {invoice.discount_amount_kes:,.2f}", total_val)],
        [Paragraph("NET AMOUNT PAYABLE:", grand_label), Paragraph(f"KES {invoice.total_amount_kes:,.2f}", grand_val)],
        [Paragraph("Amount Paid / Received:", total_label), Paragraph(f"KES {invoice.amount_paid_kes:,.2f}", total_val)],
        [Paragraph("BALANCE DUE:", bal_label), Paragraph(f"KES {invoice.balance_due_kes:,.2f}", bal_val)],
    ]
    totals_table = Table(totals_data, colWidths=[126 * mm, 56 * mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 2), (-1, 2), 1, navy_color),
        ('LINEBELOW', (0, 4), (-1, 4), 1.5, burgundy_color),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 6 * mm))

    # 5. Patient Payment & Cashier Stamp Block
    pay_instructions = [
        Paragraph("OFFICIAL MPESA & PAYMENT DETAILS", section_heading),
        Spacer(1, 1 * mm),
        Paragraph("<b>M-PESA Paybill:</b> 981234 &bull; <b>Account No:</b> " + (invoice.patient.hospice_number if invoice.patient else invoice.invoice_number), card_text),
        Paragraph("<b>Cash / Card:</b> Handled directly at Nairobi Hospice Front Accounts Desk", card_text),
        Spacer(1, 1 * mm),
        Paragraph("<i>*Palliative care services at Nairobi Hospice are non-profit and charitable.</i>", contact_text),
    ]

    cashier_block = [
        Paragraph("CASHIER / ACCOUNTS STAMP", section_heading),
        Spacer(1, 6 * mm),
        Paragraph("____________________________________", card_text),
        Paragraph("<b>Authorized Hospice Cashier & Stamp</b>", card_label),
        Paragraph("Nairobi Hospice Patient Administration", card_text),
    ]

    footer_grid = Table([[pay_instructions, cashier_block]], colWidths=[104 * mm, 78 * mm])
    footer_grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), slate_light),
        ('BOX', (0, 0), (-1, -1), 0.75, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(KeepTogether([footer_grid]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_supplier_voucher_pdf(invoice) -> io.BytesIO:
    """
    Renders an institutional, formal Supplier Purchase Voucher & Accounts Payable Requisition.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=14 * mm,
    )

    navy_color = colors.HexColor('#002D62')
    burgundy_color = colors.HexColor('#991B1B')
    slate_dark = colors.HexColor('#0F172A')
    slate_body = colors.HexColor('#334155')
    slate_muted = colors.HexColor('#64748B')
    slate_light = colors.HexColor('#F8FAFC')
    border_color = colors.HexColor('#CBD5E1')

    title_style = ParagraphStyle('SuppTitle', fontName='Helvetica-Bold', fontSize=15, leading=18, textColor=navy_color)
    motto_style = ParagraphStyle('SuppMotto', fontName='Helvetica-Oblique', fontSize=8, leading=11, textColor=burgundy_color)
    contact_text = ParagraphStyle('SuppContact', fontName='Helvetica', fontSize=7.5, leading=10.5, textColor=slate_muted)

    doc_heading = ParagraphStyle('SuppHeading', fontName='Helvetica-Bold', fontSize=12, leading=15, alignment=TA_RIGHT, textColor=navy_color)
    doc_number = ParagraphStyle('SuppNo', fontName='Helvetica-Bold', fontSize=10.5, leading=13, alignment=TA_RIGHT, textColor=navy_color)
    header_meta = ParagraphStyle('SuppHeaderMeta', fontName='Helvetica', fontSize=8, leading=11.5, alignment=TA_RIGHT, textColor=slate_body)

    section_heading = ParagraphStyle('SuppSecHead', fontName='Helvetica-Bold', fontSize=8.5, leading=12, textColor=navy_color)
    card_label = ParagraphStyle('SuppCardLabel', fontName='Helvetica-Bold', fontSize=8, leading=11, textColor=slate_dark)
    card_text = ParagraphStyle('SuppCardText', fontName='Helvetica', fontSize=8, leading=11, textColor=slate_body)

    table_header = ParagraphStyle('SuppTH', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=colors.white)
    table_cell = ParagraphStyle('SuppTC', fontName='Helvetica', fontSize=8, leading=11, textColor=slate_dark)
    table_cell_muted = ParagraphStyle('SuppTCMuted', fontName='Helvetica', fontSize=7, leading=9, textColor=slate_muted)
    table_cell_center = ParagraphStyle('SuppTCC', fontName='Helvetica', fontSize=8, leading=11, alignment=TA_CENTER, textColor=slate_dark)
    table_cell_right = ParagraphStyle('SuppTCR', fontName='Helvetica', fontSize=8, leading=11, alignment=TA_RIGHT, textColor=slate_body)
    table_cell_bold_right = ParagraphStyle('SuppTCBR', fontName='Helvetica-Bold', fontSize=8.5, leading=11, alignment=TA_RIGHT, textColor=slate_dark)

    total_label = ParagraphStyle('SuppTL', fontName='Helvetica', fontSize=8.5, leading=12, alignment=TA_RIGHT, textColor=slate_body)
    total_val = ParagraphStyle('SuppTV', fontName='Helvetica-Bold', fontSize=8.5, leading=12, alignment=TA_RIGHT, textColor=slate_dark)
    grand_label = ParagraphStyle('SuppGL', fontName='Helvetica-Bold', fontSize=10, leading=14, alignment=TA_RIGHT, textColor=navy_color)
    grand_val = ParagraphStyle('SuppGV', fontName='Helvetica-Bold', fontSize=10, leading=14, alignment=TA_RIGHT, textColor=navy_color)
    bal_label = ParagraphStyle('SuppBL', fontName='Helvetica-Bold', fontSize=9, leading=13, alignment=TA_RIGHT, textColor=burgundy_color)
    bal_val = ParagraphStyle('SuppBV', fontName='Helvetica-Bold', fontSize=9, leading=13, alignment=TA_RIGHT, textColor=burgundy_color)

    elements = []

    # 1. Official Header
    logo_img = _get_hospice_logo() or Paragraph("<b>[NH]</b>", title_style)
    hospice_details = [
        Paragraph("NAIROBI HOSPICE", title_style),
        Paragraph("PROCUREMENT & SUPPLY CHAIN DIVISION", motto_style),
        Spacer(1, 1.5 * mm),
        Paragraph("P.O. Box 48290 - 00100, Nairobi &bull; KNH Grounds | Tel: +254 20 2712383", contact_text),
        Paragraph("PIN: P051100234K &bull; Email: procurement@nairobihospice.or.ke", contact_text),
    ]

    header_brand = Table([[logo_img, hospice_details]], colWidths=[23 * mm, 85 * mm])
    header_brand.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('PADDING', (0, 0), (-1, -1), 0)]))

    status_str = invoice.get_status_display().upper()
    status_hex = '#059669' if invoice.status == 'PAID' else ('#D97706' if invoice.status == 'ISSUED' else '#991B1B')

    header_meta_content = [
        Paragraph("PURCHASE VOUCHER & INVOICE", doc_heading),
        Paragraph(f"Voucher #: {invoice.invoice_number}", doc_number),
        Spacer(1, 1.5 * mm),
        Paragraph(f"<b>Issue Date:</b> {invoice.issue_date.strftime('%d %b %Y')}", header_meta),
        Paragraph(f"<b>Due Date:</b> {invoice.due_date.strftime('%d %b %Y') if invoice.due_date else '30 Days Net'}", header_meta),
        Paragraph(f"<b>Voucher Status:</b> <font color='{status_hex}'><b>{status_str}</b></font>", header_meta),
    ]

    master_header = Table([[header_brand, header_meta_content]], colWidths=[110 * mm, 72 * mm])
    master_header.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('PADDING', (0, 0), (-1, -1), 0)]))
    elements.append(master_header)
    elements.append(Spacer(1, 3 * mm))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=navy_color, spaceAfter=4 * mm))

    # 2. Supplier & PO Terms Box
    vendor_info = [
        Paragraph("SUPPLIER / VENDOR DETAILS (ACCOUNTS PAYABLE)", section_heading),
        Spacer(1, 1 * mm),
        Paragraph(f"<b>Company:</b> {invoice.vendor.name if invoice.vendor else 'Registered Supplier'}", card_label),
        Paragraph(f"<b>Vendor Code / PIN:</b> {invoice.vendor.code if invoice.vendor else '-'} &bull; KRA: {invoice.vendor.kra_pin if invoice.vendor else 'N/A'}", card_text),
        Paragraph(f"<b>Contact Person:</b> {invoice.vendor.contact_person if invoice.vendor else '-'} ({invoice.vendor.phone_number if invoice.vendor else '-'})", card_text),
        Paragraph(f"<b>Physical Address:</b> {invoice.vendor.physical_address if invoice.vendor else 'Nairobi, Kenya'}", card_text),
    ]

    po_info = [
        Paragraph("PURCHASE ORDER & AUDIT LINKAGE", section_heading),
        Spacer(1, 1 * mm),
        Paragraph(f"<b>Linked PO:</b> <font color='#002D62'><b>{invoice.procurement_order.po_number if invoice.procurement_order else 'Direct PO'}</b></font>", card_text),
        Paragraph(f"<b>Payment Terms:</b> {invoice.vendor.payment_terms if invoice.vendor else '30 Days Net'}", card_text),
        Paragraph(f"<b>Payment Channel:</b> {invoice.payment_method or 'Bank Transfer (EFT / RTGS)'}", card_text),
        Paragraph(f"<b>Requisitioned By:</b> {invoice.created_by.display_name if invoice.created_by else 'Operations Manager'}", card_text),
    ]

    supplier_grid = Table([[vendor_info, po_info]], colWidths=[91 * mm, 91 * mm])
    supplier_grid.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), slate_light),
        ('BOX', (0, 0), (-1, -1), 0.75, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.75, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(supplier_grid)
    elements.append(Spacer(1, 5 * mm))

    # 3. Supplies Line Items Table
    table_data = [
        [
            Paragraph("<b>#</b>", table_header),
            Paragraph("<b>Stock SKU / Specification Description</b>", table_header),
            Paragraph("<b>Qty Recv</b>", ParagraphStyle('THSC', parent=table_header, alignment=TA_CENTER)),
            Paragraph("<b>Unit Cost (KES)</b>", ParagraphStyle('THSR', parent=table_header, alignment=TA_RIGHT)),
            Paragraph("<b>Total (KES)</b>", ParagraphStyle('THSR2', parent=table_header, alignment=TA_RIGHT)),
        ]
    ]

    items = invoice.items.all()
    if items.exists():
        for idx, itm in enumerate(items, 1):
            desc_cell = [Paragraph(itm.description, table_cell)]
            if itm.stock_item:
                desc_cell.append(Paragraph(f"Code: {itm.stock_item.item_code} &bull; Category: {itm.stock_item.get_category_display()}", table_cell_muted))
            table_data.append([
                Paragraph(str(idx), table_cell_center),
                desc_cell,
                Paragraph(str(itm.quantity), table_cell_center),
                Paragraph(f"{itm.unit_price_kes:,.2f}", table_cell_right),
                Paragraph(f"{itm.total_price_kes:,.2f}", table_cell_bold_right),
            ])
    else:
        desc = f"Procurement Batch Requisition - {invoice.procurement_order.po_number}" if invoice.procurement_order else (invoice.notes or "Medical Supplies Batch")
        table_data.append([
            Paragraph("1", table_cell_center),
            Paragraph(desc, table_cell),
            Paragraph("1", table_cell_center),
            Paragraph(f"{invoice.total_amount_kes:,.2f}", table_cell_right),
            Paragraph(f"{invoice.total_amount_kes:,.2f}", table_cell_bold_right),
        ])

    items_table = Table(table_data, colWidths=[10 * mm, 94 * mm, 16 * mm, 30 * mm, 32 * mm])
    items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy_color),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, 0), 5.5),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 5.5),
        ('TOPPADDING', (0, 1), (-1, -1), 5.5),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 5.5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, slate_light]),
    ]))
    elements.append(items_table)
    elements.append(Spacer(1, 4 * mm))

    # 4. Totals Block
    subtotal_val = invoice.subtotal_amount_kes if invoice.subtotal_amount_kes > 0 else invoice.total_amount_kes
    totals_data = [
        [Paragraph("Subtotal (Excl VAT):", total_label), Paragraph(f"KES {subtotal_val:,.2f}", total_val)],
        [Paragraph("VAT / Duties:", total_label), Paragraph(f"KES {invoice.tax_amount_kes:,.2f}", total_val)],
        [Paragraph("TOTAL PROCUREMENT PAYABLE:", grand_label), Paragraph(f"KES {invoice.total_amount_kes:,.2f}", grand_val)],
        [Paragraph("Disbursements / Paid to Vendor:", total_label), Paragraph(f"KES {invoice.amount_paid_kes:,.2f}", total_val)],
        [Paragraph("OUTSTANDING PAYABLE BALANCE:", bal_label), Paragraph(f"KES {invoice.balance_due_kes:,.2f}", bal_val)],
    ]
    totals_table = Table(totals_data, colWidths=[126 * mm, 56 * mm])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 2),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
        ('LINEBELOW', (0, 2), (-1, 2), 1, navy_color),
        ('LINEBELOW', (0, 4), (-1, 4), 1.5, burgundy_color),
    ]))
    elements.append(totals_table)
    elements.append(Spacer(1, 5 * mm))

    # 5. Three-Tier Institutional Authorizations Block
    auth_col1 = [
        Paragraph("1. PREPARED & CHECKED BY", section_heading),
        Spacer(1, 5 * mm),
        Paragraph("____________________________", card_text),
        Paragraph("<b>Operations & Stores Officer</b>", card_label),
        Paragraph("Stock Count & Quality Verified", contact_text),
    ]
    auth_col2 = [
        Paragraph("2. AUDITED & PASSED BY", section_heading),
        Spacer(1, 5 * mm),
        Paragraph("____________________________", card_text),
        Paragraph("<b>Internal Auditor / Accountant</b>", card_label),
        Paragraph("Matching PO & Delivery Note", contact_text),
    ]
    auth_col3 = [
        Paragraph("3. PAYMENT APPROVED BY", section_heading),
        Spacer(1, 5 * mm),
        Paragraph("____________________________", card_text),
        Paragraph("<b>Executive Director / CEO</b>", card_label),
        Paragraph("Disbursement Authorized", contact_text),
    ]

    auth_table = Table([[auth_col1, auth_col2, auth_col3]], colWidths=[61 * mm, 61 * mm, 60 * mm])
    auth_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), slate_light),
        ('BOX', (0, 0), (-1, -1), 0.75, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(KeepTogether([auth_table]))

    doc.build(elements)
    buffer.seek(0)
    return buffer


def generate_invoice_pdf(invoice) -> io.BytesIO:
    """
    Dispatcher: Generates the specific PDF layout based on invoice type.
    """
    if invoice.invoice_type == 'SUPPLIER_PURCHASE':
        return generate_supplier_voucher_pdf(invoice)
    return generate_patient_invoice_pdf(invoice)
