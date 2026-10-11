from django.db import transaction
from django.core.exceptions import ValidationError
from .models import InventoryBalance, InventoryMovement, MovementType, Warehouse
from apps.audit.services import record_audit_event

class InsufficientStockError(Exception):
    pass

@transaction.atomic
def get_or_create_balance(store, warehouse, variant):
    balance, _ = InventoryBalance.objects.select_for_update().get_or_create(
        store=store,
        warehouse=warehouse,
        variant=variant,
        defaults={
            'on_hand_quantity': 0,
            'reserved_quantity': 0,
            'quarantined_quantity': 0,
            'incoming_quantity': 0,
        }
    )
    return balance

@transaction.atomic
def reserve_stock(store, warehouse, variant, quantity, reference='', user=None):
    """Pessimistically lock the balance row and reserve stock for an order"""
    if quantity <= 0:
        raise ValueError("Quantity to reserve must be greater than zero.")

    balance = get_or_create_balance(store, warehouse, variant)
    available = balance.available

    if available < quantity:
        raise InsufficientStockError(
            f"موجودی کافی نیست برای {variant.sku}. موجودی قابل فروش: {available}، مقدار درخواستی: {quantity}"
        )

    balance.reserved_quantity += quantity
    balance.save()

    # Record movement
    InventoryMovement.objects.create(
        store=store,
        warehouse=warehouse,
        variant=variant,
        movement_type=MovementType.RESERVATION,
        quantity=quantity,
        balance_after=balance.on_hand_quantity,
        reference=reference,
        reason=f"رزرو برای سفارش {reference}",
        user=user
    )
    return balance

@transaction.atomic
def release_stock_reservation(store, warehouse, variant, quantity, reference='', user=None):
    """Release previously reserved stock (e.g. order cancelled or expired)"""
    if quantity <= 0:
        return None

    balance = get_or_create_balance(store, warehouse, variant)
    release_qty = min(quantity, balance.reserved_quantity)
    balance.reserved_quantity -= release_qty
    balance.save()

    InventoryMovement.objects.create(
        store=store,
        warehouse=warehouse,
        variant=variant,
        movement_type=MovementType.RESERVATION_RELEASE,
        quantity=-release_qty,
        balance_after=balance.on_hand_quantity,
        reference=reference,
        reason=f"آزادسازی رزرو برای سفارش {reference}",
        user=user
    )
    return balance

@transaction.atomic
def commit_stock_sale(store, warehouse, variant, quantity, reference='', user=None):
    """Convert reservation to actual sale deduction from on_hand_quantity"""
    if quantity <= 0:
        return None

    balance = get_or_create_balance(store, warehouse, variant)
    # Deduct from reservation if available, else direct
    reserved_deduct = min(quantity, balance.reserved_quantity)
    balance.reserved_quantity -= reserved_deduct
    balance.on_hand_quantity = max(0, balance.on_hand_quantity - quantity)
    balance.save()

    InventoryMovement.objects.create(
        store=store,
        warehouse=warehouse,
        variant=variant,
        movement_type=MovementType.SALE,
        quantity=-quantity,
        balance_after=balance.on_hand_quantity,
        reference=reference,
        reason=f"تحویل سفارش {reference}",
        user=user
    )
    return balance

@transaction.atomic
def adjust_stock(store, warehouse, variant, new_on_hand, reason='', reference='', user=None):
    """Manual adjustment / stocktake reconciliation with audit trail"""
    balance = get_or_create_balance(store, warehouse, variant)
    old_on_hand = balance.on_hand_quantity
    diff = new_on_hand - old_on_hand

    balance.on_hand_quantity = new_on_hand
    balance.save()

    movement = InventoryMovement.objects.create(
        store=store,
        warehouse=warehouse,
        variant=variant,
        movement_type=MovementType.ADJUSTMENT,
        quantity=diff,
        balance_after=balance.on_hand_quantity,
        reference=reference or "MANUAL_ADJUSTMENT",
        reason=reason or "تعدیل دستی انبار",
        user=user
    )

    record_audit_event(
        store=store,
        user=user,
        action="STOCK_ADJUSTED",
        target_type="ProductVariant",
        target_id=str(variant.id),
        changes={'old_on_hand': old_on_hand, 'new_on_hand': new_on_hand, 'diff': diff, 'reason': reason}
    )
    return balance
