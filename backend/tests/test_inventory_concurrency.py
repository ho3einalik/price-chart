import pytest
from decimal import Decimal
from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership
from apps.catalog.models import Product, ProductVariant
from apps.inventory.models import Warehouse, InventoryMovement, MovementType
from apps.inventory.services import (
    adjust_stock, reserve_stock, release_stock_reservation,
    commit_stock_sale, InsufficientStockError
)

@pytest.mark.django_db
def test_inventory_ledger_and_reservation_flow():
    user = User.objects.create_user(email="inventory_test@example.com", password="password123", full_name="Tester")
    biz = Business.objects.create(name="Biz", owner=user)
    store = Store.objects.create(business=biz, name="Store")
    warehouse = Warehouse.objects.create(store=store, name="Main WH")
    product = Product.objects.create(store=store, name="Test Item")
    variant = ProductVariant.objects.create(
        store=store, product=product, name="Var 1", sku="SKU-INV-1",
        cost_price=Decimal('100'), retail_price=Decimal('200')
    )

    # 1. Adjust initial stock to 10
    balance = adjust_stock(store=store, warehouse=warehouse, variant=variant, new_on_hand=10, user=user)
    assert balance.on_hand_quantity == 10
    assert balance.available == 10
    assert InventoryMovement.objects.filter(variant=variant, movement_type=MovementType.ADJUSTMENT).count() == 1

    # 2. Reserve 4 units
    reserve_stock(store=store, warehouse=warehouse, variant=variant, quantity=4, reference="ORD-01", user=user)
    balance.refresh_from_db()
    assert balance.on_hand_quantity == 10
    assert balance.reserved_quantity == 4
    assert balance.available == 6
    assert InventoryMovement.objects.filter(variant=variant, movement_type=MovementType.RESERVATION).count() == 1

    # 3. Attempting to reserve 7 units (which exceeds available 6) must raise InsufficientStockError!
    with pytest.raises(InsufficientStockError):
        reserve_stock(store=store, warehouse=warehouse, variant=variant, quantity=7, reference="ORD-02", user=user)

    # 4. Commit 2 units sale (e.g. order fulfilled)
    commit_stock_sale(store=store, warehouse=warehouse, variant=variant, quantity=2, reference="ORD-01", user=user)
    balance.refresh_from_db()
    assert balance.on_hand_quantity == 8
    assert balance.reserved_quantity == 2
    assert balance.available == 6
    assert InventoryMovement.objects.filter(variant=variant, movement_type=MovementType.SALE).count() == 1

    # 5. Release remaining 2 reserved units (e.g. order cancelled)
    release_stock_reservation(store=store, warehouse=warehouse, variant=variant, quantity=2, reference="ORD-01", user=user)
    balance.refresh_from_db()
    assert balance.reserved_quantity == 0
    assert balance.available == 8
    assert InventoryMovement.objects.filter(variant=variant, movement_type=MovementType.RESERVATION_RELEASE).count() == 1
