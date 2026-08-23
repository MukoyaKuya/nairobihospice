# Engineering Remediation Plan

## Completed in code

- Patient-history querysets are bounded to the most recent 100 records in the patient workspace.
- Appointment API writes are limited to reception, management, and administrator roles; reads remain authenticated-staff scoped.
- Undelivered webhook records can be replayed with `manage.py replay_webhooks --limit 100`.
- Private media roots are configurable with `PCMS_PRIVATE_MEDIA_ROOT`.
- A bounded ORM smoke script is available at `scripts/load_smoke.py`.
- Dependency auditing is standardized in `scripts/dependency_audit.ps1`.

## Required staging/CI gates

### ORM and concurrency

Run `python manage.py shell < scripts/load_smoke.py` against a staging-sized PostgreSQL/MySQL dataset and capture query plans. Run concurrent stock, invoice, and workflow tests against the production database engine; SQLite tests do not establish production locking behavior.

The inventory locking smoke test is available as `python manage.py concurrency_smoke --workers 8 --quantity 1`. Run it only against an isolated staging database because it creates a test stock item.

### Browser end-to-end testing

Run the browser checklist in `docs/STAGING_RELEASE_CHECKLIST.md` using a real HTTPS staging deployment. Automated Playwright coverage remains to be added because no browser runner is currently configured in the repository.

### Dependency audit

Run `scripts/dependency_audit.ps1` in CI or an environment with reliable network access. The local audit completed after upgrading pip to 26.2.1: no known vulnerabilities were found in installed third-party packages. The local application package was skipped because it is not published on PyPI.

### Upload malware scanning

The application validates file type, signatures, size, and image dimensions. Set `PCMS_REQUIRE_MALWARE_SCAN=True` and `PCMS_MALWARE_SCANNER_COMMAND=clamscan` (or an approved scanner wrapper) in production. Required scanning fails closed when the scanner is unavailable; development/tests remain scanner-free by default.

### CSP nonce migration

The current templates contain inline Tailwind configuration and JavaScript. The configured CSP therefore permits inline scripts for compatibility. A strict nonce-based policy requires moving inline scripts/configuration into static files or adding per-response nonces across all templates.

### Audit immutability

Audit records are immutable at the Django model layer. Database triggers, restricted database roles, and append-only archival/WORM controls must be configured per production database platform for operator-level immutability.

### Private media scaling

`PCMS_PRIVATE_MEDIA_ROOT` supports a mounted shared encrypted filesystem. If multiple instances are deployed, configure shared/object storage, backup synchronization, and authenticated application delivery before routing traffic to more than one instance.
