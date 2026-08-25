"""
Test settings for Nairobi Hospice PCMS.
"""
from .base import *

DEBUG = False
SECRET_KEY = 'test-secret-key-nairobi-hospice-pcms-testing'
ALLOWED_HOSTS = ['*']

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': ':memory:',
    }
}

PASSWORD_HASHERS = [
    'django.contrib.auth.hashers.MD5PasswordHasher',
]

CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

MFA_ENFORCEMENT_MIDDLEWARE_ENABLED = False

EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
