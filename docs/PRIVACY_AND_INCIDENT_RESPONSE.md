# Nairobi Hospice PCMS: Privacy, Data Protection & Incident Response Operational Pack
**Compliance Framework: Kenya Data Protection Act (DPA 2019) & Ministry of Health Guidelines**

---

## 1. Governance & Registered Roles (Kenya DPA 2019)

| Role / Entity | Designation / Name | Contact Details | Key Statutory Responsibility |
| :--- | :--- | :--- | :--- |
| **Data Controller** | **Nairobi Hospice Management Committee** | info@nairobihospice.or.ke / +254 722 200 413 | Legal accountability for all patient health data processing |
| **Data Protection Officer (DPO)** | `[Designated DPO Name / Medical Director]` | dpo@nairobihospice.or.ke | Oversight of DPA compliance, DPIAs, and ODPC liaison |
| **Clinical Incident Lead** | **Palliative Medical Director / Head Nurse** | medical@nairobihospice.or.ke | Clinical triage of data access, consent, and patient disclosures |
| **Systems & Security Admin** | **Lead Systems Administrator** | admin@nairobihospice.or.ke | Access revocation, audit log review, backup integrity, MFA enforcement |
| **Regulatory Authority** | **Office of the Data Protection Commissioner (ODPC)** | info@odpc.go.ke / +254 711 081 300 | Statutory breach notification within 72 hours |


Production go-live requires the hospice to name a Data Protection Officer (replace the placeholder above). Do not invent a person's name in this pack.

---

## 2. Data Subject Rights & Subject Access Requests (SAR)

Under Sections 25 & 26 of the Kenya Data Protection Act 2019, patients (or authorized legal guardians / Next of Kin) have the right to access, rectify, or request restriction of their personal data.

### 2.1 Request Handling SOP
1. **Intake & Identity Verification**:
   - Requester identity must be verified using national ID or passport against registered `NextOfKin` / `Caregiver` records.
   - Clinical requests are logged with a unique SAR reference number.
2. **Review & Redaction**:
   - Management / Medical Director approves data disclosure.
   - Third-party references and notes not relevant to the patient's direct care are reviewed.
3. **Fulfillment Timeline**:
   - Must be fulfilled within **21 calendar days** of verified identity.
   - Exports are generated via management-only export views creating an immutable `AuditAction.EXPORT` log.
   - Delivered via encrypted physical handoff or password-protected secure transfer.

### 2.2 Retention & Disposal Policy
- **Adult Clinical Records**: Retained for **20 years** following the last active palliative care contact or death.
- **Pediatric Palliative Records**: Retained until the patient's 25th birthday or 20 years after last encounter (whichever is longer).
- **Destruction**: Database records are soft-closed; physical purge requires joint approval from CEO and Medical Director, followed by secure cryptographic zeroization of associated media.

---

## 3. Mandatory 72-Hour Breach & Incident Response Procedure

### Phase 1: Detection & Immediate Containment (Hour 0 – Hour 4)
1. **Isolate**: Revoke active sessions for compromised staff accounts; rotate database credentials; block malicious IPs at firewall.
2. **Preserve Forensic State**: Capture database snapshots, Nginx logs, Celery logs, and `AuditEvent` table entries.
3. **Liveness Verification**: Verify that backup files in `backups/` are intact and uncompromised.

### Phase 2: Triage & Impact Assessment (Hour 4 – Hour 24)
1. Determine whether Protected Health Information (PHI), patient identity, HIV status, or controlled substance records were accessed or exfiltrated.
2. Identify all affected patient records by `hospice_number` and UUID.

### Phase 3: Statutory Notification (Hour 24 – Hour 72)
1. If sensitive personal data / health records were breached, notify the **ODPC Kenya** within **72 hours** using the official ODPC Data Breach Notification Form.
2. If risk to patient rights/welfare is high, notify affected individuals or their designated Next of Kin in clear language detailing protective steps.

### Phase 4: Remediation & Post-Incident Review
1. Patch vulnerability or configuration defect.
2. Conduct full access review across all staff accounts and enforce TOTP MFA resets.
3. Archive complete incident report in the hospice compliance register.

---

## 4. Operational Scope Boundaries & Controlled Substance Protocols

### 4.1 Digital Health Act (DHA) & Social Health Authority (SHA) Scope Sign-off
- **Current Status**: Standalone SHA claims submission engine is **OUT OF SCOPE** for the core PCMS deployment.
- **Current Workflow**: Patient billing vouchers, fee waivers, and invoice PDFs are generated within PCMS (`/operations/invoices/`) for manual reconciliation with NHIF/SHA paperwork.

### 4.2 Patient Reminders & Messaging Scope Sign-off
- **Current Status**: Automated third-party paid SMS gateway integration is **OUT OF SCOPE** for current baseline.
- **Current Workflow**: Receptionists and palliative nurses use appointment calendar rosters and telephone contact lists for care scheduling.

### 4.3 Controlled Substance (Morphine) Sunday Reconciliation Protocol
- **Weekly Physical Count**: Every Friday afternoon and Monday morning, the Pharmacist-in-Charge conducts a physical count of Oral Morphine bottles and controlled opioids against the immutable `StockMovement` ledger.
- **Variance Investigation**: Any discrepancy between physical inventory and ledger balance triggers an immediate operational audit report to the Medical Director.
- **Export Registry**: Monthly exports for Pharmacy & Poisons Board (PPB) inspections are generated via `/operations/pharmacy/controlled-register/export/`.
