import pytest
from decimal import Decimal
from django.utils import timezone
from apps.accounts.models import User
from apps.tenancy.models import Business, Store
from apps.catalog.models import Product, ProductVariant
from apps.inventory.models import Warehouse, InventoryBalance
from apps.inventory.services import adjust_stock
from apps.orders.models import Order, Customer, OrderStatus, PaymentStatus, OrderChannel
from apps.orders.services import create_order
from apps.fulfillment.models import Shipment, Carrier, ShipmentStatus, ShipmentTrackingEvent
from apps.fulfillment.services import create_shipment, update_shipment_status, IranPostAdapter
from apps.social.models import SocialContent, ContentStatus
from apps.social.services import SocialService
from apps.social_inbox.models import ConversationThread, ThreadChannel
from apps.marketing.models import Coupon, DiscountType, ProductRecommendation, RecommendationType
from apps.marketing.services import evaluate_product_recommendations
from apps.finance.models import GatewaySettlement, AccountsPayableReceivable, DebtEntityType, DebtStatus, RefundRecord
from apps.intelligence.services import calculate_demand_forecasts, calculate_slow_movers
from apps.wholesale_pos.models import B2BClientProfile, VolumeTierDiscount, POSTerminal, POSRegisterSession, POSSessionStatus, ProformaInvoice, ProformaStatus, B2BTier
from apps.wholesale_pos.services import pos_quick_checkout, convert_proforma_to_order, calculate_b2b_price
from apps.audit.models import Notification, NotificationCategory, NotificationLevel, AuditLog

@pytest.fixture
def setup_store():
    user = User.objects.create_user(email="product_tester@example.com", password="password123", full_name="Super Tester")
    biz = Business.objects.create(name="Capabilities Biz", owner=user)
    store = Store.objects.create(business=biz, name="Capabilities Store", currency='IRT')
    warehouse = Warehouse.objects.create(store=store, name="Main Central Warehouse")
    product = Product.objects.create(store=store, name="Awesome Jacket")
    variant = ProductVariant.objects.create(
        store=store, product=product, name="Size L Black", sku="JCK-BLK-L",
        cost_price=Decimal('200000'), retail_price=Decimal('450000')
    )
    # Give initial stock of 50 units
    adjust_stock(store=store, warehouse=warehouse, variant=variant, new_on_hand=50, user=user)

    customer = Customer.objects.create(store=store, full_name="Ali Reza", phone_number="09121112233")
    order = create_order(
        store=store,
        customer_data={'full_name': customer.full_name, 'phone_number': customer.phone_number},
        items_data=[{'variant_id': str(variant.id), 'quantity': 2, 'unit_price': variant.retail_price}],
        warehouse=warehouse,
        shipping_cost=Decimal('35000'),
        user=user
    )
    return {
        'user': user,
        'store': store,
        'warehouse': warehouse,
        'product': product,
        'variant': variant,
        'customer': customer,
        'order': order
    }


@pytest.mark.django_db
def test_fulfillment_carrier_tracking_and_idempotency(setup_store):
    d = setup_store
    order = d['order']
    store = d['store']
    user = d['user']

    # 1. Create shipment with idempotency key
    idem_key = "IDEM-TEST-1001"
    shipment = create_shipment(
        store=store,
        order=order,
        tracking_number="POST-12345678",
        carrier=Carrier.IRPOST,
        shipping_cost=Decimal('40000'),
        idempotency_key=idem_key
    )
    assert shipment.carrier == Carrier.IRPOST
    assert shipment.status == ShipmentStatus.SHIPPED
    assert shipment.tracking_number == "POST-12345678"
    assert shipment.idempotency_key == idem_key

    # 2. Idempotent call with same key returns existing shipment without duplicating
    shipment_dup = create_shipment(
        store=store,
        order=order,
        tracking_number="POST-12345678",
        carrier=Carrier.IRPOST,
        idempotency_key=idem_key
    )
    assert shipment_dup.id == shipment.id
    assert Shipment.objects.filter(order=order).count() == 1

    # 3. Update status & verify tracking events
    update_shipment_status(shipment, ShipmentStatus.IN_TRANSIT, location="تهران - مرکز مبادلات پستی")
    shipment.refresh_from_db()
    assert shipment.status == ShipmentStatus.IN_TRANSIT

    events = shipment.tracking_events.all()
    assert events.count() >= 2
    latest = events.first()
    assert latest.status == ShipmentStatus.IN_TRANSIT
    assert "تهران" in latest.location


@pytest.mark.django_db
def test_social_order_linking_and_content_proof(setup_store):
    d = setup_store
    store = d['store']
    order = d['order']
    user = d['user']

    # 1. Social thread linking to order & internal notes
    thread = ConversationThread.objects.create(
        store=store,
        channel=ThreadChannel.INSTAGRAM_DM,
        external_thread_id="insta_user_999",
        contact_name="zahra_style",
        order=order,
        internal_notes="مشتری درخواست ارسال فوری با تیپاکس داشت.",
        auto_reply_enabled=False
    )
    assert thread.order == order
    assert thread.auto_reply_enabled is False

    # 2. Social content proof of publishing & manager verification
    content = SocialContent.objects.create(
        store=store,
        title="معرفی کالکشن پاییزه",
        caption="کاپشن‌های جدید با تخفیف ویژه",
        status=ContentStatus.PUBLISHED,
        creator=user
    )
    # Staff submits proof
    SocialService.submit_proof(content, proof_url="https://instagram.com/p/DB123456", proof_image_url="https://cdn.shoppilot.io/proof1.jpg")
    content.refresh_from_db()
    assert content.proof_url == "https://instagram.com/p/DB123456"

    # Manager approves proof
    SocialService.verify_proof(content, manager_user=user)
    content.refresh_from_db()
    assert content.approved_by == user


@pytest.mark.django_db
def test_marketing_coupons_and_cross_sell(setup_store):
    d = setup_store
    store = d['store']
    variant = d['variant']

    # 1. Coupon stackable protection
    coupon1 = Coupon.objects.create(
        store=store,
        code="YALDA50",
        discount_type=DiscountType.PERCENTAGE,
        discount_value=Decimal('50'),
        is_stackable=False,
        is_active=True
    )
    assert coupon1.is_stackable is False

    # 2. Product cross-sell recommendations
    other_prod = Product.objects.create(store=store, name="Warm Scarf")
    other_var = ProductVariant.objects.create(
        store=store, product=other_prod, name="Red Scarf", sku="SCF-RED-1",
        retail_price=Decimal('150000')
    )
    rec = ProductRecommendation.objects.create(
        store=store,
        source_variant=variant,
        recommended_variant=other_var,
        recommendation_type=RecommendationType.CROSS_SELL,
        discount_incentive_percent=10
    )
    results = evaluate_product_recommendations(store, variant.id)
    assert len(results) == 1
    assert results[0]['recommended_sku'] == "SCF-RED-1"
    assert results[0]['discount_incentive_percent'] == 10


@pytest.mark.django_db
def test_finance_settlement_reconciliation_and_receivables(setup_store):
    d = setup_store
    store = d['store']
    customer = d['customer']
    order = d['order']
    user = d['user']

    # 1. Gateway settlement reconciliation
    settlement = GatewaySettlement.objects.create(
        store=store,
        gateway_name="ZARINPAL",
        gross_amount=Decimal('10000000'),
        gateway_fee=Decimal('20000'),
        net_deposited_amount=Decimal('9980000'),
        sheba_number="IR120170000000111122223333",
        is_reconciled=True
    )
    assert settlement.net_deposited_amount == Decimal('9980000')
    assert settlement.is_reconciled is True

    # 2. Accounts Receivable ledger
    receivable = AccountsPayableReceivable.objects.create(
        store=store,
        entity_type=DebtEntityType.CUSTOMER_CREDIT,
        customer=customer,
        title=f"مطالبه نسیه سفارش {order.order_number}",
        total_amount=Decimal('500000'),
        paid_amount=Decimal('200000'),
        status=DebtStatus.PARTIALLY_PAID
    )
    assert receivable.remaining_balance == Decimal('300000')

    # 3. Refund record
    refund = RefundRecord.objects.create(
        store=store,
        order=order,
        amount=Decimal('100000'),
        destination_card_or_sheba="6037991912345678",
        tracking_code="PAYA-987654",
        processed_by=user
    )
    assert refund.amount == Decimal('100000')
    assert refund.processed_by == user


@pytest.mark.django_db
def test_intelligence_demand_forecast_and_dead_stock(setup_store):
    d = setup_store
    store = d['store']
    variant = d['variant']
    warehouse = d['warehouse']

    # 1. Calculate demand forecasts with safety stock & reorder point
    forecasts = calculate_demand_forecasts(store=store, period_days=30)
    assert len(forecasts) >= 1
    f = next(item for item in forecasts if item['variant_id'] == str(variant.id))
    assert 'lead_time_days' in f
    assert 'safety_stock' in f
    assert 'reorder_point' in f
    assert f['lead_time_days'] == 7

    # 2. Dead stock / Slow movers detection: Create variant with stock but 0 sales
    dead_prod = Product.objects.create(store=store, name="Old Summer Hat")
    dead_var = ProductVariant.objects.create(
        store=store, product=dead_prod, name="Straw Hat", sku="HAT-STR-01",
        cost_price=Decimal('80000'), retail_price=Decimal('180000')
    )
    adjust_stock(store=store, warehouse=warehouse, variant=dead_var, new_on_hand=20)

    slow_movers_report = calculate_slow_movers(store=store, period_days=60)
    assert slow_movers_report['slow_mover_count'] >= 1
    dead_item = next(i for i in slow_movers_report['items'] if i['sku'] == "HAT-STR-01")
    assert dead_item['total_on_hand'] == 20
    assert dead_item['units_sold_in_period'] == 0
    assert Decimal(dead_item['tied_up_capital']) == Decimal('80000') * 20


@pytest.mark.django_db
def test_wholesale_b2b_pricing_and_pos_checkout(setup_store):
    d = setup_store
    store = d['store']
    warehouse = d['warehouse']
    variant = d['variant']
    user = d['user']

    # 1. MOQ volume tier discount
    tier = VolumeTierDiscount.objects.create(
        store=store,
        variant=variant,
        min_quantity=10,
        unit_price=Decimal('380000'),
        tier_label="خرید عمده بالای ۱۰ عدد"
    )
    b2b_cust = Customer.objects.create(store=store, full_name="شرکت بازرگانی آوا", phone_number="09129998877")
    b2b_client = B2BClientProfile.objects.create(
        store=store,
        customer=b2b_cust,
        company_name="بازرگانی آوا گستر",
        credit_limit=Decimal('50000000'),
        current_debt=Decimal('0'),
        payment_terms_days=45,
        tier=B2BTier.GOLD
    )

    # Unit price with MOQ & VIP tier
    price = calculate_b2b_price(variant=variant, quantity=15, client=b2b_client)
    # Tier price is 380,000; GOLD gets 10% off -> 342,000
    assert price == Decimal('342000')

    # 2. In-Person POS Quick Checkout
    terminal = POSTerminal.objects.create(
        store=store,
        name="صندوق ۱ مرکزی",
        terminal_code="POS-REG-01",
        warehouse=warehouse
    )
    session = POSRegisterSession.objects.create(
        store=store,
        terminal=terminal,
        opened_by=user,
        opening_cash=Decimal('1000000'),
        status=POSSessionStatus.OPEN
    )

    initial_on_hand = InventoryBalance.objects.get(warehouse=warehouse, variant=variant).on_hand_quantity

    pos_order = pos_quick_checkout(
        store=store,
        session_id=str(session.id),
        items_data=[{'variant_id': str(variant.id), 'quantity': 3, 'unit_price': variant.retail_price}],
        customer_phone="09351234567",
        customer_name="مشتری خرید حضوری",
        user=user
    )

    assert pos_order.channel == OrderChannel.POS
    assert pos_order.order_status == OrderStatus.COMPLETED
    assert pos_order.payment_status == PaymentStatus.PAID
    assert pos_order.grand_total == variant.retail_price * 3

    # Verify inventory was committed immediately
    balance_after = InventoryBalance.objects.get(warehouse=warehouse, variant=variant)
    assert balance_after.on_hand_quantity == initial_on_hand - 3

    session.refresh_from_db()
    assert session.total_sales == pos_order.grand_total


@pytest.mark.django_db
def test_notifications_and_audit_events(setup_store):
    d = setup_store
    store = d['store']
    user = d['user']

    # 1. In-app notification
    notif = Notification.objects.create(
        store=store,
        user=user,
        title="هشدار کسری موجودی",
        message="موجودی کاپشن مشکی به کمتر از ۵ عدد رسیده است.",
        category=NotificationCategory.INVENTORY,
        level=NotificationLevel.WARNING
    )
    assert notif.is_read is False

    notif.is_read = True
    notif.save()
    assert notif.is_read is True

    # 2. Audit log existence
    AuditLog.objects.create(
        store=store,
        user=user,
        action="TEST_ACTION_EVENT",
        target_type="TestTarget",
        target_id="12345"
    )
    assert AuditLog.objects.filter(store=store, action="TEST_ACTION_EVENT").exists()
