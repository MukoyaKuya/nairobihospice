# Nairobi Hospice PCMS: External Penetration-Test Handoff & Scoping Document

> **Status:** Engagement **not completed**. This file is scoping and authorization only. It is **not** a penetration-test report and contains **no findings**.


This document provides external security auditors and penetration testers with the verified authorization matrix, testing boundaries, target endpoints, and critical security controls for the Nairobi Hospice Palliative Care Management System (PCMS).

---

## 1. Engagement Rules & Authorization

- **Environment**: Testing must target **Staging / Isolated Test Environment ONLY**.
- **Prohibitions**: Never scan production databases, production mail infrastructure, live clinical messaging, or third-party upstream APIs.
- **Data Protection**: Do not exfiltrate or store patient PHI. Any sensitive test artifacts created during testing must be sanitized at engagement close.

---

## 2. Target Roles & Test Account Profiles

| Role | Staging Username / Role | Authorized Scope | Key Security Invariants to Audit |
| :--- | :--- | :--- | :--- |
| **Receptionist** | `staging_receptionist` | Bio-Data, Caregivers, Scheduling, ID Cards | **BARRED**: Primary diagnosis, HIV status, encounters, ESAS, care plans, clinical documents, medication records. |
| **Pharmacist** | `staging_pharmacist` | Bio-Data, Active Prescriptions, Inventory/Dispense | **BARRED**: Patient registration (403), edit (403), DRF PATCH (403), encounters/ESAS/care plans/field routes. |
| **Palliative Nurse** | `staging_nurse` | Assigned Caseload Bio-Data + Full Clinical Dossier | **BARRED**: Unassigned patients (404), restricted substance prescribing. |
| **Doctor / CO** | `staging_doctor` | Assigned Caseload Bio-Data + Clinical + Prescribing | **BARRED**: Unassigned patients (404). |
| **Manager / Admin** | `staging_manager` | System Administration, Audit Logs, Deletions | Requires verified MFA on privileged sessions. |

---

## 3. High-Priority Testing Target Areas

### A. Broken Object-Level Authorization (BOLA / IDOR) & Caseload Boundaries
- `GET /patients/<uuid:pk>/`: Verify that unassigned patients return HTTP 404 for clinicians.
- `GET /patients/<uuid:pk>/`: Verify that pharmacists only access patients with prior recorded dispenses, and that clinical tabs (Encounters, ESAS, Care Plans) are completely absent.
- `POST /patients/<uuid:pk>/edit/`: Verify that pharmacists and receptionists receive HTTP 403.
- `PATCH /api/v1/patients/<uuid:pk>/`: Verify that pharmacists receive HTTP 403.

### B. PHI Leakage via Search, Calendars, and API Serialization
- `GET /patients/api/search/?q=<term>`: Verify that `primary_diagnosis` is stripped (`""`) for receptionists and pharmacists.
- `GET /api/v1/appointments/?search=<clinical_term>`: Verify that non-clinical users cannot match clinical keywords (`reason`, `notes`).
- `GET /appointments/`: Verify that Alpine.js DOM filter attributes do not interpolate clinical diagnoses for non-clinical sessions.
- `POST /referrals/create/`: Verify that non-clinical submissions store fixed token (`'Palliative care intake evaluation requested.'`) and discard injected clinical narrative.

### C. Pharmacy & Controlled Substance Safety Ledger
- `POST /operations/pharmacy/dispense/`: Verify that every `DISPENSE` movement requires a valid `patient_id` and linked `medication_statement_id`.
- Verify database CHECK constraint and DB trigger: Attempting to insert mismatched `medication_statement` belonging to a different patient must abort with database error.
- `GET /operations/pharmacy/controlled-register/export/`: Verify role authorization and streaming security headers.

### D. Private Media & Storage Isolation
- `GET /documents/<uuid:pk>/download/` & `GET /patients/<uuid:pk>/photo/`: Verify that unauthenticated requests return 302/403 and authorized requests return headers:
  ```http
  Cache-Control: private, no-store, max-age=0, must-revalidate
  X-Content-Type-Options: nosniff
  ```
- Direct file paths (`/private_media/...`, `/media/clinical_documents/...`, `/media/patient_photos/...`): Verify that webserver returns HTTP 404/403.

### E. Authentication, MFA, and Injection Defenses
- Privileged & Clinical MFA enforcement on protected routes.
- Open redirect validation on all `next=` query parameters.
- Content Security Policy (CSP): Nonce verification on `<script>` tags, absence of `unsafe-inline` in `script-src`.
- File upload malware scanning fail-closed validation.

---

## 4. Reporting & Remediation Protocol

Testers must document findings with:
1. **Finding ID & Severity** (Critical, High, Medium, Low, Informational)
2. **Target URL & Request Payload / PoC**
3. **Observed Behavior vs Expected Policy Matrix**
4. **Remediation Recommendation**
