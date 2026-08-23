import hashlib

from django.core.cache import cache

LOGIN_ATTEMPT_LIMIT = 5
LOGIN_ATTEMPT_WINDOW = 15 * 60

MFA_ATTEMPT_LIMIT = 5
MFA_ATTEMPT_WINDOW = 15 * 60


def login_attempt_key(request):
    ip = request.META.get('REMOTE_ADDR', 'unknown')
    email = request.POST.get('username', '').strip().lower()
    digest = hashlib.sha256(f'{ip}:{email}'.encode()).hexdigest()
    return f'pcms-login-attempts:{digest}'


def is_login_rate_limited(request):
    return int(cache.get(login_attempt_key(request), 0)) >= LOGIN_ATTEMPT_LIMIT


def record_failed_login(request):
    key = login_attempt_key(request)
    if cache.add(key, 1, LOGIN_ATTEMPT_WINDOW):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, LOGIN_ATTEMPT_WINDOW)
        return 1


def clear_login_attempts(request):
    cache.delete(login_attempt_key(request))


def mfa_attempt_key(user_id):
    return f'pcms-mfa-attempts:{user_id}'


def is_mfa_rate_limited(user_id) -> bool:
    return int(cache.get(mfa_attempt_key(user_id), 0)) >= MFA_ATTEMPT_LIMIT


def record_failed_mfa(user_id) -> int:
    key = mfa_attempt_key(user_id)
    if cache.add(key, 1, MFA_ATTEMPT_WINDOW):
        return 1
    try:
        return cache.incr(key)
    except ValueError:
        cache.set(key, 1, MFA_ATTEMPT_WINDOW)
        return 1


def clear_mfa_attempts(user_id):
    cache.delete(mfa_attempt_key(user_id))
