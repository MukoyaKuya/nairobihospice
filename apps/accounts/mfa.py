import base64
import hashlib
import hmac
import secrets
import time
from urllib.parse import quote

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.cache import cache
from django.db import transaction

ISSUER = 'Nairobi Hospice PCMS'


def _get_fernet():
    """Derives a 32-byte Fernet key from the Django SECRET_KEY."""
    raw_key = hashlib.sha256(settings.SECRET_KEY.encode('utf-8')).digest()
    return Fernet(base64.urlsafe_b64encode(raw_key))


def encrypt_mfa_secret(secret: str) -> str:
    """Encrypt the plaintext base32 TOTP secret at rest before saving to database."""
    if not secret:
        return ''
    f = _get_fernet()
    return f.encrypt(secret.encode('utf-8')).decode('utf-8')


def decrypt_mfa_secret(stored_val: str) -> str:
    """Decrypt the stored ciphertext. Handles legacy unencrypted base32 secrets gracefully."""
    if not stored_val:
        return ''
    f = _get_fernet()
    try:
        return f.decrypt(stored_val.encode('utf-8')).decode('utf-8')
    except (InvalidToken, Exception):
        import re
        if re.fullmatch(r'[A-Z2-7]{16,64}', stored_val.strip()):
            return stored_val.strip()
        return ''


# A token stays valid for at most verify_totp's window (±1 step). Remembering
# used tokens for twice that span makes replay impossible even with clock skew.
TOTP_REPLAY_TTL = 3 * 60


def generate_secret():
    return base64.b32encode(secrets.token_bytes(20)).decode('ascii').rstrip('=')


def _counter_bytes(counter):
    return counter.to_bytes(8, 'big')


def generate_totp(secret, timestamp=None, interval=30):
    if not secret:
        return ''
    timestamp = int(time.time() if timestamp is None else timestamp)
    counter = timestamp // interval
    key = base64.b32decode(secret + '=' * (-len(secret) % 8), casefold=True)
    digest = hmac.new(key, _counter_bytes(counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = int.from_bytes(digest[offset:offset + 4], 'big') & 0x7FFFFFFF
    return f'{value % 1_000_000:06d}'


def verify_totp(secret, token, timestamp=None, window=1):
    if not secret or not token or not token.isdigit() or len(token) != 6:
        return False
    now = int(time.time() if timestamp is None else timestamp)
    return any(
        hmac.compare_digest(generate_totp(secret, now + offset * 30), token)
        for offset in range(-window, window + 1)
    )


def _totp_replay_key(user, token):
    return f'pcms-totp-used:{user.pk}:{token}'


def verify_totp_for_user(user, token):
    """Verify a TOTP code and reject reuse of an already-consumed code."""
    raw_secret = decrypt_mfa_secret(user.mfa_secret)
    if not verify_totp(raw_secret, token):
        return False
    if not cache.add(_totp_replay_key(user, token), 1, TOTP_REPLAY_TTL):
        return False
    if user.mfa_secret and not user.mfa_secret.startswith('gAAAAA'):
        user.mfa_secret = encrypt_mfa_secret(raw_secret)
        user.save(update_fields=['mfa_secret'])
    return True


def provisioning_uri(secret, email):
    label = quote(f'{ISSUER}:{email}')
    return f'otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}&algorithm=SHA1&digits=6&period=30'


def generate_recovery_codes(count=10):
    plain_codes = [secrets.token_hex(5).upper() for _ in range(count)]
    return plain_codes, [make_password(code) for code in plain_codes]


def consume_recovery_code(user, code):
    if not code:
        return False
    with transaction.atomic():
        locked_user = user.__class__.objects.select_for_update().get(pk=user.pk)
        stored_codes = list(locked_user.mfa_recovery_codes or [])
        for index, stored_code in enumerate(stored_codes):
            if check_password(code.strip().upper(), stored_code):
                stored_codes.pop(index)
                locked_user.mfa_recovery_codes = stored_codes
                locked_user.save(update_fields=['mfa_recovery_codes'])
                return True
        return False


def privileged_user_requires_mfa(user):
    from django.conf import settings

    return bool(
        getattr(settings, 'MFA_REQUIRED_FOR_PRIVILEGED', True)
        and user
        and user.is_authenticated
        and (
            user.is_superuser
            or user.is_manager
            or user.is_clinical
            or getattr(user, 'is_pharmacist', False)
            or getattr(user, 'is_receptionist', False)
        )
    )
