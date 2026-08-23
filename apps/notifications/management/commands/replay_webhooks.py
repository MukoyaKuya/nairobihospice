from django.core.management.base import BaseCommand

from apps.notifications.models import WebhookDelivery
from apps.notifications.tasks import deliver_webhook


class Command(BaseCommand):
    help = 'Queue undelivered webhook records for retry.'

    def add_arguments(self, parser):
        parser.add_argument('--limit', type=int, default=100)

    def handle(self, *args, **options):
        deliveries = WebhookDelivery.objects.filter(delivered_at__isnull=True).order_by('created_at')[:options['limit']]
        count = 0
        for delivery in deliveries:
            deliver_webhook.delay(str(delivery.id))
            count += 1
        self.stdout.write(self.style.SUCCESS(f'Queued {count} undelivered webhook(s).'))
