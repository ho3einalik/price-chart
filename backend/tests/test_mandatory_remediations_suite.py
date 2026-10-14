import pytest
from decimal import Decimal
from unittest import mock
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework.test import APIRequestFactory, force_authenticate
from rest_framework.exceptions import ValidationError as DRFValidationError, PermissionDenied

from apps.tenancy.models import Store, Business, StoreMembership, Role, MembershipStatus
from apps.accounts.models import User
from apps.catalog.models import Product, ProductVariant, Category
from apps.inventory.models import Warehouse, InventoryBalance
from apps.orders.models import Customer, Order, OrderItem, OrderStatus, PaymentStatus, OrderChannel
from apps.wholesale_pos.models import B2BClientProfile, B2BTier, ProformaInvoice, ProformaStatus, VolumeTierDiscount
from apps.wholesale_pos.services import create_quick_sku_order, convert_proforma_to_order
from apps.social.models import SocialContent, SocialAccount, SocialPlatform, PublishingMode, ContentStatus
from apps.social.services import SocialService
from apps.marketing.models import AbandonedCart, AbandonedCartStatus, RecoveryDeliveryStatus
from apps.marketing.tasks import check_abandoned_carts_and_notify
from apps.marketing.views import AbandonedCartViewSet
from apps.features.services import FeatureService
from apps.features.models import StoreFeatureSetting, SubscriptionTier
from apps.catalog.views import ProductViewSet
from apps.payments.views import PaymentTransactionViewSet
from apps.returns.models import ReturnRequest, ReturnItem, ReturnStatus, RefundStatus as ReturnRefundStatus
from apps.returns.services import inspect_and_process_return
from apps.finance.models import AccountsPayableReceivable, DebtEntityType, RefundRecord


@pytest.fixture
def store(db):
    owner = User.objects.create_user(phone_number="09129990000", email="owner@shop.com", full_name="مالک کسب‌وکار")
    biz = Business.objects.create(name="تست بیزنس رمدیشن", owner=owner)
    s = Store.objects.create(business=biz, name="فروشگاه آزمایشی رمدیشن")
    return s


@pytest.fixture
def default_warehouse(db, store):
    return Warehouse.objects.create(store=store, name="انبار مرکزی", is_default=True)


@pytest.fixture
def secondary_warehouse(db, store):
    return Warehouse.objects.create(store=store, name="انبار مشهد", code="WH-MHD", is_default=False)


@pytest.fixture
def staff_user(db, store):
    u = User.objects.create_user(phone_number="09121112233", email="staff@shop.com", full_name="کارمند آزمایشی")
    StoreMembership.objects.create(store=store, user=u, role=Role.ADMIN, status=MembershipStatus.ACTIVE, is_active=True)
    return u


@pytest.fixture
def manager_user(db, store):
    u = User.objects.create_user(phone_number="09123334455", email="manager@shop.com", full_name="مدیر فروشگاه")
    StoreMembership.objects.create(store=store, user=u, role=Role.ADMIN, status=MembershipStatus.ACTIVE, is_active=True)
    return u


@pytest.fixture
def product_and_variant(db, store):
    p = Product.objects.create(store=store, name="کفش ورزشی نایک", status="ACTIVE")
    v = ProductVariant.objects.create(
        store=store,
        product=p,
        sku="NIKE-RUN-42",
        name="سایز 42",
        retail_price=Decimal("1500000"),
        wholesale_price=Decimal("1200000"),
        cost_price=Decimal("1000000")
    )
    return p, v


# -------------------------------------------------------------
# 1. Wholesale Quick SKU & Credit Limits
# -------------------------------------------------------------
@pytest.mark.django_db
def test_wholesale_quick_sku_unapproved_client_rejected(store, product_and_variant):
    _, variant = product_and_variant
    cust = Customer.objects.create(store=store, full_name="همکار تأیید نشده", phone_number="09120001122")
    client = B2BClientProfile.objects.create(
        store=store,
        customer=cust,
        company_name="شرکت همکاران آزمایشی",
        is_approved=False,
        credit_limit=Decimal("50000000"),
        current_debt=Decimal("0")
    )

    with pytest.raises(ValidationError) as exc:
        create_quick_sku_order(
            store=store,
            client=client,
            sku_items=[{'sku': variant.sku, 'quantity': 5}]
        )
    assert "تأیید نشده" in str(exc.value)


@pytest.mark.django_db
def test_wholesale_quick_sku_credit_limit_exceeded(store, product_and_variant):
    _, variant = product_and_variant
    cust = Customer.objects.create(store=store, full_name="همکار اعتباری", phone_number="09120003344")
    client = B2BClientProfile.objects.create(
        store=store,
        customer=cust,
        company_name="پخش سراسری البرز",
        is_approved=True,
        credit_limit=Decimal("5000000"),
        current_debt=Decimal("4000000") # remaining: 1,000,000
    )

    # 5 items * 1,200,000 = 6,000,000 -> exceeds 1,000,000 remaining credit
    with pytest.raises(ValidationError) as exc:
        create_quick_sku_order(
            store=store,
            client=client,
            sku_items=[{'sku': variant.sku, 'quantity': 5}]
        )
    assert "سقف اعتبار" in str(exc.value)


# -------------------------------------------------------------
# 2. Social Publishing: Manual Proof Flow & Direct API Protection
# -------------------------------------------------------------
@pytest.mark.django_db
def test_social_manual_mode_direct_publish_blocked(store, staff_user, manager_user):
    account = SocialAccount.objects.create(store=store, platform=SocialPlatform.INSTAGRAM, handle="myshop_insta")
    content = SocialContent.objects.create(
        store=store,
        account=account,
        title="معرفی محصول جدید در استوری",
        publishing_mode=PublishingMode.MANUAL_REMINDER,
        creator=staff_user,
        status=ContentStatus.APPROVED
    )

    # Direct publish must be BLOCKED for MANUAL_REMINDER
    with pytest.raises(DRFValidationError) as exc:
        SocialService.publish_content(
            content=content,
            published_url="https://instagram.com/p/test1234",
            user=staff_user
        )
    assert "مدرک" in str(exc.value) or "دستی" in str(exc.value)

    # Strict two-step flow: submit proof -> verify proof
    SocialService.submit_proof(
        content=content,
        proof_url="https://instagram.com/stories/test",
        user=staff_user
    )
    content.refresh_from_db()
    assert content.status == ContentStatus.PENDING_PROOF_VERIFICATION

    # Verify proof by manager
    SocialService.verify_proof(
        content=content,
        manager_user=manager_user,
        approved=True,
        notes="مدرک بررسی و تأیید شد."
    )
    content.refresh_from_db()
    assert content.status == ContentStatus.PUBLISHED
    assert content.approved_by == manager_user


# -------------------------------------------------------------
# 3. Abandoned Cart SMS Retry Policy (NOT_CONFIGURED & SIMULATED)
# -------------------------------------------------------------
@pytest.mark.django_db
def test_abandoned_cart_not_configured_increments_attempts_and_retries(store):
    two_hours_ago = timezone.now() - timezone.timedelta(hours=3)
    cart = AbandonedCart.objects.create(
        store=store,
        phone_or_email="09129998877",
        total_amount=Decimal("500000"),
        delivery_status=RecoveryDeliveryStatus.NOT_SENT,
        recovery_attempts=0,
        created_at=two_hours_ago
    )
    # Ensure created_at is in the past
    AbandonedCart.objects.filter(id=cart.id).update(created_at=two_hours_ago)

    with mock.patch('apps.features.adapters.SMSGateway.send_sms', return_value={'status': 'NOT_CONFIGURED', 'message': 'درگاه تنظیم نشده'}):
        check_abandoned_carts_and_notify()

    cart.refresh_from_db()
    assert cart.delivery_status == RecoveryDeliveryStatus.NOT_CONFIGURED
    assert cart.recovery_attempts == 1
    assert cart.recovery_sms_sent_at is None


@pytest.mark.django_db
def test_abandoned_cart_simulated_sets_timestamp_preventing_duplicate_spam(store):
    two_hours_ago = timezone.now() - timezone.timedelta(hours=3)
    cart = AbandonedCart.objects.create(
        store=store,
        phone_or_email="09129998877",
        total_amount=Decimal("500000"),
        delivery_status=RecoveryDeliveryStatus.NOT_SENT,
        recovery_attempts=0
    )
    AbandonedCart.objects.filter(id=cart.id).update(created_at=two_hours_ago)

    with mock.patch('apps.features.adapters.SMSGateway.send_sms', return_value={'status': 'SIMULATED'}):
        check_abandoned_carts_and_notify()

    cart.refresh_from_db()
    assert cart.delivery_status == RecoveryDeliveryStatus.SIMULATED
    assert cart.recovery_sms_sent_at is not None
    assert cart.recovery_attempts == 1

    # Second run should NOT re-process because recovery_sms_sent_at is not None
    with mock.patch('apps.features.adapters.SMSGateway.send_sms') as mock_send:
        check_abandoned_carts_and_notify()
        mock_send.assert_not_called()


# -------------------------------------------------------------
# 4. Quota Logic & Boundary Testing (limit - 1, limit, limit + 1)
# -------------------------------------------------------------
@pytest.mark.django_db
def test_quota_boundary_limits(store):
    settings = StoreFeatureSetting.objects.create(store=store, tier=SubscriptionTier.FREE)
    # FREE max_products = 50

    # Clean existing products
    Product.objects.filter(store=store).delete()

    # Limit - 1 (current=48, increment=1 -> 49 <= 50): Allowed
    with mock.patch('apps.catalog.models.Product.objects.filter') as mock_filter:
        mock_filter.return_value.count.return_value = 48
        allowed, current, limit, _ = FeatureService.check_plan_quota(store, 'products', increment=1)
        assert allowed is True
        assert limit == 50

    # Limit (current=49, increment=1 -> 50 <= 50): Allowed
    with mock.patch('apps.catalog.models.Product.objects.filter') as mock_filter:
        mock_filter.return_value.count.return_value = 49
        allowed, current, limit, _ = FeatureService.check_plan_quota(store, 'products', increment=1)
        assert allowed is True

    # Limit + 1 (current=50, increment=1 -> 51 <= 50): Denied
    with mock.patch('apps.catalog.models.Product.objects.filter') as mock_filter:
        mock_filter.return_value.count.return_value = 50
        allowed, current, limit, msg = FeatureService.check_plan_quota(store, 'products', increment=1)
        assert allowed is False
        assert "سقف تعداد محصولات" in msg


# -------------------------------------------------------------
# 5. Multi-Warehouse CSV Export & Import
# -------------------------------------------------------------
@pytest.mark.django_db
def test_multi_warehouse_csv_import_does_not_contaminate_default(store, default_warehouse, secondary_warehouse, product_and_variant, staff_user):
    _, variant = product_and_variant
    # Initial balance: Default=10, Secondary=20
    b1 = InventoryBalance.objects.create(store=store, warehouse=default_warehouse, variant=variant, on_hand_quantity=10)
    b2 = InventoryBalance.objects.create(store=store, warehouse=secondary_warehouse, variant=variant, on_hand_quantity=20)

    # CSV targeting secondary warehouse specifically
    csv_data = (
        "کد تنوع (SKU),نام انبار,موجودی در این انبار,قیمت فروش (تومان)\n"
        f"{variant.sku},{secondary_warehouse.name},35,1600000\n"
    )

    factory = APIRequestFactory()
    request = factory.post('/api/v1/catalog/products/import-csv/', {'csv_content': csv_data})
    force_authenticate(request, user=staff_user)
    request.store = store
    request.membership = StoreMembership.objects.get(store=store, user=staff_user)

    view = ProductViewSet.as_view({'post': 'import_csv'})
    response = view(request)

    assert response.status_code == 200
    b1.refresh_from_db()
    b2.refresh_from_db()

    # Secondary warehouse was updated to 35, default warehouse remained untouched at 10!
    assert b2.on_hand_quantity == 35
    assert b1.on_hand_quantity == 10


# -------------------------------------------------------------
# 6. Bulk Update Atomicity & Transparency
# -------------------------------------------------------------
@pytest.mark.django_db
def test_bulk_update_atomic_rollback_on_any_invalid_row(store, product_and_variant, staff_user):
    _, variant = product_and_variant
    orig_price = variant.retail_price

    payload = {
        'items': [
            {'variant_id': str(variant.id), 'retail_price': 1800000}, # valid row
            {'variant_id': '00000000-0000-0000-0000-000000000000', 'retail_price': 2000000} # invalid row
        ]
    }

    factory = APIRequestFactory()
    request = factory.post('/api/v1/catalog/products/bulk-update/', payload, format='json')
    force_authenticate(request, user=staff_user)
    request.store = store
    request.membership = StoreMembership.objects.get(store=store, user=staff_user)

    view = ProductViewSet.as_view({'post': 'bulk_update'})
    response = view(request)

    # Must return 400 with rollback
    assert response.status_code == 400
    variant.refresh_from_db()
    # Price must NOT have changed for the first item
    assert variant.retail_price == orig_price


# -------------------------------------------------------------
# 7. Payment Callback URL Validation & Spoofing Defense
# -------------------------------------------------------------
@pytest.mark.django_db
def test_payment_callback_url_spoofing_defense(store):
    factory = APIRequestFactory()
    request = factory.post('/api/v1/payments/pay/', HTTP_HOST='myshop.ir')
    request.store = store

    view = PaymentTransactionViewSet()

    # Userinfo injection: must be rejected to fallback
    url_userinfo = "https://admin:secret@myshop.ir/api/v1/payments/online-verify/"
    safe = view._resolve_safe_callback_url(request, url_userinfo)
    assert "admin:secret" not in safe
    assert safe.endswith('/api/v1/payments/online-verify/')

    # Attacker subdomain / spoofing: must be rejected to fallback
    url_spoofed = "https://myshop.ir.attacker.com/callback"
    safe_spoofed = view._resolve_safe_callback_url(request, url_spoofed)
    assert "attacker.com" not in safe_spoofed

    # Port manipulation: must be rejected to fallback
    url_bad_port = "https://myshop.ir:9999/callback"
    safe_port = view._resolve_safe_callback_url(request, url_bad_port)
    assert "9999" not in safe_port


# -------------------------------------------------------------
# 8. Return Item Exchange Financial Settlement
# -------------------------------------------------------------
@pytest.mark.django_db
def test_return_exchange_price_difference_financial_tracking(store, default_warehouse, product_and_variant, staff_user):
    _, variant1 = product_and_variant
    p2 = Product.objects.create(store=store, name="کفش ورزشی آدیداس", status="ACTIVE")
    variant2 = ProductVariant.objects.create(
        store=store,
        product=p2,
        sku="ADIDAS-ULTRABOOST",
        name="سایز 42",
        retail_price=Decimal("2000000"),
        cost_price=Decimal("1400000")
    )
    InventoryBalance.objects.create(store=store, warehouse=default_warehouse, variant=variant1, on_hand_quantity=10)
    InventoryBalance.objects.create(store=store, warehouse=default_warehouse, variant=variant2, on_hand_quantity=10)

    customer = Customer.objects.create(store=store, full_name="مشتری مرجوعی", phone_number="09121234567")
    order = Order.objects.create(
        store=store,
        customer=customer,
        warehouse=default_warehouse,
        order_number="ORD-RET-EXCH-01",
        grand_total=Decimal("1500000"),
        total_items_price=Decimal("1500000"),
        order_status=OrderStatus.COMPLETED,
        payment_status=PaymentStatus.PAID
    )

    order_item = OrderItem.objects.create(
        order=order,
        variant=variant1,
        variant_sku=variant1.sku,
        variant_name=variant1.name,
        quantity=1,
        unit_price=Decimal("1500000"),
        cost_price_snapshot=Decimal("1000000"),
        total_price=Decimal("1500000")
    )

    # Customer exchanges variant1 (1,500,000) for variant2 (2,000,000) -> customer owes difference +500,000
    price_diff = Decimal("500000")
    rma = ReturnRequest.objects.create(
        store=store,
        order=order,
        customer=customer,
        rma_number="RMA-EXCH-001",
        status=ReturnStatus.APPROVED,
        is_exchange=True,
        exchange_variant=variant2,
        exchange_quantity=1,
        exchange_price_difference=price_diff
    )
    ReturnItem.objects.create(
        return_request=rma,
        order_item=order_item,
        variant=variant1,
        quantity=1,
        action="RESTOCK"
    )

    inspect_and_process_return(
        rma=rma,
        inspection_items_data=[{'item_id': str(rma.items.first().id), 'action': 'RESTOCK', 'restock_warehouse_id': str(default_warehouse.id)}],
        warehouse=default_warehouse,
        user=staff_user,
        refund_status=ReturnRefundStatus.NO_REFUND
    )

    # Must create AccountsPayableReceivable for customer debt (+500,000)
    receivable = AccountsPayableReceivable.objects.filter(
        store=store,
        customer=customer,
        total_amount=price_diff
    ).first()
    assert receivable is not None
    assert receivable.entity_type == DebtEntityType.CUSTOMER_CREDIT
    assert receivable.remaining_balance == price_diff
