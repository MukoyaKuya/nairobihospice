import logging

from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger(__name__)


@require_GET
def live(request):
    return JsonResponse({'status': 'ok'})


def _cache_healthy():
    cache.set('healthcheck:ready', 'ok', 30)
    return cache.get('healthcheck:ready') == 'ok'


def _broker_healthy():
    """Ping the Celery broker when one is configured; skip in eager/dev setups."""
    from django.conf import settings

    broker_url = getattr(settings, 'CELERY_BROKER_URL', None)
    if not broker_url or getattr(settings, 'CELERY_TASK_ALWAYS_EAGER', False):
        return True
    try:
        from kombu import Connection

        with Connection(broker_url) as conn:
            conn.ensure_connection(max_retries=1, timeout=2)
        return True
    except Exception:
        logger.exception('Readiness broker check failed')
        return False


@require_GET
def ready(request):
    components = {}
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        components['database'] = 'ok'
    except Exception:
        logger.exception('Readiness database check failed')
        components['database'] = 'error'

    try:
        components['cache'] = 'ok' if _cache_healthy() else 'error'
    except Exception:
        logger.exception('Readiness cache check failed')
        components['cache'] = 'error'

    components['broker'] = 'ok' if _broker_healthy() else 'error'

    if 'error' in components.values():
        return JsonResponse({'status': 'not_ready', 'components': components}, status=503)
    return JsonResponse({'status': 'ready', 'components': components})
