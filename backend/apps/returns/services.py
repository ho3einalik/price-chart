import random
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import (
    ReturnRequest, ReturnItem, ReturnStatus, RefundStatus, ReturnAction
)
from apps.orders.models import FulfillmentStatus
from apps.inventory.services import process_return_stock
from apps.audit.services import record_audit_event

def generate_rma_number():
    date_str = timezone.now().strftime('%y%m%d')
    suffix = random.randint(1000, 9999)
    return f"RMA-{date_str}-{suffix}"

from django.db.models import Sum
from apps.orders.models import Order, OrderItem, FulfillmentStatus, OrderStatus

@transaction.atomic
def create_return_request(
    order, items_data, customer_notes='', user=None,
    is_exchange=False, exchange_variant=None, exchange_quantity=0, exchange_price_difference=Decimal('0')
):
    if not items_data:
        raise ValidationError("درخواست مرجوعی باید حداقل دارای یک ردیف کالا باشد.")

    # Pessimistically lock Order to serialize return creations and status checks
    order = Order.objects.select_for_update().get(id=order.id)

    # Validate that order has been fulfilled or partially fulfilled
    if order.fulfillment_status not in [FulfillmentStatus.FULFILLED, FulfillmentStatus.PARTIALLY_FULFILLED] and order.order_status not in [OrderStatus.FULFILLED, OrderStatus.COMPLETED]:
        raise ValidationError("تنها برای سفارش‌هایی که ارسال شده‌اند امکان ثبت مرجوعی وجود دارد.")

    # Deadlock-free locking: collect unique order item IDs and lock in consistent sorted order
    item_ids = sorted(list({item_data['order_item'].id for item_data in items_data}))
    locked_items = {
        item.id: item
        for item in OrderItem.objects.select_for_update().filter(id__in=item_ids, order=order).order_by('id')
    }

    rma_number = generate_rma_number()
    total_refund = Decimal('0')

    rma = ReturnRequest.objects.create(
        store=order.store,
        rma_number=rma_number,
        order=order,
        customer=order.customer,
        status=ReturnStatus.REQUESTED,
        refund_status=RefundStatus.PENDING,
        customer_notes=customer_notes,
        created_by=user,
        refund_amount=Decimal('0'),
        is_exchange=is_exchange,
        exchange_variant=exchange_variant,
        exchange_quantity=exchange_quantity,
        exchange_price_difference=exchange_price_difference
    )

    for item_data in items_data:
        raw_order_item = item_data['order_item']
        order_item = locked_items.get(raw_order_item.id)
        if not order_item:
            raise ValidationError(f"ردیف کالای انتخابی ({raw_order_item.id}) متعلق به این سفارش نیست.")

        quantity = int(item_data['quantity'])
        reason = item_data.get('reason', 'CUSTOMER_REMORSE')

        if quantity <= 0:
            raise ValidationError("تعداد کالای مرجوعی باید بزرگتر از صفر باشد.")

        # Calculate already returned quantity for this order item across all active RMAs under row lock
        prior_returned = ReturnItem.objects.filter(
            order_item=order_item
        ).exclude(
            return_request__status=ReturnStatus.REJECTED
        ).aggregate(total=Sum('quantity'))['total'] or 0

        remaining_returnable = order_item.quantity - prior_returned
        if quantity > remaining_returnable:
            raise ValidationError(
                f"تعداد مرجوعی درخواستی ({quantity}) برای {order_item.variant_sku} نمی‌تواند از مانده قابل مرجوعی ({remaining_returnable}) بیشتر باشد. "
                f"(تعداد کل خریداری‌شده: {order_item.quantity}، قبلاً مرجوع‌شده: {prior_returned})"
            )

        unit_refund = order_item.unit_price - order_item.unit_discount
        total_refund += unit_refund * quantity

        ReturnItem.objects.create(
            return_request=rma,
            order_item=order_item,
            variant=order_item.variant,
            quantity=quantity,
            reason=reason
        )

    rma.refund_amount = total_refund
    rma.save(update_fields=['refund_amount'])

    record_audit_event(
        store=order.store,
        user=user,
        action="RETURN_REQUEST_CREATED",
        target_type="ReturnRequest",
        target_id=str(rma.id),
        changes={'rma_number': rma.rma_number, 'order': order.order_number, 'refund_amount': str(total_refund)}
    )

    def _dispatch_return_requested():
        try:
            from apps.automation.services import trigger_automation
            from apps.automation.models import TriggerEvent
            trigger_automation(
                store=order.store,
                trigger_event=TriggerEvent.RETURN_REQUESTED,
                payload={
                    'rma_id': str(rma.id),
                    'rma_number': rma.rma_number,
                    'order_number': order.order_number,
                    'customer_name': order.customer.full_name,
                    'customer_phone': order.customer.phone_number,
                    'refund_amount': float(rma.refund_amount),
                    'idempotency_key': f"return_requested_{rma.id}"
                }
            )
        except Exception:
            pass

    transaction.on_commit(_dispatch_return_requested)
    return rma

@transaction.atomic
def approve_return_request(rma, user=None, staff_notes=''):
    rma = ReturnRequest.objects.select_for_update().get(id=rma.id)
    if rma.status != ReturnStatus.REQUESTED:
        raise ValidationError(f"تنها درخواست‌های جدید قابل تایید هستند. وضعیت فعلی: {rma.get_status_display()}")

    rma.status = ReturnStatus.APPROVED
    if staff_notes:
        rma.staff_notes = staff_notes
    rma.save(update_fields=['status', 'staff_notes', 'updated_at'])

    record_audit_event(
        store=rma.store,
        user=user,
        action="RETURN_REQUEST_APPROVED",
        target_type="ReturnRequest",
        target_id=str(rma.id),
        changes={'new_status': rma.status}
    )
    return rma

@transaction.atomic
def inspect_and_process_return(rma, inspection_items_data, warehouse, user=None, refund_status=RefundStatus.PENDING, staff_notes=''):
    """
    Final inspection of returned items and restocking to warehouse ledger.
    Connects to Finance RefundRecord to ensure refunds are tracked and not fabricated.
    """
    rma = ReturnRequest.objects.select_for_update().get(id=rma.id)
    if rma.status in [ReturnStatus.COMPLETED, ReturnStatus.REJECTED]:
        raise ValidationError(f"این مرجوعی قبلاً نهایی شده است (وضعیت: {rma.get_status_display()})")
    if rma.status != ReturnStatus.APPROVED:
        raise ValidationError(f"تنها درخواست‌های مرجوعی تأییدشده توسط مدیر قابل بازرسی و فرآوری هستند. وضعیت فعلی: {rma.get_status_display()}")

    items_dict = {str(item.id): item for item in rma.items.select_for_update()}

    for data in inspection_items_data:
        item_id = str(data['item_id'])
        item = items_dict.get(item_id)
        if not item or item.is_inspected:
            continue

        item.condition = data.get('condition', item.condition)
        item.action = data.get('action', item.action)
        item.inspection_notes = data.get('notes', '')
        item.is_inspected = True
        item.save()

        # Update physical inventory
        if item.action == ReturnAction.RESTOCK:
            process_return_stock(
                store=rma.store,
                warehouse=warehouse,
                variant=item.variant,
                quantity=item.quantity,
                is_sellable=True,
                reference=rma.rma_number,
                reason=f"بازگشت کالا از مرجوعی {rma.rma_number} به انبار {warehouse.name}",
                user=user
            )
        elif item.action == ReturnAction.QUARANTINE_SCRAP:
            process_return_stock(
                store=rma.store,
                warehouse=warehouse,
                variant=item.variant,
                quantity=item.quantity,
                is_sellable=False,
                reference=rma.rma_number,
                reason=f"قرنطینه کالای معیوب مرجوعی {rma.rma_number}",
                user=user
            )

    # Handle item exchange dispatch from inventory
    if rma.is_exchange and rma.exchange_variant and rma.exchange_quantity > 0:
        from apps.inventory.services import get_or_create_balance, MovementType, InventoryMovement
        exchange_bal = get_or_create_balance(rma.store, warehouse, rma.exchange_variant)
        if exchange_bal.on_hand_quantity < rma.exchange_quantity:
            raise ValidationError(
                f"موجودی انبار {warehouse.name} برای ارسال کالای جایگزین ({rma.exchange_variant.sku}) کافی نیست. "
                f"موجودی فعلی: {exchange_bal.on_hand_quantity}، تعداد موردنیاز: {rma.exchange_quantity}"
            )
        exchange_bal.on_hand_quantity -= rma.exchange_quantity
        exchange_bal.save()

        InventoryMovement.objects.create(
            store=rma.store,
            warehouse=warehouse,
            variant=rma.exchange_variant,
            movement_type=MovementType.SALE,
            quantity=-rma.exchange_quantity,
            balance_after=exchange_bal.on_hand_quantity,
            reference=f"EXCHANGE_{rma.rma_number}",
            reason=f"خروج کالای تعویضی بابت مرجوعی {rma.rma_number}",
            user=user
        )

    rma.status = ReturnStatus.COMPLETED
    rma.refund_status = refund_status
    if staff_notes:
        rma.staff_notes = staff_notes
    rma.save(update_fields=['status', 'refund_status', 'staff_notes', 'updated_at'])

    # Synchronize financial refund record in apps.finance
    if rma.refund_amount > 0:
        try:
            from apps.finance.models import RefundRecord, RefundStatus as FinRefundStatus
            fin_status = FinRefundStatus.COMPLETED if refund_status == RefundStatus.REFUNDED else FinRefundStatus.PENDING
            RefundRecord.objects.get_or_create(
                store=rma.store,
                order=rma.order,
                reason=f"استرداد وجه بابت مرجوعی {rma.rma_number}",
                defaults={
                    'amount': rma.refund_amount,
                    'status': fin_status,
                    'processed_by': user if refund_status == RefundStatus.REFUNDED else None,
                    'processed_at': timezone.now() if refund_status == RefundStatus.REFUNDED else None,
                }
            )
        except Exception:
            pass

    record_audit_event(
        store=rma.store,
        user=user,
        action="RETURN_PROCESSED_AND_RESTOCKED",
        target_type="ReturnRequest",
        target_id=str(rma.id),
        changes={'rma_number': rma.rma_number, 'refund_status': refund_status}
    )
    return rma
