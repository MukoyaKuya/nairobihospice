# External penetration-test handoff

## Required authorization

Testing must target staging only, with written approval from the system owner. Do not scan production, patient systems, mail infrastructure, or third-party services without separate authorization.

## Scope to provide the tester

- Staging HTTPS hostname/IP and approved test window.
- Test accounts for receptionist, clinician, manager, and administrator roles.
- MFA test enrollment/reset procedure and test mailbox.
- API base URL and an authenticated test token/session process.
- Explicit out-of-scope systems and rate-limit-safe testing limits.

## Required coverage

- Authentication, MFA enrollment/challenge/recovery, password reset, session fixation/expiry, and login throttling.
- Object-level authorization across patients, referrals, appointments, clinical records, documents, photos, exports, and API filters.
- Receptionist-safe views and serializer leakage, including HTML/HTMX/JSON responses.
- Private-media path traversal, direct URL access, content-type handling, and cache headers.
- CSRF, XSS, SQL injection, SSRF, file upload validation, host-header handling, and security headers.
- API throttling, pagination, error handling, OpenAPI exposure, and privilege escalation.
- Audit-log tampering, export access, backup exposure, and sensitive data in logs.

## Evidence and remediation

Require a finding ID, severity, affected URL/request, reproducible evidence, business impact, remediation owner, retest result, and residual-risk decision for every finding. Production approval requires no unresolved critical/high findings and explicit acceptance for any remaining medium findings.
