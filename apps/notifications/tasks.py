import logging

from celery import shared_task
from django.utils import timezone

from .models import WebhookDelivery
from .webhooks import send_webhook_delivery

logger = logging.getLogger(__name__)


@shared_task(bind=True, autoretry_for=(Exception,), retry_backoff=True, retry_kwargs={'max_retries': 5})
def deliver_webhook(self, delivery_id: str):
    delivery = WebhookDelivery.objects.get(pk=delivery_id)
    if delivery.delivered_at:
        return
    delivery.attempts += 1
    try:
        send_webhook_delivery(delivery)
    except Exception as exc:
        delivery.last_error = str(exc)[:2000]
        delivery.save(update_fields=['attempts', 'last_error'])
        logger.warning('Webhook delivery %s failed on attempt %s', delivery.id, delivery.attempts)
        raise
    delivery.delivered_at = timezone.now()
    delivery.last_error = ''
    delivery.save(update_fields=['attempts', 'delivered_at', 'last_error'])
