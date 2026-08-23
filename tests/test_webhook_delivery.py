import pytest
from django.db import transaction
from django.test import override_settings

from apps.notifications.models import WebhookDelivery
from apps.notifications.webhooks import dispatch_webhook_event


@pytest.mark.django_db(transaction=True)
@override_settings(PCMS_WEBHOOK_URLS=['https://hooks.example.test/pcms'], PCMS_WEBHOOK_SECRET='test-secret')
def test_webhook_is_persisted_and_enqueued_after_commit(monkeypatch):
    queued = []
    monkeypatch.setattr(
        'apps.notifications.tasks.deliver_webhook.delay',
        lambda delivery_id: queued.append(delivery_id),
    )

    with transaction.atomic():
        dispatch_webhook_event('patient.registered', {'patient_id': 'p-1'})
        delivery = WebhookDelivery.objects.get()
        assert queued == []
        assert delivery.delivered_at is None

    assert queued == [str(delivery.id)]


@pytest.mark.django_db(transaction=True)
@override_settings(PCMS_WEBHOOK_URLS=['https://hooks.example.test/pcms'], PCMS_WEBHOOK_SECRET='test-secret')
def test_webhook_is_not_created_when_transaction_rolls_back(monkeypatch):
    queued = []
    monkeypatch.setattr(
        'apps.notifications.tasks.deliver_webhook.delay',
        lambda delivery_id: queued.append(delivery_id),
    )

    with pytest.raises(RuntimeError):
        with transaction.atomic():
            dispatch_webhook_event('patient.registered', {'patient_id': 'p-2'})
            raise RuntimeError('rollback')

    assert WebhookDelivery.objects.count() == 0
    assert queued == []
