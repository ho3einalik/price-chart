from django.db import transaction
from django.core.exceptions import ValidationError
from .models import InventoryBalance, InventoryMovement, MovementType, Warehouse
from apps.audit.services import record_audit_event

class InsufficientStockError(Exception):
    pass

@transaction.atomic
def get_or_create_balance(store, warehouse, variant):
    if warehouse.store_id != store.id:
        raise ValidationError("انبار انتخابی متعلق به این فروشگاه نیست.")
    if variant.product.store_id != store.id:
        raise ValidationError("تنوع کالای انتخابی متعلق به این فروشگاه نیست.")

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
    """Convert reservation to actual sale deduction from on_hand_quantity with strict inventory check"""
    if quantity <= 0:
        return None

    balance = get_or_create_balance(store, warehouse, variant)

    # Strictly verify on-hand quantity: NEVER silently clamp to zero
    if balance.on_hand_quantity < quantity:
        raise InsufficientStockError(
            f"موجودی فیزیکی در انبار {warehouse.name} برای {variant.sku} کافی نیست. "
            f"موجودی موجود: {balance.on_hand_quantity}، مقدار درخواستی: {quantity}"
        )

    # Deduct from reservation if available
    reserved_deduct = min(quantity, balance.reserved_quantity)
    balance.reserved_quantity -= reserved_deduct
    balance.on_hand_quantity -= quantity
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
def transfer_stock(store, source_warehouse, dest_warehouse, variant, quantity, reference='', reason='', user=None):
    """Safely transfers stock between two warehouses of the same store with ledger entries"""
    if quantity <= 0:
        raise ValueError("تعداد انتقال باید بیشتر از صفر باشد.")
    if source_warehouse.id == dest_warehouse.id:
        raise ValueError("انبار مبدا و مقصد نمی‌تواند یکسان باشد.")
    if source_warehouse.store_id != store.id or dest_warehouse.store_id != store.id:
        raise ValidationError("انبارهای مبدا و مقصد باید متعلق به همین فروشگاه باشند.")

    src_balance = get_or_create_balance(store, source_warehouse, variant)
    if src_balance.available < quantity:
        raise InsufficientStockError(f"موجودی قابل انتقال در انبار مبدا کافی نیست: {src_balance.available}")

    dest_balance = get_or_create_balance(store, dest_warehouse, variant)

    src_balance.on_hand_quantity -= quantity
    src_balance.save()

    dest_balance.on_hand_quantity += quantity
    dest_balance.save()

    InventoryMovement.objects.create(
        store=store,
        warehouse=source_warehouse,
        variant=variant,
        movement_type=MovementType.TRANSFER_OUT,
        quantity=-quantity,
        balance_after=src_balance.on_hand_quantity,
        reference=reference or f"TRF-{dest_warehouse.name}",
        reason=reason or f"انتقال خروجی به انبار {dest_warehouse.name}",
        user=user
    )

    InventoryMovement.objects.create(
        store=store,
        warehouse=dest_warehouse,
        variant=variant,
        movement_type=MovementType.TRANSFER_IN,
        quantity=quantity,
        balance_after=dest_balance.on_hand_quantity,
        reference=reference or f"TRF-{source_warehouse.name}",
        reason=reason or f"انتقال ورودی از انبار {source_warehouse.name}",
        user=user
    )

    record_audit_event(
        store=store,
        user=user,
        action="STOCK_TRANSFERRED",
        target_type="ProductVariant",
        target_id=str(variant.id),
        changes={'source': source_warehouse.name, 'dest': dest_warehouse.name, 'quantity': quantity}
    )
    return src_balance, dest_balance

@transaction.atomic
def adjust_stock(store, warehouse, variant, new_on_hand, reason='', reference='', user=None):
    """Manual adjustment / stocktake reconciliation with audit trail"""
    if new_on_hand < 0:
        raise ValueError("موجودی فیزیکی جدید نمی‌تواند کمتر از صفر باشد.")

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

@transaction.atomic
def receive_stock(store, warehouse, variant, quantity, unit_cost=None, reference='', reason='', user=None):
    """Receive new inventory from supplier purchase order or goods receipt"""
    if quantity <= 0:
        raise ValueError("تعداد ورودی کالا باید بیشتر از صفر باشد.")

    balance = get_or_create_balance(store, warehouse, variant)
    balance.on_hand_quantity += quantity
    balance.save()

    # If incoming quantity was tracked, adjust it
    if balance.incoming_quantity > 0:
        balance.incoming_quantity = max(0, balance.incoming_quantity - quantity)
        balance.save()

    # Optionally update cost price on variant if provided
    if unit_cost is not None and unit_cost > 0:
        variant.cost_price = unit_cost
        variant.save(update_fields=['cost_price', 'updated_at'])

    InventoryMovement.objects.create(
        store=store,
        warehouse=warehouse,
        variant=variant,
        movement_type=MovementType.RECEIPT,
        quantity=quantity,
        balance_after=balance.on_hand_quantity,
        reference=reference or "GOODS_RECEIPT",
        reason=reason or f"ورود کالا از فاکتور خرید {reference}",
        user=user
    )

    record_audit_event(
        store=store,
        user=user,
        action="STOCK_RECEIVED",
        target_type="ProductVariant",
        target_id=str(variant.id),
        changes={'quantity_received': quantity, 'new_on_hand': balance.on_hand_quantity, 'reference': reference}
    )
    return balance

@transaction.atomic
def process_return_stock(store, warehouse, variant, quantity, is_sellable=True, reference='', reason='', user=None):
    """Process customer return into stock (sellable restock or quarantine)"""
    if quantity <= 0:
        raise ValueError("تعداد کالای مرجوعی باید بیشتر از صفر باشد.")

    balance = get_or_create_balance(store, warehouse, variant)

    if is_sellable:
        balance.on_hand_quantity += quantity
        movement_type = MovementType.RETURN
        movement_reason = reason or f"بازگشت کالای سالم به موجودی فروش (RMA: {reference})"
    else:
        balance.on_hand_quantity += quantity
        balance.quarantined_quantity += quantity
        movement_type = MovementType.DAMAGE
        movement_reason = reason or f"قرنطینه کالای مرجوعی معیوب / غیرقابل فروش (RMA: {reference})"

    balance.save()

    InventoryMovement.objects.create(
        store=store,
        warehouse=warehouse,
        variant=variant,
        movement_type=movement_type,
        quantity=quantity,
        balance_after=balance.on_hand_quantity,
        reference=reference or "RMA_RETURN",
        reason=movement_reason,
        user=user
    )

    record_audit_event(
        store=store,
        user=user,
        action="RETURN_PROCESSED",
        target_type="ProductVariant",
        target_id=str(variant.id),
        changes={'quantity': quantity, 'is_sellable': is_sellable, 'reference': reference}
    )
    return balance

