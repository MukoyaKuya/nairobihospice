"""
Base settings for Nairobi Hospice Palliative Care Management System.
"""
import os
from pathlib import Path

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Application definition
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY')
if not SECRET_KEY and os.environ.get('DJANGO_SETTINGS_MODULE', '').endswith('.production'):
    # Production must never silently boot with a shared signing key.
    raise RuntimeError('DJANGO_SECRET_KEY must be configured.')
SECRET_KEY = SECRET_KEY or 'local-development-only-key-change-me'
DEBUG = False
ALLOWED_HOSTS = []

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'django_filters',
    'django_htmx',
    'corsheaders',
    'drf_spectacular',
]

LOCAL_APPS = [
    'apps.accounts.apps.AccountsConfig',
    'apps.patients.apps.PatientsConfig',
    'apps.referrals.apps.ReferralsConfig',
    'apps.care.apps.CareConfig',
    'apps.encounters.apps.EncountersConfig',
    'apps.assessments.apps.AssessmentsConfig',
    'apps.symptoms.apps.SymptomsConfig',
    'apps.medications.apps.MedicationsConfig',
    'apps.appointments.apps.AppointmentsConfig',
    'apps.communications.apps.CommunicationsConfig',
    'apps.documents.apps.DocumentsConfig',
    'apps.notifications.apps.NotificationsConfig',
    'apps.reporting.apps.ReportingConfig',
    'apps.operations.apps.OperationsConfig',
    'apps.audit.apps.AuditConfig',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'apps.audit.middleware.BrandedErrorMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'apps.audit.middleware.HtmxAuthRedirectMiddleware',
    'apps.audit.middleware.AuditMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.notifications.context_processors.unread_notifications_processor',
                'apps.accounts.context_processors.user_role_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator', 'OPTIONS': {'min_length': 12}},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# Authentication URLs
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'reporting:clinical_dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'
MFA_REQUIRED_FOR_PRIVILEGED = os.environ.get('MFA_REQUIRED_FOR_PRIVILEGED', 'True').lower() in ('true', '1', 'yes')
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_SAVE_EVERY_REQUEST = True
PASSWORD_RESET_TIMEOUT = 60 * 60

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Africa/Nairobi'
USE_I18N = True
USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
PRIVATE_MEDIA_ROOT = Path(os.environ.get('PCMS_PRIVATE_MEDIA_ROOT', BASE_DIR / 'private_media'))
PCMS_REQUIRE_MALWARE_SCAN = False
PCMS_MALWARE_SCANNER_COMMAND = os.environ.get('PCMS_MALWARE_SCANNER_COMMAND', '')
PCMS_MALWARE_SCAN_TIMEOUT = int(os.environ.get('PCMS_MALWARE_SCAN_TIMEOUT', '30'))

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Django REST Framework
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'api.v1.exception_handlers.api_exception_handler',
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle',
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '30/minute',
        'user': '300/minute',
    },
}

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'nairobi-hospice-pcms-development',
    },
}

# OpenAPI Docs (drf-spectacular)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Nairobi Hospice PCMS API',
    'DESCRIPTION': 'Clinical and Operational API for Nairobi Hospice Palliative Care Management System',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
}

# Celery Configuration
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60

# Keep application diagnostics available in every environment. Deployments can route
# these loggers to their platform's structured logging collector.
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {name} request_id={request_id} {message}',
            'style': '{',
            'defaults': {'request_id': '-'},
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'apps': {'handlers': ['console'], 'level': 'INFO', 'propagate': False},
    },
}

# Forwarded client IP headers are disabled by default. Production must enable
# this only when its trusted reverse proxy strips and rewrites the header.
TRUST_PROXY_HEADERS = False
