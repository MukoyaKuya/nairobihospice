# Nairobi Hospice PCMS: Security & Privacy Architecture

This document defines the official security model, access control matrix, and data protection controls for the Nairobi Hospice Palliative Care Management System (PCMS).

---

## 1. Role-Based Access Control (RBAC) & PHI Boundary Matrix

The PCMS enforces strict separation between **Demographic Bio-Data** (Intake/Logistics), **Dispense Verification** (Pharmacy), and **Clinical Dossier / PHI** (Direct Care).

```
+-------------------+------------------------------------+------------------------------------+
| Role              | Authorized Scope                   | Prohibited / Scrubbed Scope        |
+-------------------+------------------------------------+------------------------------------+
| Receptionist      | Bio-Data, Caregivers,              | HIV Status, Primary Diagnosis,     |
|                   | Next of Kin, Scheduling,           | Clinical Notes, Encounters,        |
|                   | ID Card Generation                 | ESAS Symptoms, Prescriptions,      |
|                   |                                    | Care Plans, Field Route Logistics  |
+-------------------+------------------------------------+------------------------------------+
| Pharmacist        | Identification Bio-Data,           | Patient Registration, Editing      |
|                   | Active Prescriptions,              | Patient Records, Encounters,       |
|                   | Inventory & Stock Dispense         | ESAS Symptoms, Formal Assessments, |
|                   |                                    | Care Plans, Prescribing (API/Web), |
|                   |                                    | Field Route Logistics, Diagnosis   |
+-------------------+------------------------------------+------------------------------------+
| Doctor &          | Full Bio-Data + Full Clinical      | Cross-Caseload Access (unassigned  |
| Clinical Officer  | Dossier for Assigned Caseload;     | patients outside active care or    |
|                   | Prescribing & Clinical Oversight   | appointments return 404)           |
+-------------------+------------------------------------+------------------------------------+
| Palliative Nurse  | Full Bio-Data + Full Clinical      | Prescribing Restricted Substances; |
|                   | Dossier for Assigned Caseload;     | Cross-Caseload Access              |
|                   | ESAS, Encounters, Care Plans       |                                    |
+-------------------+------------------------------------+------------------------------------+
| Social Worker /   | Bio-Data, Caregivers, Next of Kin, | Direct Medication Prescribing;     |
| Counsellor        | Psychosocial Encounters/Notes      | Medical Clinical Alterations       |
+-------------------+------------------------------------+------------------------------------+
| Manager & Admin   | System Administration, Management  | N/A (Full Administrative Bypass    |
|                   | Metrics, Deletion Request Review   | Subject to Comprehensive Audit)    |
+-------------------+------------------------------------+------------------------------------+
```

---

## 2. Protected Health Information (PHI) Controls

1. **Search & Typeahead Scrubbing**:
   - `search_patients` and `/patients/api/search/` return `primary_diagnosis: ""` for receptionists and pharmacists.
   - Typeahead comboboxes for non-receptionists are strictly scoped to `authorized_patient_queryset`.

2. **Calendar & Patient Lists**:
   - Diagnosis and clinical focus reasons on the appointment calendar are gated by `clinical_access`.
   - Alpine.js `matchesFilter` client-side evaluation and search placeholders omit clinical text for non-clinical roles.
   - Appointment search by query `q` and REST API `AppointmentViewSet ?search=` exclude clinical `reason` and `notes` matching for non-clinical staff.
   - Patient directory tables render `Palliative Care` instead of actual clinical diagnoses for non-clinical users.

3. **Referral Intake & Scrubbing**:
   - Referral form conditionally hides diagnosis, clinical summary, and medication fields from receptionists.
   - Submissions from non-clinical staff set `primary_diagnosis` to `'Pending Clinical Review'` and store a fixed intake token (`'Palliative care intake evaluation requested.'`), dropping any submitted free-text clinical narrative.

4. **Media Access Controls & Headers**:
   - Clinical documents and patient photos are protected behind role-authorized streaming endpoints and served with headers:
     ```http
     Cache-Control: private, no-store, max-age=0, must-revalidate
     X-Content-Type-Options: nosniff
     ```

---

## 3. Pharmacy & Controlled Substance Safety

1. **Caseload & Candidate Scoping**:
   - A pharmacist's personal caseload (`authorized_patient_queryset`) is strictly limited to patients to whom they have recorded a dispense (`stock_movements__recorded_by=user`).
   - The initial dispense candidate dropdown (`StockDispenseForm`) renders only patients from the pharmacist's own authorized caseload. A requested patient query parameter is not appended unless that patient is already in authorized_patient_queryset (managers/admins keep the full active-Rx register).
2. **Dispense Audit Integrity & Database Constraints**:
   - Stock dispenses require both `patient_id` and `medication_statement_id` ForeignKeys.
   - Enforced at the database level via `CheckConstraint(dispense_requires_patient_and_rx)` AND database triggers (`check_dispense_patient_rx_match`) across SQLite, PostgreSQL, and MySQL, ensuring that the medication statement belongs to the dispensed patient on `INSERT`, `UPDATE`, and `bulk_create`.
   - Model layer validation (`StockMovement.clean()` / `full_clean()`) and service layer validation (`record_stock_movement`) maintain matching integrity.
   - Pharmacists cannot create new medication prescriptions via Web or API (`MEDICATION_RECORDER_ROLES` is restricted to prescribers and nurses).
3. **Dedicated Operational Dashboard**:
   - Pharmacist dashboard displays medication KPIs, controlled substance registries, and user-scoped total dispenses, completely skipping clinical pain/encounter database queries.

---

## 4. Authentication, Session & Transport Security

1. **Multi-Factor Authentication (MFA)**:
   - TOTP secrets are encrypted at rest with AES-128-CBC / Fernet (key derived via SHA-256 from Django `SECRET_KEY`).
   - All staff roles with access to live PHI, active prescriptions, or the patient register (Superusers, Managers, Doctors, Nurses, Clinical Officers, Pharmacists, Receptionists) require MFA verification when `MFA_REQUIRED_FOR_PRIVILEGED` is active.
2. **Open Redirect Protection**:
   - All `next=` redirect parameters are validated via `url_has_allowed_host_and_scheme`.
3. **Content Security Policy (CSP)**:
   - Dynamic per-request cryptographic nonces (`'nonce-{csp_nonce}'`) are enforced on script tags, removing `'unsafe-inline'` from `script-src`.
   - Error pages and the Django admin login template load local static/css/custom.css only. They must not load Tailwind CDN (cdn.tailwindcss.com) or unpkg.
   - 'unsafe-eval' remains in script-src because the vendored Alpine.js 3.14.8 standard build compiles x-data / x-on expressions with the Function constructor, and the vendored Tailwind Play 3.4.16 in-browser JIT compiler also requires eval. The Alpine CSP build is not currently vendored. Do not drop 'unsafe-eval' until those libraries are replaced with CSP-safe builds. Nonce-only script-src is not sufficient for the current Alpine 3 standard bundle.
4. **Malware Defense**:
   - File uploads (documents and patient photos) undergo malware inspection via `clamscan`.
   - In production (`PCMS_REQUIRE_MALWARE_SCAN=True`), uploads fail-closed if scanner is unavailable.
