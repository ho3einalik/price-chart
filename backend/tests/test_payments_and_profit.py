import pytest
from decimal import Decimal
from apps.accounts.models import User
from apps.tenancy.models import Business, Store
from apps.catalog.models import Product, ProductVariant
from apps.inventory.models import Warehouse
from apps.inventory.services import adjust_stock
from apps.orders.models import Order, PaymentStatus
from apps.orders.services import create_order
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentVerificationStatus
from apps.payments.services import verify_payment_transaction
from apps.analytics.services import calculate_store_overview_metrics

@pytest.mark.django_db
def test_payment_verification_and_profit_engine():
    user = User.objects.create_user(email="profit_test@example.com", password="password123", full_name="Tester")
    biz = Business.objects.create(name="Profit Biz", owner=user)
    store = Store.objects.create(business=biz, name="Profit Store")
    warehouse = Warehouse.objects.create(store=store, name="Warehouse 1")
    product = Product.objects.create(store=store, name="Product Profit")
    variant = ProductVariant.objects.create(
        store=store, product=product, name="Var Profit", sku="SKU-PROFIT-1",
        cost_price=Decimal('200000'), retail_price=Decimal('350000')
    )

    adjust_stock(store=store, warehouse=warehouse, variant=variant, new_on_hand=10, user=user)

    # Order: 2 units at 350,000 each = 700,000. Shipping = 30,000. Grand total = 730,000.
    order = create_order(
        store=store,
        customer_data={'full_name': "Payer", 'phone_number': "09129998877"},
        items_data=[{'variant_id': str(variant.id), 'quantity': 2, 'unit_price': Decimal('350000')}],
        warehouse=warehouse,
        shipping_cost=Decimal('30000'),
        user=user
    )

    assert order.payment_status == PaymentStatus.PENDING

    # Create and verify payment
    payment = PaymentTransaction.objects.create(
        store=store,
        order=order,
        method=PaymentMethod.CARD_TO_CARD,
        amount=order.grand_total,
        status=PaymentVerificationStatus.PENDING_VERIFICATION
    )
    verify_payment_transaction(payment=payment, user=user)
    order.refresh_from_db()
    assert order.payment_status == PaymentStatus.PAID

    # Verify Profit calculation:
    # Gross Sales of items = 700,000
    # COGS = 2 * 200,000 = 400,000
    # Gross Profit = 700,000 - 400,000 = 300,000
    metrics = calculate_store_overview_metrics(store=store, days=7)
    assert metrics['gross_sales'] == 700000
    assert metrics['gross_profit'] == 300000
    assert metrics['paid_revenue'] == 730000
    assert metrics['outstanding_amount'] == 0
    assert metrics['order_count'] == 1
