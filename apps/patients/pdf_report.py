import io
import os
from datetime import datetime

from django.conf import settings
from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas
from reportlab.platypus import (
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.platypus import Image as RLImage


class NumberedCanvas(canvas.Canvas):
    """
    Two-pass canvas to dynamically compute and draw 'Page X of Y' 
    and confidentiality footer with generation metadata.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 7.5)
        self.setFillColor(colors.HexColor("#64748B"))

        # Footer line
        self.setStrokeColor(colors.HexColor("#E2E8F0"))
        self.setLineWidth(0.5)
        self.line(14 * mm, 12 * mm, 196 * mm, 12 * mm)

        # Footer contents
        left_text = "CONFIDENTIAL MEDICAL RECORD &bull; NAIROBI HOSPICE PCMS"
        center_text = f"Generated: {timezone.now().strftime('%d/%m/%Y %H:%M')}"
        right_text = f"Page {self._pageNumber} of {page_count}"

        self.drawString(14 * mm, 8 * mm, left_text)
        self.drawCentredString(105 * mm, 8 * mm, center_text)
        self.drawRightString(196 * mm, 8 * mm, right_text)
        self.restoreState()


def _get_hospice_logo():
    logo_path = os.path.join(settings.BASE_DIR, 'static', 'images', 'hospice_symbol.png')
    if os.path.exists(logo_path):
        return RLImage(logo_path, width=20 * mm, height=18 * mm)
    return None


def generate_patient_comprehensive_report_pdf(patient, requesting_user=None) -> io.BytesIO:
    """
    Renders a comprehensive, professionally styled Clinical Patient Report PDF
    capturing master demographics, alerts, emergency contacts, medications,
    encounters, ESAS symptom profiles, and care plans.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=14 * mm,
        leftMargin=14 * mm,
        topMargin=12 * mm,
        bottomMargin=16 * mm,
    )

    navy_color = colors.HexColor('#002D62')
    burgundy_color = colors.HexColor('#991B1B')
    slate_dark = colors.HexColor('#0F172A')
    slate_body = colors.HexColor('#334155')
    slate_muted = colors.HexColor('#64748B')
    slate_light = colors.HexColor('#F8FAFC')
    border_color = colors.HexColor('#CBD5E1')
    alert_bg = colors.HexColor('#FEF2F2')
    alert_border = colors.HexColor('#FECACA')

    title_style = ParagraphStyle('RepDocTitle', fontName='Helvetica-Bold', fontSize=14, leading=16, textColor=navy_color)
    motto_style = ParagraphStyle('RepMotto', fontName='Helvetica-Oblique', fontSize=7.5, leading=10, textColor=burgundy_color)
    contact_text = ParagraphStyle('RepContact', fontName='Helvetica', fontSize=7, leading=9.5, textColor=slate_muted)

    doc_heading = ParagraphStyle('RepHeading', fontName='Helvetica-Bold', fontSize=11, leading=13, alignment=TA_RIGHT, textColor=navy_color)
    doc_subhead = ParagraphStyle('RepSubHead', fontName='Helvetica', fontSize=8, leading=10.5, alignment=TA_RIGHT, textColor=slate_body)

    sec_title = ParagraphStyle('RepSecTitle', fontName='Helvetica-Bold', fontSize=8.5, leading=11, textColor=navy_color)
    sec_banner = ParagraphStyle('RepSecBanner', fontName='Helvetica-Bold', fontSize=8.5, leading=10.5, textColor=colors.white)

    label_style = ParagraphStyle('RepLabel', fontName='Helvetica-Bold', fontSize=7.5, leading=10, textColor=slate_dark)
    value_style = ParagraphStyle('RepValue', fontName='Helvetica', fontSize=7.5, leading=10, textColor=slate_body)
    value_bold = ParagraphStyle('RepValueBold', fontName='Helvetica-Bold', fontSize=7.5, leading=10, textColor=slate_dark)
    value_code = ParagraphStyle('RepValueCode', fontName='Helvetica-Bold', fontSize=8, leading=10, textColor=navy_color)

    th_style = ParagraphStyle('RepTH', fontName='Helvetica-Bold', fontSize=7.5, leading=9.5, textColor=colors.white)
    td_style = ParagraphStyle('RepTD', fontName='Helvetica', fontSize=7.5, leading=10, textColor=slate_body)
    td_bold = ParagraphStyle('RepTDBold', fontName='Helvetica-Bold', fontSize=7.5, leading=10, textColor=slate_dark)
    td_center = ParagraphStyle('RepTDCenter', fontName='Helvetica', fontSize=7.5, leading=10, alignment=TA_CENTER, textColor=slate_body)

    elements = []

    # 1. Header & Institutional Branding
    logo_img = _get_hospice_logo() or Paragraph("<b>[NH]</b>", title_style)
    hospice_info = [
        Paragraph("NAIROBI HOSPICE", title_style),
        Paragraph('"Put life into their days, not just days into their life"', motto_style),
        Spacer(1, 1 * mm),
        Paragraph("KNH Grounds, P.O. Box 48290 - 00100, Nairobi | Tel: +254 20 2712383", contact_text),
        Paragraph("Email: info@nairobihospice.or.ke &bull; Web: www.nairobihospice.or.ke", contact_text),
    ]

    header_brand = Table([[logo_img, hospice_info]], colWidths=[22 * mm, 88 * mm])
    header_brand.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP'), ('PADDING', (0, 0), (-1, -1), 0)]))

    user_name = requesting_user.get_full_name() if requesting_user and hasattr(requesting_user, 'get_full_name') else "Authorized Clinician"
    user_role = requesting_user.get_role_display() if requesting_user and hasattr(requesting_user, 'get_role_display') else "Clinical Staff"

    header_meta = [
        Paragraph("COMPREHENSIVE PATIENT CLINICAL DOSSIER", doc_heading),
        Spacer(1, 1 * mm),
        Paragraph(f"<b>Hospice File No:</b> {patient.hospice_number}", doc_subhead),
        Paragraph(f"<b>Status:</b> {patient.get_status_display().upper()}", doc_subhead),
        Paragraph(f"<b>Requested By:</b> {user_name} ({user_role})", doc_subhead),
        Paragraph(f"<b>Report Date:</b> {timezone.now().strftime('%d %b %Y, %H:%M')}", doc_subhead),
    ]

    header_table = Table([[header_brand, header_meta]], colWidths=[110 * mm, 72 * mm])
    header_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('PADDING', (0, 0), (-1, -1), 0),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 2 * mm))
    elements.append(HRFlowable(width="100%", thickness=1.2, color=navy_color, spaceBefore=1, spaceAfter=4))

    # 2. Patient Master Demographics Table
    patient_col1 = [
        [Paragraph("Full Patient Name:", label_style), Paragraph(patient.full_name, value_bold)],
        [Paragraph("Hospice File No:", label_style), Paragraph(patient.hospice_number, value_code)],
        [Paragraph("Hospital IP/OP No:", label_style), Paragraph(patient.ip_op_number or "N/A", value_bold)],
        [Paragraph("Daycare Reg No:", label_style), Paragraph(patient.daycare_number or "N/A", value_style)],
        [Paragraph("Age / Gender:", label_style), Paragraph(f"{patient.age or '-'} yrs &bull; {patient.get_sex_display()}", value_style)],
        [Paragraph("Date of Birth:", label_style), Paragraph(patient.date_of_birth.strftime('%d/%m/%Y') if patient.date_of_birth else "N/A", value_style)],
        [Paragraph("Marital Status:", label_style), Paragraph(patient.get_marital_status_display(), value_style)],
        [Paragraph("National / Alien ID:", label_style), Paragraph(patient.identification_number or "N/A", value_style)],
    ]
    patient_col2 = [
        [Paragraph("Primary Diagnosis:", label_style), Paragraph(patient.primary_diagnosis or "Palliative Care", value_bold)],
        [Paragraph("HIV Status:", label_style), Paragraph("[REDACTED]", value_style)],
        [Paragraph("Primary Phone:", label_style), Paragraph(patient.phone_number or "N/A", value_style)],
        [Paragraph("Residence / County:", label_style), Paragraph(f"{patient.county or 'Nairobi'}{f' / {patient.sub_county}' if patient.sub_county else ''}", value_style)],
        [Paragraph("Ward & Area:", label_style), Paragraph(f"{patient.ward or '-'}{f', {patient.address}' if patient.address else ''}", value_style)],
        [Paragraph("Nearest Bus Stop:", label_style), Paragraph(patient.landmark or "N/A", value_bold)],
        [Paragraph("Referring Facility:", label_style), Paragraph(patient.referred_by or "N/A", value_style)],
        [Paragraph("Enrollment Date:", label_style), Paragraph(patient.registration_date.strftime('%d/%m/%Y') if patient.registration_date else "N/A", value_style)],
    ]

    t_col1 = Table(patient_col1, colWidths=[30 * mm, 58 * mm])
    t_col1.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('PADDING', (0, 0), (-1, -1), 1.5),
    ]))

    t_col2 = Table(patient_col2, colWidths=[32 * mm, 56 * mm])
    t_col2.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 1.5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1.5),
        ('PADDING', (0, 0), (-1, -1), 1.5),
    ]))

    demo_table = Table([[t_col1, t_col2]], colWidths=[90 * mm, 92 * mm])
    demo_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), slate_light),
        ('BOX', (0, 0), (-1, -1), 0.75, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 4),
        ('RIGHTPADDING', (0, 0), (-1, -1), 4),
    ]))

    elements.append(Table([[Paragraph("1. PATIENT MASTER IDENTIFIERS &amp; DEMOGRAPHICS", sec_banner)]], 
                          colWidths=[182 * mm], 
                          style=[('BACKGROUND', (0, 0), (-1, -1), navy_color), ('PADDING', (0, 0), (-1, -1), 3)]))
    elements.append(demo_table)
    elements.append(Spacer(1, 2.5 * mm))

    # 3. Clinical Alerts & Allergies (If Any)
    if patient.allergies or patient.clinical_alerts:
        alert_rows = []
        if patient.allergies:
            alert_rows.append([Paragraph("<b>Known Drug Allergies:</b>", label_style), Paragraph(patient.allergies, value_bold)])
        if patient.clinical_alerts:
            alert_rows.append([Paragraph("<b>Clinical Precautions / Alerts:</b>", label_style), Paragraph(patient.clinical_alerts, value_bold)])
        
        alert_table = Table(alert_rows, colWidths=[42 * mm, 136 * mm])
        alert_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), alert_bg),
            ('BOX', (0, 0), (-1, -1), 1, alert_border),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, alert_border),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 5),
            ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(alert_table)
        elements.append(Spacer(1, 2.5 * mm))

    # 4. Next of Kin & Caregivers Circle Table
    nok_list = list(patient.next_of_kin.all())
    cg_list = list(patient.caregivers.all())

    contacts_data = [[
        Paragraph("Contact Type", th_style),
        Paragraph("Full Name", th_style),
        Paragraph("Relationship", th_style),
        Paragraph("Phone", th_style),
        Paragraph("Age / Sex", th_style),
        Paragraph("County & Location", th_style),
        Paragraph("Nearest Bus Stop", th_style),
    ]]

    for nok in nok_list:
        loc = f"{nok.county or 'Nairobi'}{f' / {nok.sub_county}' if nok.sub_county else ''}{f' ({nok.address})' if nok.address else ''}"
        contacts_data.append([
            Paragraph("Next of Kin", td_bold),
            Paragraph(nok.name, td_bold),
            Paragraph(nok.relationship or "-", td_style),
            Paragraph(nok.phone_number or "-", td_style),
            Paragraph(f"{nok.age or '-'}y &bull; {nok.gender or '-'}", td_style),
            Paragraph(loc, td_style),
            Paragraph(nok.nearest_stage or "-", td_bold),
        ])

    for cg in cg_list:
        loc = f"{cg.county or 'Nairobi'}{f' / {cg.sub_county}' if cg.sub_county else ''}{f' ({cg.address})' if cg.address else ''}"
        contacts_data.append([
            Paragraph("Caregiver", td_bold),
            Paragraph(cg.name, td_bold),
            Paragraph(cg.relationship or "Caregiver", td_style),
            Paragraph(cg.phone_number or "-", td_style),
            Paragraph(f"{cg.age or '-'}y &bull; {cg.gender or '-'}", td_style),
            Paragraph(loc, td_style),
            Paragraph(cg.nearest_stage or "-", td_bold),
        ])

    if len(contacts_data) == 1:
        contacts_data.append([Paragraph("No next of kin or caregivers recorded.", td_style)] + [Paragraph("-", td_style)] * 6)

    contacts_table = Table(contacts_data, colWidths=[20 * mm, 30 * mm, 24 * mm, 24 * mm, 18 * mm, 38 * mm, 28 * mm])
    contacts_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy_color),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, slate_light]),
    ]))

    elements.append(Table([[Paragraph("2. NEXT OF KIN &amp; CAREGIVERS CONTACT CIRCLE", sec_banner)]], 
                          colWidths=[182 * mm], 
                          style=[('BACKGROUND', (0, 0), (-1, -1), navy_color), ('PADDING', (0, 0), (-1, -1), 3)]))
    elements.append(contacts_table)
    elements.append(Spacer(1, 3 * mm))

    # 5. Active & Recent Palliative Medications
    meds = patient.medications.order_by('-start_date', '-created_at')[:12]
    meds_data = [[
        Paragraph("Medication & Formulation", th_style),
        Paragraph("Dosage", th_style),
        Paragraph("Route", th_style),
        Paragraph("Frequency", th_style),
        Paragraph("Clinical Indication", th_style),
        Paragraph("Start Date", th_style),
        Paragraph("Status", th_style),
    ]]

    for m in meds:
        meds_data.append([
            Paragraph(m.medication_name, td_bold),
            Paragraph(m.dosage or "-", td_style),
            Paragraph(m.get_route_display() if hasattr(m, 'get_route_display') else m.route, td_style),
            Paragraph(m.frequency or "-", td_style),
            Paragraph(m.indication or "-", td_style),
            Paragraph(m.start_date.strftime('%d/%m/%Y') if m.start_date else "-", td_style),
            Paragraph(m.get_status_display().upper() if hasattr(m, 'get_status_display') else m.status, td_bold),
        ])

    if len(meds_data) == 1:
        meds_data.append([Paragraph("No active palliative medications on record.", td_style)] + [Paragraph("-", td_style)] * 6)

    meds_table = Table(meds_data, colWidths=[40 * mm, 24 * mm, 18 * mm, 32 * mm, 36 * mm, 16 * mm, 16 * mm])
    meds_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), navy_color),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 3),
        ('RIGHTPADDING', (0, 0), (-1, -1), 3),
        ('GRID', (0, 0), (-1, -1), 0.5, border_color),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, slate_light]),
    ]))

    elements.append(Table([[Paragraph("3. PALLIATIVE MEDICATION STATEMENTS &amp; PRESCRIPTIONS", sec_banner)]], 
                          colWidths=[182 * mm], 
                          style=[('BACKGROUND', (0, 0), (-1, -1), navy_color), ('PADDING', (0, 0), (-1, -1), 3)]))
    elements.append(meds_table)
    elements.append(Spacer(1, 3 * mm))

    # 6. ESAS Edmonton Symptom Assessment Scores Profile (Latest 4 records)
    symptoms = patient.symptom_records.prefetch_related('scores').order_by('-recorded_at')[:4]
    if symptoms.exists():
        esas_data = [[
            Paragraph("Assessment Date", th_style),
            Paragraph("Pain", th_style),
            Paragraph("Tired", th_style),
            Paragraph("Nausea", th_style),
            Paragraph("Depr", th_style),
            Paragraph("Anx", th_style),
            Paragraph("Drowsy", th_style),
            Paragraph("Appet", th_style),
            Paragraph("Wellb", th_style),
            Paragraph("SOB", th_style),
            Paragraph("Distress Score", th_style),
        ]]

        for r in symptoms:
            scores_map = {s.symptom_type: s.score for s in r.scores.all()}
            
            esas_data.append([
                Paragraph(r.recorded_at.strftime('%d/%m/%Y %H:%M') if r.recorded_at else "-", td_bold),
                Paragraph(str(scores_map.get('PAIN', '-')), td_center),
                Paragraph(str(scores_map.get('TIREDNESS', '-')), td_center),
                Paragraph(str(scores_map.get('NAUSEA', '-')), td_center),
                Paragraph(str(scores_map.get('DEPRESSION', '-')), td_center),
                Paragraph(str(scores_map.get('ANXIETY', '-')), td_center),
                Paragraph(str(scores_map.get('DROWSINESS', '-')), td_center),
                Paragraph(str(scores_map.get('LACK_OF_APPETITE', '-')), td_center),
                Paragraph(str(scores_map.get('WELLBEING', '-')), td_center),
                Paragraph(str(scores_map.get('SHORTNESS_OF_BREATH', '-')), td_center),
                Paragraph(f"<b>{r.total_distress_score} / 100</b>", td_center),
            ])

        esas_table = Table(esas_data, colWidths=[32 * mm, 15 * mm, 15 * mm, 15 * mm, 15 * mm, 15 * mm, 15 * mm, 15 * mm, 15 * mm, 15 * mm, 25 * mm])
        esas_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), burgundy_color),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('TOPPADDING', (0, 0), (-1, -1), 2.5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2.5),
            ('LEFTPADDING', (0, 0), (-1, -1), 2),
            ('RIGHTPADDING', (0, 0), (-1, -1), 2),
            ('GRID', (0, 0), (-1, -1), 0.5, border_color),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, slate_light]),
        ]))

        elements.append(Table([[Paragraph("4. EDMONTON SYMPTOM ASSESSMENT SYSTEM (ESAS) PROFILE", sec_banner)]], 
                              colWidths=[182 * mm], 
                              style=[('BACKGROUND', (0, 0), (-1, -1), burgundy_color), ('PADDING', (0, 0), (-1, -1), 3)]))
        elements.append(esas_table)
        elements.append(Spacer(1, 3 * mm))

    # 7. Recent Clinical Encounters & Care Notes (Latest 3 encounters)
    encounters = patient.encounters.select_related('clinician').order_by('-encounter_date', '-created_at')[:4]
    if encounters.exists():
        enc_elements = []
        enc_elements.append(Table([[Paragraph("5. RECENT CLINICAL ENCOUNTERS &amp; PALLIATIVE NOTES", sec_banner)]], 
                                  colWidths=[182 * mm], 
                                  style=[('BACKGROUND', (0, 0), (-1, -1), navy_color), ('PADDING', (0, 0), (-1, -1), 3)]))

        for enc in encounters:
            clinician_name = enc.clinician.get_full_name() if enc.clinician else "Attending Clinician"
            enc_date_str = enc.encounter_date.strftime('%d %B %Y') if enc.encounter_date else enc.created_at.strftime('%d %B %Y')
            enc_type_str = enc.get_encounter_type_display() if hasattr(enc, 'get_encounter_type_display') else enc.encounter_type

            enc_header = [
                Paragraph(f"<b>Date:</b> {enc_date_str} &bull; <b>Type:</b> {enc_type_str}", label_style),
                Paragraph(f"<b>Clinician:</b> {clinician_name}", label_style),
            ]
            enc_header_table = Table([enc_header], colWidths=[91 * mm, 91 * mm])
            enc_header_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), slate_light),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ]))

            notes_rows = [
                [Paragraph("<b>Chief Complaint / Reason:</b>", label_style), Paragraph(enc.reason or "Routine clinical review", value_style)],
            ]
            if getattr(enc, 'subjective_notes', None):
                notes_rows.append([Paragraph("<b>Subjective History:</b>", label_style), Paragraph(enc.subjective_notes, value_style)])
            if getattr(enc, 'objective_assessment', None):
                notes_rows.append([Paragraph("<b>Objective Findings:</b>", label_style), Paragraph(enc.objective_assessment, value_style)])
            if getattr(enc, 'clinical_plan', None):
                notes_rows.append([Paragraph("<b>Management Plan:</b>", label_style), Paragraph(enc.clinical_plan, value_bold)])

            notes_table = Table(notes_rows, colWidths=[38 * mm, 144 * mm])
            notes_table.setStyle(TableStyle([
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),
                ('TOPPADDING', (0, 0), (-1, -1), 2),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
                ('LEFTPADDING', (0, 0), (-1, -1), 3),
                ('RIGHTPADDING', (0, 0), (-1, -1), 3),
                ('GRID', (0, 0), (-1, -1), 0.5, border_color),
            ]))

            single_enc_card = Table([[enc_header_table], [notes_table]], colWidths=[182 * mm])
            single_enc_card.setStyle(TableStyle([
                ('BOX', (0, 0), (-1, -1), 0.75, border_color),
                ('PADDING', (0, 0), (-1, -1), 0),
            ]))

            enc_elements.append(single_enc_card)
            enc_elements.append(Spacer(1, 2 * mm))

        elements.append(KeepTogether(enc_elements[:2]))  # Keep first pair together if possible
        if len(enc_elements) > 2:
            elements.extend(enc_elements[2:])

    # 8. Clinician Sign-off & Confidentiality Block
    sign_off_col1 = [
        Paragraph("<b>CLINICAL REPORT CERTIFICATION</b>", sec_title),
        Paragraph("This document contains confidential patient health information under Kenya Data Protection Act 2019 and Medical Practitioners & Dentists Board standards. Authorized for clinical care and hospice MDT use only.", contact_text),
    ]

    sign_off_col2 = [
        Paragraph("<b>REVIEWING CLINICIAN SIGNATURE</b>", sec_title),
        Spacer(1, 4 * mm),
        Paragraph("Sign / Stamp: ___________________________", label_style),
        Paragraph(f"Name: {user_name} &bull; Date: {timezone.now().strftime('%d/%m/%Y')}", contact_text),
    ]

    sign_table = Table([[sign_off_col1, sign_off_col2]], colWidths=[105 * mm, 77 * mm])
    sign_table.setStyle(TableStyle([
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('BACKGROUND', (0, 0), (-1, -1), slate_light),
        ('BOX', (0, 0), (-1, -1), 0.75, border_color),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, border_color),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
    ]))

    elements.append(Spacer(1, 3 * mm))
    elements.append(KeepTogether([sign_table]))

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    return buffer
