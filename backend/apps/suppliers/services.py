import random
from decimal import Decimal
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from .models import Supplier, PurchaseOrder, PurchaseOrderItem, PurchaseOrderStatus
from apps.inventory.services import receive_stock
from apps.audit.services import record_audit_event

def generate_po_number():
    date_str = timezone.now().strftime('%y%m%d')
    suffix = random.randint(1000, 9999)
    return f"PO-{date_str}-{suffix}"

@transaction.atomic
def create_purchase_order(store, supplier, warehouse, items_data, user=None, notes='', expected_delivery_date=None):
    if not items_data:
        raise ValidationError("سفارش خرید باید حداقل دارای یک ردیف کالا باشد.")

    po_number = generate_po_number()
    po = PurchaseOrder.objects.create(
        store=store,
        po_number=po_number,
        supplier=supplier,
        warehouse=warehouse,
        status=PurchaseOrderStatus.DRAFT,
        currency=store.currency,
        expected_delivery_date=expected_delivery_date,
        notes=notes,
        created_by=user,
        total_amount=Decimal('0')
    )

    total_amount = Decimal('0')
    for item in items_data:
        variant = item['variant']
        qty = int(item['quantity_ordered'])
        unit_cost = Decimal(str(item['unit_cost']))
        row_total = unit_cost * qty

        PurchaseOrderItem.objects.create(
            purchase_order=po,
            variant=variant,
            quantity_ordered=qty,
            quantity_received=0,
            unit_cost=unit_cost,
            total_cost=row_total
        )
        total_amount += row_total

    po.total_amount = total_amount
    po.save(update_fields=['total_amount'])

    record_audit_event(
        store=store,
        user=user,
        action="PURCHASE_ORDER_CREATED",
        target_type="PurchaseOrder",
        target_id=str(po.id),
        changes={'po_number': po.po_number, 'supplier': supplier.name, 'total_amount': str(total_amount)}
    )
    return po

@transaction.atomic
def approve_purchase_order(po, user=None):
    if po.status != PurchaseOrderStatus.DRAFT:
        raise ValidationError(f"تنها سفارشات در وضعیت پیش‌نویس قابل تایید هستند. وضعیت فعلی: {po.get_status_display()}")

    po.status = PurchaseOrderStatus.APPROVED
    po.save(update_fields=['status', 'updated_at'])

    record_audit_event(
        store=po.store,
        user=user,
        action="PURCHASE_ORDER_APPROVED",
        target_type="PurchaseOrder",
        target_id=str(po.id),
        changes={'new_status': po.status}
    )
    return po

@transaction.atomic
def mark_purchase_order_sent(po, user=None):
    if po.status not in [PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.APPROVED]:
        raise ValidationError(f"امکان ارسال سفارش خرید در وضعیت {po.get_status_display()} وجود ندارد.")

    po.status = PurchaseOrderStatus.SENT
    po.save(update_fields=['status', 'updated_at'])

    record_audit_event(
        store=po.store,
        user=user,
        action="PURCHASE_ORDER_SENT",
        target_type="PurchaseOrder",
        target_id=str(po.id),
        changes={'new_status': po.status}
    )
    return po

@transaction.atomic
def receive_po_goods(po, receipts_data, user=None):
    """
    Receive items into inventory warehouse.
    receipts_data format: [{'item_id': uuid, 'quantity_received': int}]
    """
    if po.status in [PurchaseOrderStatus.DRAFT, PurchaseOrderStatus.CANCELLED, PurchaseOrderStatus.COMPLETED]:
        raise ValidationError(f"امکان رسید کالا برای این سفارش وجود ندارد (وضعیت: {po.get_status_display()})")

    items_dict = {str(item.id): item for item in po.items.select_for_update()}
    received_anything = False

    for receipt in receipts_data:
        item_id = str(receipt['item_id'])
        qty_to_receive = int(receipt['quantity_received'])

        if qty_to_receive <= 0:
            continue

        item = items_dict.get(item_id)
        if not item:
            raise ValidationError(f"ردیف کالای انتخابی {item_id} در این سفارش خرید یافت نشد.")

        if qty_to_receive > item.remaining_quantity:
            raise ValidationError(
                f"تعداد ورودی ({qty_to_receive}) برای {item.variant.sku} نمی‌تواند بیشتر از مانده سفارش ({item.remaining_quantity}) باشد."
            )

        # Receive into double-entry inventory ledger
        receive_stock(
            store=po.store,
            warehouse=po.warehouse,
            variant=item.variant,
            quantity=qty_to_receive,
            unit_cost=item.unit_cost,
            reference=po.po_number,
            reason=f"رسید انبار از سفارش خرید {po.po_number}",
            user=user
        )

        item.quantity_received += qty_to_receive
        item.save(update_fields=['quantity_received'])
        received_anything = True

    if not received_anything:
        raise ValidationError("هیچ کالایی با تعداد معتبر جهت تحویل و رسید انبار مشخص نشده است.")

    # Check overall PO completion status
    all_completed = all(i.is_fully_received for i in po.items.all())
    po.status = PurchaseOrderStatus.COMPLETED if all_completed else PurchaseOrderStatus.PARTIALLY_RECEIVED
    po.save(update_fields=['status', 'updated_at'])

    record_audit_event(
        store=po.store,
        user=user,
        action="PURCHASE_ORDER_GOODS_RECEIVED",
        target_type="PurchaseOrder",
        target_id=str(po.id),
        changes={'status': po.status, 'receipts_count': len(receipts_data)}
    )
    return po
