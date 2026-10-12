import pytest
from decimal import Decimal
from apps.suppliers.models import Supplier, PurchaseOrder, PurchaseOrderStatus
from apps.suppliers.services import create_purchase_order, approve_purchase_order, receive_po_goods
from apps.returns.models import ReturnRequest, ReturnStatus, ReturnAction, RefundStatus
from apps.returns.services import create_return_request, approve_return_request, inspect_and_process_return
from apps.inventory.models import InventoryBalance, InventoryMovement, MovementType
from apps.orders.models import Order, OrderItem, OrderStatus, PaymentStatus

@pytest.mark.django_db
def test_supplier_po_lifecycle_and_inventory_receipt(store_a, warehouse_a, variant_a1, admin_user_a):
    supplier = Supplier.objects.create(
        store=store_a,
        name="تولیدی نوین پوشاک",
        contact_name="آقای احمدی",
        phone_number="09121112233"
    )

    items_data = [{
        'variant': variant_a1,
        'quantity_ordered': 20,
        'unit_cost': Decimal('150000')
    }]

    po = create_purchase_order(
        store=store_a,
        supplier=supplier,
        warehouse=warehouse_a,
        items_data=items_data,
        user=admin_user_a,
        notes="سفارش خرید بهاره"
    )

    assert po.status == PurchaseOrderStatus.DRAFT
    assert po.total_amount == Decimal('3000000')
    po_item = po.items.first()
    assert po_item.quantity_ordered == 20
    assert po_item.quantity_received == 0

    # Approve PO
    approve_purchase_order(po, user=admin_user_a)
    po.refresh_from_db()
    assert po.status == PurchaseOrderStatus.APPROVED

    # Receive partial goods (10 items)
    balance_before = InventoryBalance.objects.get(warehouse=warehouse_a, variant=variant_a1).on_hand_quantity
    receipts_data = [{'item_id': str(po_item.id), 'quantity_received': 10}]
    receive_po_goods(po, receipts_data, user=admin_user_a)

    po.refresh_from_db()
    po_item.refresh_from_db()
    assert po.status == PurchaseOrderStatus.PARTIALLY_RECEIVED
    assert po_item.quantity_received == 10
    assert po_item.remaining_quantity == 10

    # Verify double-entry inventory ledger recorded RECEIPT
    balance_after = InventoryBalance.objects.get(warehouse=warehouse_a, variant=variant_a1).on_hand_quantity
    assert balance_after == balance_before + 10

    last_movement = InventoryMovement.objects.filter(variant=variant_a1).order_by('-created_at').first()
    assert last_movement.movement_type == MovementType.RECEIPT
    assert last_movement.quantity == 10


@pytest.mark.django_db
def test_customer_return_rma_inspection_and_restock(store_a, warehouse_a, variant_a1, customer_a, admin_user_a):
    order = Order.objects.create(
        store=store_a,
        order_number="ORD-RET-TEST",
        customer=customer_a,
        warehouse=warehouse_a,
        order_status=OrderStatus.COMPLETED,
        payment_status=PaymentStatus.PAID,
        total_items_price=Decimal('500000'),
        grand_total=Decimal('500000')
    )

    order_item = OrderItem.objects.create(
        order=order,
        variant=variant_a1,
        variant_sku=variant_a1.sku,
        variant_name="پیراهن نخی",
        quantity=2,
        unit_price=Decimal('250000'),
        cost_price_snapshot=Decimal('150000'),
        total_price=Decimal('500000')
    )

    # Customer submits return request
    rma = create_return_request(
        order=order,
        items_data=[{'order_item': order_item, 'quantity': 1, 'reason': 'SIZE_MISMATCH'}],
        customer_notes="سایز برای من بزرگ بود",
        user=admin_user_a
    )

    assert rma.status == ReturnStatus.REQUESTED
    assert rma.refund_amount == Decimal('250000')

    approve_return_request(rma, user=admin_user_a)
    rma.refresh_from_db()
    assert rma.status == ReturnStatus.APPROVED

    # Inspect and restock sellable item
    balance_before = InventoryBalance.objects.get(warehouse=warehouse_a, variant=variant_a1).on_hand_quantity
    rma_item = rma.items.first()
    inspection_data = [{
        'item_id': str(rma_item.id),
        'condition': 'OPENED_GOOD',
        'action': ReturnAction.RESTOCK,
        'notes': 'کالا بدون استفاده و کاملا تمیز است'
    }]

    inspect_and_process_return(
        rma=rma,
        inspection_items_data=inspection_data,
        warehouse=warehouse_a,
        user=admin_user_a,
        refund_status=RefundStatus.REFUNDED
    )

    rma.refresh_from_db()
    assert rma.status == ReturnStatus.COMPLETED
    assert rma.refund_status == RefundStatus.REFUNDED

    # Check stock incremented
    balance_after = InventoryBalance.objects.get(warehouse=warehouse_a, variant=variant_a1).on_hand_quantity
    assert balance_after == balance_before + 1

    last_movement = InventoryMovement.objects.filter(variant=variant_a1).order_by('-created_at').first()
    assert last_movement.movement_type == MovementType.RETURN
    assert last_movement.quantity == 1
