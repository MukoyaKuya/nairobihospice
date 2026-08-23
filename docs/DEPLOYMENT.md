# Nairobi Hospice PCMS deployment

## Runtime

Run the application with `config.settings.production` and provide all secrets through the process environment. Do not use the development settings module in a shared or public environment.

Required deployment steps:

```powershell
uv sync --extra dev --frozen
uv run python manage.py migrate --noinput
uv run python manage.py collectstatic --noinput
uv run python manage.py check --deploy
uv run python manage.py spectacular --file /tmp/openapi.yml --validate
uv run python -m pytest
```

The equivalent commands work with the system interpreter when uv is not
available: `python -m pip install -e .` followed by `python manage.py ...`.

The reverse proxy must terminate HTTPS, forward the original host and protocol correctly, and serve only static assets. Clinical documents and patient identification photographs are stored under `private_media/` and must not be exposed as public web directories. Downloads and photo delivery go through authenticated Django endpoints.

Before routing traffic to a release, verify media isolation from an external client. Requests to `/media/clinical_documents/<known-file>` and `/media/patient_photos/<known-file>` must return 404/403 without authentication; authenticated access must use the Django download/photo endpoints. This check is mandatory because web-server aliases can bypass Django authorization.

## Process responsibilities

- WSGI: `config.wsgi.application`
- ASGI: `config.asgi.application`
- Celery configuration: `config.celery`
- Liveness probe: `/health/live/`
- Readiness probe: `/health/ready/`

Run migrations as a release step before routing traffic to a new application version. Keep the previous release available until health and smoke checks pass.

## Required production checks

- `DJANGO_DEBUG=False`
- A randomly generated `DJANGO_SECRET_KEY`
- Explicit `DJANGO_ALLOWED_HOSTS`
- HTTPS, secure session cookies, and secure CSRF cookies
- Production database credentials with least privilege
- Redis credentials and network restrictions when Celery is enabled
- `DJANGO_CACHE_URL` and `CELERY_BROKER_URL` must be explicit Redis URLs; production has no localhost fallback
- `PCMS_REQUIRE_MALWARE_SCAN=True` and `PCMS_MALWARE_SCANNER_COMMAND` must be configured; production startup fails otherwise
- SMTP credentials supplied through the environment
- Private and encrypted backups configured before go-live
- Encrypted backups copied to an independent/off-site destination with restricted access
- A successful restore drill for the database and matching private media recorded before go-live
- Redis-backed cache configured for login/API throttling and Celery
- MFA enrollment completed for all privileged users

The release owner must also record a successful backup timestamp and restore-drill result. Use the runbook in `docs/BACKUP_RESTORE.md`; deployment health checks do not prove that backups are restorable.

Use `docs/STAGING_RELEASE_CHECKLIST.md` for the pre-production browser, MFA, privacy, media, and restore checks.

Do not place `.env`, database files, private media, or demo credentials in source control.
