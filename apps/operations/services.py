from django.core.exceptions import ValidationError
from django.db import transaction

from .models import (
    MovementTypeChoices,
    StockItem,
    StockMovement,
)


@transaction.atomic
def record_stock_movement(
    *,
    stock_item: StockItem,
    movement_type: str,
    quantity: int,
    reference_document: str = '',
    notes: str = '',
    user = None,
    patient = None,
    medication_statement = None,
) -> StockMovement:
    """
    Adjusts stock quantity on hand and records an immutable ledger entry.
    """
    if quantity <= 0:
        raise ValidationError('Stock movement quantity must be greater than zero.')
    if movement_type not in MovementTypeChoices.values:
        raise ValidationError(f'Unsupported stock movement type: {movement_type}')

    # Lock the row so concurrent receipts/dispenses cannot overwrite each other's balance.
    stock_item = StockItem.objects.select_for_update().get(pk=stock_item.pk)

    if movement_type == MovementTypeChoices.RECEIVE:
        stock_item.quantity_on_hand += quantity
    elif movement_type in [MovementTypeChoices.DISPENSE, MovementTypeChoices.TRANSFER, MovementTypeChoices.WASTAGE]:
        if quantity > stock_item.quantity_on_hand:
            raise ValidationError(
                f'Insufficient stock for {stock_item.name}: '
                f'{stock_item.quantity_on_hand} available, {quantity} requested.'
            )
        stock_item.quantity_on_hand -= quantity
    elif movement_type == MovementTypeChoices.ADJUSTMENT:
        stock_item.quantity_on_hand = quantity

    stock_item.save(update_fields=['quantity_on_hand', 'updated_at'])

    movement = StockMovement.objects.create(
        stock_item=stock_item,
        movement_type=movement_type,
        quantity=quantity,
        balance_after=stock_item.quantity_on_hand,
        reference_document=reference_document,
        patient=patient,
        medication_statement=medication_statement,
        notes=notes,
        recorded_by=user,
    )
    return movement
