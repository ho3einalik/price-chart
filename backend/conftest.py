import pytest
from decimal import Decimal
from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role
from apps.catalog.models import Product, ProductVariant
from apps.inventory.models import Warehouse, InventoryBalance
from apps.orders.models import Customer

@pytest.fixture
def admin_user_a(db):
    return User.objects.create_user(email="owner_a@test.com", password="password123", full_name="مدیر فروشگاه الف")

@pytest.fixture
def store_a(db, admin_user_a):
    biz = Business.objects.create(name="کسب و کار تست", owner=admin_user_a)
    store = Store.objects.create(business=biz, name="فروشگاه الف", currency="IRT")
    StoreMembership.objects.create(store=store, user=admin_user_a, role=Role.OWNER)
    return store

@pytest.fixture
def warehouse_a(db, store_a):
    return Warehouse.objects.create(store=store_a, name="انبار مرکزی", is_default=True)

@pytest.fixture
def variant_a1(db, store_a, warehouse_a):
    product = Product.objects.create(store=store_a, name="پیراهن نخی اعلا")
    variant = ProductVariant.objects.create(
        store=store_a,
        product=product,
        name="سایز L / آبی",
        sku="SHIRT-BLU-L",
        cost_price=Decimal('120000'),
        retail_price=Decimal('250000')
    )
    InventoryBalance.objects.create(
        store=store_a,
        warehouse=warehouse_a,
        variant=variant,
        on_hand_quantity=50
    )
    return variant

@pytest.fixture
def customer_a(db, store_a):
    return Customer.objects.create(
        store=store_a,
        full_name="علی رضایی",
        phone_number="09129876543",
        city="تهران",
        address_line="تهران، خیابان آزادی، پلاک ۱۲"
    )
