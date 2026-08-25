# Nairobi Hospice PCMS: Production Deployment & Server Operations Runbook

This runbook specifies the step-by-step procedures for deploying, hardening, and operating the Nairobi Hospice PCMS in a production environment (HostPinnacle VPS / Linux Server).

---

## 1. Pre-Deployment Environment Setup

### 1.1 Python & System Dependencies
```bash
sudo apt-get update
sudo apt-get install -y python3.12 python3.12-venv python3-pip clamav clamav-daemon redis-server postgresql-client
```

### 1.2 Environment File (`.env`) Configuration
Create `/var/www/pcms/.env` with permissions `600` owned by the application service user:
```ini
DJANGO_SECRET_KEY=<generate-at-least-50-random-characters>
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=pcms.nairobihospice.or.ke,nairobihospice.or.ke
DJANGO_CSRF_TRUSTED_ORIGINS=https://pcms.nairobihospice.or.ke,https://nairobihospice.or.ke

# Database (PostgreSQL 14+ or MySQL 8.0.16+)
DB_ENGINE=postgresql
DB_NAME=nairobih_pcms
DB_USER=nairobih_user
DB_PASSWORD=<strong-db-password>
DB_HOST=127.0.0.1
DB_PORT=5432

# Redis & Celery
DJANGO_CACHE_URL=redis://127.0.0.1:6379/1
CELERY_BROKER_URL=redis://127.0.0.1:6379/0
CELERY_RESULT_BACKEND=redis://127.0.0.1:6379/0

# Security, SSL & Cookies
CSRF_COOKIE_SECURE=True
SESSION_COOKIE_SECURE=True
SECURE_SSL_REDIRECT=True
MFA_REQUIRED_FOR_PRIVILEGED=True
MFA_REQUIRED_FOR_ALL_STAFF=True
SESSION_COOKIE_AGE=1800
SESSION_EXPIRE_AT_BROWSER_CLOSE=True

# Malware Defense (Fail-closed)
PCMS_REQUIRE_MALWARE_SCAN=True
PCMS_MALWARE_SCANNER_COMMAND=clamscan

# Monitoring
SENTRY_DSN=https://<key>@<org>.ingest.sentry.io/<id>
```

---

## 2. Database Migrations & Integrity Verification

### 2.1 Apply Migrations
```bash
python manage.py migrate --settings=config.settings.production
```

### 2.2 Verify Database CHECK Constraints & Triggers

#### PostgreSQL Verification:
```sql
-- Check table constraints
SELECT conname, pg_get_constraintdef(c.oid)
FROM pg_constraint c
WHERE conrelid = 'operations_stockmovement'::regclass;

-- Check trigger functions
SELECT tgname, proname
FROM pg_trigger t
JOIN pg_proc p ON t.tgfoid = p.oid
WHERE tgrelid = 'operations_stockmovement'::regclass;
```

#### MySQL 8.0.16+ Verification:
```sql
SELECT CONSTRAINT_NAME, CHECK_CLAUSE
FROM INFORMATION_SCHEMA.CHECK_CONSTRAINTS
WHERE CONSTRAINT_SCHEMA = 'nairobih_pcms';

SHOW TRIGGERS LIKE 'operations_stockmovement';
```

---

## 3. Webserver & Private Media Isolation (Nginx)

### 3.1 Nginx Site Configuration Block
Ensure `private_media/` is **NEVER** aliased in Nginx. All document/photo requests must pass through Django authentication:

```nginx
server {
    server_name pcms.nairobihospice.or.ke;
    listen 443 ssl http2;

    ssl_certificate /etc/letsencrypt/live/pcms.nairobihospice.or.ke/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/pcms.nairobihospice.or.ke/privkey.pem;

    # Static assets (public CSS/JS/images)
    location /static/ {
        alias /var/www/pcms/staticfiles/;
        expires 30d;
        access_log off;
    }

    # CRITICAL: Do NOT create any location block for /private_media/ or /media/
    # Gunicorn / WSGI application proxy
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 3.2 Verify Media Isolation via Script
```powershell
pwsh scripts/verify_private_media_isolation.ps1 -BaseUrl "https://pcms.nairobihospice.or.ke" -KnownPrivatePath "media/clinical_documents/example.pdf"
```

---

## 4. Background Workers & Celery

Create systemd unit file `/etc/systemd/system/pcms-celery.service`:
```ini
[Unit]
Description=Nairobi Hospice PCMS Celery Worker
After=network.target redis-server.service

[Service]
Type=forking
User=pcms
Group=pcms
WorkingDirectory=/var/www/pcms
ExecStart=/var/www/pcms/.venv/bin/celery -A config worker --loglevel=INFO --detach
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 5. Security & Deployment Check

Run Django's deployment audit:
```bash
python manage.py check --deploy --settings=config.settings.production
```
Expected output:
```
System check identified no issues (0 silenced).
```
