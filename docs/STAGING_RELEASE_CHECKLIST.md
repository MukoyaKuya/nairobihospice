# Staging release checklist

Run staging with `config.settings.production`, a non-production database, Redis-backed cache/Celery, HTTPS, SMTP test delivery, and a private-media directory that is not web-served.

## Automated gate

Set the staging environment variables, then run:

```powershell
.\scripts\staging_smoke.ps1
```

The script checks unapplied migrations, deployment security settings, OpenAPI validation, and the full test suite.

## Browser smoke tests

Automated Playwright suite:

```powershell
cd e2e
npm install
npx playwright install chromium
$env:PCMS_E2E_BASE_URL = 'https://staging.example.invalid'
$env:PCMS_E2E_RECEPTION_EMAIL = 'staging-reception@example.invalid'
$env:PCMS_E2E_RECEPTION_PASSWORD = '<secret from staging secret store>'
npm test
```

Set `PCMS_E2E_MANAGER_EMAIL` and `PCMS_E2E_MANAGER_PASSWORD` to include the privileged MFA flow. Do not commit these values.

- Sign in as receptionist, clinician, manager, and administrator.
- Confirm receptionist patient views contain demographics but not diagnosis, allergies, clinical notes, documents, or clinical appointment reasons.
- Confirm an unrelated clinician receives 404/empty results for another clinician's patient, referral, appointment, photo, and document.
- Enroll a manager in MFA, verify a TOTP login, consume one recovery code, and confirm the used code is rejected.
- Request a password reset through staging SMTP and complete the reset link.
- Confirm `/health/live/` and `/health/ready/` return success.
- Confirm clinical document and patient-photo URLs are authenticated endpoints, not public media URLs.
- Run `scripts/verify_private_media_isolation.ps1` against a known private document and photo path; both public requests must return 403 or 404.

## Release evidence

Attach the deployment commit, migration output, test output, backup timestamp, restore-drill result, RPO/RTO measurement, and reviewer approval to the release record.
