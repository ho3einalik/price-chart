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

@transaction.atomic
def create_return_request(order, items_data, customer_notes='', user=None):
    if not items_data:
        raise ValidationError("درخواست مرجوعی باید حداقل دارای یک ردیف کالا باشد.")

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
        refund_amount=Decimal('0')
    )

    for item_data in items_data:
        order_item = item_data['order_item']
        quantity = int(item_data['quantity'])
        reason = item_data.get('reason', 'CUSTOMER_REMORSE')

        if quantity > order_item.quantity:
            raise ValidationError(f"تعداد مرجوعی ({quantity}) نمی‌تواند از تعداد خریداری‌شده ({order_item.quantity}) بیشتر باشد.")

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
    return rma

@transaction.atomic
def approve_return_request(rma, user=None, staff_notes=''):
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
def inspect_and_process_return(rma, inspection_items_data, warehouse, user=None, refund_status=RefundStatus.REFUNDED, staff_notes=''):
    """
    Final inspection of returned items and restocking to warehouse ledger.
    inspection_items_data format: [
      {'item_id': uuid, 'condition': 'OPENED_GOOD', 'action': 'RESTOCK', 'notes': 'سالم است'}
    ]
    """
    if rma.status in [ReturnStatus.COMPLETED, ReturnStatus.REJECTED]:
        raise ValidationError(f"این مرجوعی قبلاً نهایی شده است (وضعیت: {rma.get_status_display()})")

    items_dict = {str(item.id): item for item in rma.items.select_for_update()}

    for data in inspection_items_data:
        item_id = str(data['item_id'])
        item = items_dict.get(item_id)
        if not item:
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

    rma.status = ReturnStatus.COMPLETED
    rma.refund_status = refund_status
    if staff_notes:
        rma.staff_notes = staff_notes
    rma.save(update_fields=['status', 'refund_status', 'staff_notes', 'updated_at'])

    record_audit_event(
        store=rma.store,
        user=user,
        action="RETURN_PROCESSED_AND_RESTOCKED",
        target_type="ReturnRequest",
        target_id=str(rma.id),
        changes={'rma_number': rma.rma_number, 'refund_status': refund_status}
    )
    return rma
