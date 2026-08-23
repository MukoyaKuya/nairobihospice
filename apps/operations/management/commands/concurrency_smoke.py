from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from django.core.management.base import BaseCommand, CommandError
from django.db import close_old_connections

from apps.operations.models import MovementTypeChoices, StockItem
from apps.operations.services import record_stock_movement


class Command(BaseCommand):
    help = 'Exercise concurrent stock movements; run against staging PostgreSQL/MySQL.'

    def add_arguments(self, parser):
        parser.add_argument('--workers', type=int, default=8)
        parser.add_argument('--quantity', type=int, default=1)

    def handle(self, *args, **options):
        workers = options['workers']
        quantity = options['quantity']
        if workers < 2 or quantity < 1:
            raise CommandError('workers must be at least 2 and quantity must be positive.')

        item = StockItem.objects.create(
            item_code=f'CONC-{uuid4().hex[:12].upper()}',
            name='Concurrency smoke item',
            quantity_on_hand=workers * quantity,
        )

        def dispense(_):
            close_old_connections()
            try:
                record_stock_movement(
                    stock_item=item,
                    movement_type=MovementTypeChoices.DISPENSE,
                    quantity=quantity,
                )
                return True
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=workers) as executor:
            results = list(executor.map(dispense, range(workers)))

        item.refresh_from_db()
        expected = 0
        if not all(results) or item.quantity_on_hand != expected:
            raise CommandError(
                f'Concurrency check failed: successful={sum(results)}, '
                f'expected_balance={expected}, actual_balance={item.quantity_on_hand}'
            )
        self.stdout.write(self.style.SUCCESS(f'Concurrency check passed with {workers} workers.'))
