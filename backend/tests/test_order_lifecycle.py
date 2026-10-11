import pytest
from decimal import Decimal
from apps.accounts.models import User
from apps.tenancy.models import Business, Store
from apps.catalog.models import Product, ProductVariant
from apps.inventory.models import Warehouse, InventoryBalance
from apps.inventory.services import adjust_stock
from apps.orders.models import Order, OrderStatus, FulfillmentStatus
from apps.orders.services import create_order, cancel_order, fulfill_order

@pytest.mark.django_db
def test_order_creation_reservation_and_cancellation():
    user = User.objects.create_user(email="order_test@example.com", password="password123", full_name="Tester")
    biz = Business.objects.create(name="Order Biz", owner=user)
    store = Store.objects.create(business=biz, name="Order Store")
    warehouse = Warehouse.objects.create(store=store, name="Warehouse 1")
    product = Product.objects.create(store=store, name="Test Product")
    variant = ProductVariant.objects.create(
        store=store, product=product, name="Var 1", sku="SKU-ORD-1",
        cost_price=Decimal('50000'), retail_price=Decimal('120000')
    )

    # Initial stock: 10
    adjust_stock(store=store, warehouse=warehouse, variant=variant, new_on_hand=10, user=user)

    # Create Order for 3 units
    order = create_order(
        store=store,
        customer_data={'full_name': "Customer 1", 'phone_number': "09120000001"},
        items_data=[{'variant_id': str(variant.id), 'quantity': 3, 'unit_price': variant.retail_price}],
        warehouse=warehouse,
        shipping_cost=Decimal('20000'),
        user=user
    )

    assert order.order_status == OrderStatus.CONFIRMED
    assert order.items.count() == 1
    item = order.items.first()
    assert item.cost_price_snapshot == Decimal('50000')
    assert item.quantity == 3

    # Balance check: 3 reserved, 7 available
    balance = InventoryBalance.objects.get(warehouse=warehouse, variant=variant)
    assert balance.on_hand_quantity == 10
    assert balance.reserved_quantity == 3
    assert balance.available == 7

    # Cancel order: reservation must be released!
    cancel_order(order=order, reason="Customer cancelled", user=user)
    order.refresh_from_db()
    assert order.order_status == OrderStatus.CANCELLED

    balance.refresh_from_db()
    assert balance.reserved_quantity == 0
    assert balance.available == 10

@pytest.mark.django_db
def test_order_fulfillment_commits_sale():
    user = User.objects.create_user(email="fulfill_test@example.com", password="password123", full_name="Tester")
    biz = Business.objects.create(name="Fulfill Biz", owner=user)
    store = Store.objects.create(business=biz, name="Fulfill Store")
    warehouse = Warehouse.objects.create(store=store, name="Warehouse 1")
    product = Product.objects.create(store=store, name="Product 2")
    variant = ProductVariant.objects.create(
        store=store, product=product, name="Var 2", sku="SKU-ORD-2",
        cost_price=Decimal('30000'), retail_price=Decimal('80000')
    )

    adjust_stock(store=store, warehouse=warehouse, variant=variant, new_on_hand=5, user=user)

    order = create_order(
        store=store,
        customer_data={'full_name': "Customer 2", 'phone_number': "09120000002"},
        items_data=[{'variant_id': str(variant.id), 'quantity': 2, 'unit_price': variant.retail_price}],
        warehouse=warehouse,
        user=user
    )

    fulfilled_order, shipment = fulfill_order(order=order, tracking_number="TRK-12345", user=user)
    assert fulfilled_order.order_status == OrderStatus.FULFILLED
    assert fulfilled_order.fulfillment_status == FulfillmentStatus.FULFILLED
    assert shipment.tracking_number == "TRK-12345"

    balance = InventoryBalance.objects.get(warehouse=warehouse, variant=variant)
    assert balance.on_hand_quantity == 3  # Deducted from 5 to 3
    assert balance.reserved_quantity == 0
    assert balance.available == 3
