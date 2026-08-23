import hashlib
import hmac
import json
import logging
import os
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any, Dict, List
from urllib.parse import urlparse

from django.conf import settings
from django.db import transaction

from .models import WebhookDelivery

logger = logging.getLogger(__name__)


def _get_webhook_urls() -> List[str]:
    configured = getattr(settings, 'PCMS_WEBHOOK_URLS', None)
    raw_urls = configured or os.environ.get('PCMS_WEBHOOK_URL') or os.environ.get('WEBHOOK_URL')
    if isinstance(raw_urls, str):
        urls = [url.strip() for url in raw_urls.split(',') if url.strip()]
    else:
        urls = [str(url).strip() for url in (raw_urls or []) if str(url).strip()]

    allow_insecure = bool(getattr(settings, 'DEBUG', False) and getattr(settings, 'PCMS_ALLOW_INSECURE_WEBHOOKS', False))
    safe_urls = []
    for url in urls:
        if urlparse(url).scheme == 'https' or (allow_insecure and urlparse(url).scheme == 'http'):
            safe_urls.append(url)
        else:
            logger.warning('Ignoring webhook URL without an allowed HTTPS scheme: %s', url)
    return safe_urls


def dispatch_webhook_event(event_name: str, payload: Dict[str, Any]):
    """Persist deliveries and enqueue them only after the surrounding transaction commits."""
    urls = _get_webhook_urls()
    if not urls:
        return

    full_payload = {
        'event': event_name,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'facility': 'Nairobi Hospice',
        'data': payload,
    }
    deliveries = [WebhookDelivery(event_name=event_name, url=url, payload=full_payload) for url in urls]
    WebhookDelivery.objects.bulk_create(deliveries)
    delivery_ids = [delivery.id for delivery in deliveries]

    def enqueue():
        from .tasks import deliver_webhook
        for delivery_id in delivery_ids:
            deliver_webhook.delay(str(delivery_id))

    transaction.on_commit(enqueue)


def send_webhook_delivery(delivery: WebhookDelivery):
    payload_json = json.dumps(delivery.payload, default=str)
    secret = getattr(settings, 'PCMS_WEBHOOK_SECRET', os.environ.get('PCMS_WEBHOOK_SECRET', ''))
    signature = hmac.new(secret.encode(), payload_json.encode(), hashlib.sha256).hexdigest()
    req = urllib.request.Request(
        delivery.url,
        data=payload_json.encode('utf-8'),
        headers={
            'Content-Type': 'application/json',
            'User-Agent': 'NairobiHospice-PCMS-Webhook/1.0',
            'X-PCMS-Signature': signature,
            'X-PCMS-Delivery': datetime.now(timezone.utc).isoformat(),
            'X-PCMS-Event-ID': str(delivery.id),
        },
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=4.0) as response:
        if not 200 <= response.getcode() < 300:
            raise urllib.error.HTTPError(delivery.url, response.getcode(), 'non-success response', response.headers, None)
