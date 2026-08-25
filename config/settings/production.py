"""
Production settings for Nairobi Hospice PCMS (HostPinnacle / cPanel Python / VPS Ready - No Docker required).
"""
import os

from .base import *

DEBUG = os.environ.get('DJANGO_DEBUG', 'False').lower() in ('true', '1', 'yes')
if DEBUG:
    raise RuntimeError('DJANGO_DEBUG must be False in production settings.')

SECRET_KEY = os.environ['DJANGO_SECRET_KEY']
if len(SECRET_KEY) < 50:
    raise RuntimeError('DJANGO_SECRET_KEY must contain at least 50 characters in production.')

# Allowed hosts configured via comma-separated string in .env
allowed_hosts = os.environ.get('DJANGO_ALLOWED_HOSTS', '')
if not allowed_hosts.strip():
    raise RuntimeError('DJANGO_ALLOWED_HOSTS must be explicitly configured in production.')
ALLOWED_HOSTS = [host.strip() for host in allowed_hosts.split(',') if host.strip()]

# Database configuration for HostPinnacle (supports PostgreSQL or MySQL/MariaDB)
DB_ENGINE = os.environ.get('DB_ENGINE', 'postgresql')

if DB_ENGINE == 'mysql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.mysql',
            'NAME': os.environ.get('DB_NAME', 'nairobih_pcms'),
            'USER': os.environ.get('DB_USER', 'nairobih_user'),
            'PASSWORD': os.environ['DB_PASSWORD'],
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '3306'),
            'OPTIONS': {
                'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
                'charset': 'utf8mb4',
            },
        }
    }
elif DB_ENGINE == 'postgresql':
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': os.environ.get('DB_NAME', 'nairobih_pcms'),
            'USER': os.environ.get('DB_USER', 'nairobih_user'),
            'PASSWORD': os.environ['DB_PASSWORD'],
            'HOST': os.environ.get('DB_HOST', 'localhost'),
            'PORT': os.environ.get('DB_PORT', '5432'),
        }
    }
else:
    raise RuntimeError('DB_ENGINE must be postgresql or mysql in production.')

# Security Headers & Cookies for HTTPS production
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_HSTS_SECONDS = int(os.environ.get('SECURE_HSTS_SECONDS', '31536000'))
SECURE_HSTS_INCLUDE_SUBDOMAINS = os.environ.get('SECURE_HSTS_INCLUDE_SUBDOMAINS', 'True').lower() in ('true', '1')
SECURE_HSTS_PRELOAD = os.environ.get('SECURE_HSTS_PRELOAD', 'True').lower() in ('true', '1')
SECURE_REFERRER_POLICY = os.environ.get('SECURE_REFERRER_POLICY', 'same-origin')
CONTENT_SECURITY_POLICY = os.environ.get(
    'CONTENT_SECURITY_POLICY',
    "default-src 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'; "
    "img-src 'self' data:; font-src 'self' https://fonts.gstatic.com; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "script-src 'self' 'nonce-{csp_nonce}' 'unsafe-eval'; "
    "connect-src 'self'; form-action 'self';"
)
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_HOST = os.environ.get('DJANGO_SECURE_SSL_HOST', '') or None
CSRF_TRUSTED_ORIGINS = [
    origin.strip()
    for origin in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',')
    if origin.strip()
]

def _required_true(name):
    value = os.environ.get(name)
    if value is None or value.lower() not in ('true', '1', 'yes'):
        raise RuntimeError(f'{name} must explicitly be true in production.')
    return True


CSRF_COOKIE_SECURE = _required_true('CSRF_COOKIE_SECURE')
SESSION_COOKIE_SECURE = _required_true('SESSION_COOKIE_SECURE')
SECURE_SSL_REDIRECT = _required_true('SECURE_SSL_REDIRECT')
TRUST_PROXY_HEADERS = os.environ.get('TRUST_PROXY_HEADERS', 'False').lower() in ('true', '1', 'yes')
PCMS_REQUIRE_MALWARE_SCAN = _required_true('PCMS_REQUIRE_MALWARE_SCAN')
if PCMS_REQUIRE_MALWARE_SCAN and not os.environ.get('PCMS_MALWARE_SCANNER_COMMAND'):
    raise RuntimeError('PCMS_MALWARE_SCANNER_COMMAND must be configured when malware scanning is required.')
SESSION_COOKIE_AGE = int(os.environ.get('SESSION_COOKIE_AGE', '1800'))
SESSION_EXPIRE_AT_BROWSER_CLOSE = os.environ.get('SESSION_EXPIRE_AT_BROWSER_CLOSE', 'True').lower() in ('true', '1')

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': os.environ['DJANGO_CACHE_URL'],
    },
}

# Celery in production (supports Redis or direct DB broker)
CELERY_BROKER_URL = os.environ['CELERY_BROKER_URL']
CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', CELERY_BROKER_URL)

# Email configuration
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = os.environ.get('EMAIL_HOST', 'mail.nairobihospice.or.ke')
EMAIL_PORT = int(os.environ.get('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.environ.get('EMAIL_USE_TLS', 'True').lower() in ('true', '1')
EMAIL_HOST_USER = os.environ.get('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.environ.get('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.environ.get('DEFAULT_FROM_EMAIL', 'Nairobi Hospice <noreply@nairobihospice.or.ke>')

if not CSRF_TRUSTED_ORIGINS:
    raise RuntimeError('DJANGO_CSRF_TRUSTED_ORIGINS must be configured in production.')

webhook_urls = os.environ.get('PCMS_WEBHOOK_URLS') or os.environ.get('PCMS_WEBHOOK_URL') or os.environ.get('WEBHOOK_URL')
if webhook_urls and not os.environ.get('PCMS_WEBHOOK_SECRET'):
    raise RuntimeError('PCMS_WEBHOOK_SECRET must be configured when production webhooks are enabled.')

# Sentry Monitoring (Fail-safe, PII-scrubbed)
sentry_dsn = os.environ.get('SENTRY_DSN', '').strip()
if sentry_dsn:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.django import DjangoIntegration
        from sentry_sdk.integrations.celery import CeleryIntegration
        sentry_sdk.init(
            dsn=sentry_dsn,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            traces_sample_rate=float(os.environ.get('SENTRY_TRACES_SAMPLE_RATE', '0.1')),
            send_default_pii=False,  # Never transmit PHI/PII in error traces
        )
    except ImportError:
        pass
