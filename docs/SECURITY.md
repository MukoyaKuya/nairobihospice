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
   - Patient directory tables render `Palliative Care` instead of actual clinical diagnoses for non-clinical users.

3. **Referral Intake**:
   - Referrals created by non-clinical staff omit clinical summary and medication fields; `primary_diagnosis` defaults to `'Pending Clinical Review'`.

4. **Private Media Isolation**:
   - Patient ID photos and clinical documents are stored outside the web root (`private_media/`).
   - Served exclusively through authenticated, role-gated endpoints with headers:
     ```http
     Cache-Control: private, no-store, max-age=0, must-revalidate
     X-Content-Type-Options: nosniff
     ```

---

## 3. Pharmacy & Controlled Substance Safety

1. **Caseload-Only Visibility**:
   - Pharmacists only see patients who have active prescriptions or historical dispenses.
2. **Dispense Audit Integrity**:
   - Every stock dispense must bind both `patient_id` and `medication_statement_id` ForeignKeys.
   - Pharmacists cannot create new medication prescriptions via Web or API (`MEDICATION_RECORDER_ROLES` is restricted to prescribers and nurses).

---

## 4. Authentication, Session & Transport Security

1. **Multi-Factor Authentication (MFA)**:
   - TOTP secrets are encrypted at rest using AES-128-CBC / Fernet with HMAC authentication (`FERNET_SECRET_KEY`).
   - Privileged roles (Manager, Administrator, Clinicians) require MFA enrollment.
2. **Open Redirect Protection**:
   - All `next=` redirect parameters are validated via `url_has_allowed_host_and_scheme`.
3. **Malware Defense**:
   - All file uploads (documents and patient photos) undergo malware inspection via `clamscan`.
   - Production setting `PCMS_REQUIRE_MALWARE_SCAN=True` enforces fail-closed rejection if scanner is unavailable.
