import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework.exceptions import ValidationError, PermissionDenied


from apps.tenancy.models import Store, Business, StoreMembership, Role
from apps.accounts.models import User
from apps.features.models import SubscriptionTier, SubscriptionInvoice, InvoiceStatus, StoreFeatureSetting
from apps.features.services import SubscriptionPaymentService, FeatureService
from apps.payments.models import PaymentTransaction, PaymentVerificationStatus, PaymentMethod
from apps.payments.services import verify_payment_transaction, process_payment_refund
from apps.payments.gateways import validate_and_convert_to_gateway_amount, GatewayPaymentResult
from apps.orders.models import Customer, Order, OrderItem, OrderStatus, PaymentStatus, FulfillmentStatus
from apps.inventory.models import Warehouse, InventoryBalance
from apps.inventory.services import get_or_create_balance, transfer_stock
from apps.catalog.models import Product, ProductVariant
from apps.returns.models import ReturnRequest, ReturnItem, ReturnStatus, RefundStatus
from apps.returns.services import create_return_request
from apps.automation.models import AutomationRule, AutomationExecutionLog, ExecutionStatus, TriggerEvent
from apps.automation.services import trigger_automation
from apps.social.models import SocialContent, ContentStatus, ContentType
from apps.social.services import SocialService


@pytest.fixture
def test_setup(db):
    user = User.objects.create_user(email='owner@shoppilot.ir', phone_number='09121111111', password='Password123!', full_name='Owner User')
    staff_user = User.objects.create_user(email='staff@shoppilot.ir', phone_number='09122222222', password='Password123!', full_name='Staff User', is_staff=True)
    business = Business.objects.create(name='Test Biz', owner=user)
    store = Store.objects.create(business=business, name='Main Store')
    membership = StoreMembership.objects.create(store=store, user=user, role=Role.OWNER, is_active=True)

    other_user = User.objects.create_user(email='other@shoppilot.ir', phone_number='09123333333', password='Password123!', full_name='Other Owner')
    other_biz = Business.objects.create(name='Other Biz', owner=other_user)
    other_store = Store.objects.create(business=other_biz, name='Other Store')



    return {
        'owner': user,
        'staff': staff_user,
        'store': store,
        'membership': membership,
        'other_store': other_store,
        'other_owner': other_user
    }


@pytest.mark.django_db
class TestSaaSProductionIntegrity:

    def test_subscription_invoice_lifecycle_and_security(self, test_setup, client):
        store = test_setup['store']
        owner = test_setup['owner']
        staff = test_setup['staff']

        # 1. Create paid tier invoice
        invoice = SubscriptionPaymentService.create_subscription_invoice(store, SubscriptionTier.PRO)
        assert invoice.status == InvoiceStatus.PENDING
        assert invoice.amount == Decimal('590000')

        # 2. Client-supplied fake tracking string should NOT be allowed for regular store admin
        client.force_login(owner)
        client.defaults['HTTP_X_STORE_ID'] = str(store.id)
        res = client.post(f"/api/v1/features/invoices/{invoice.id}/pay/", {'tracking_code': 'FAKE-CLIENT-123'})
        assert res.status_code == 400
        invoice.refresh_from_db()
        assert invoice.status == InvoiceStatus.PENDING

        # 3. Staff manual override requires reason
        client.force_login(staff)
        res_fail = client.post(f"/api/v1/features/invoices/{invoice.id}/pay/", {'tracking_code': 'MANUAL-123'})
        assert res_fail.status_code == 400  # missing reason

        res_ok = client.post(f"/api/v1/features/invoices/{invoice.id}/pay/", {'reason': 'Approved by platform support manager'})
        assert res_ok.status_code == 200
        invoice.refresh_from_db()
        assert invoice.status == InvoiceStatus.PAID
        settings = FeatureService.get_or_create_settings(store)
        assert settings.tier == SubscriptionTier.PRO

        # 4. Free tier invoice auto-activates cleanly
        free_inv = SubscriptionPaymentService.create_subscription_invoice(store, SubscriptionTier.FREE)
        assert free_inv.status == InvoiceStatus.PAID
        settings.refresh_from_db()
        assert settings.tier == SubscriptionTier.FREE

    def test_payment_currency_conversion_and_refunds(self, test_setup):
        # 1. Toman vs Rial canonical conversion
        assert validate_and_convert_to_gateway_amount(Decimal('50000'), 'IRT') == 50000
        assert validate_and_convert_to_gateway_amount(Decimal('500000'), 'IRR') == 50000

        # Enforces minimum 1,000 Tomans
        with pytest.raises(ValidationError):
            validate_and_convert_to_gateway_amount(Decimal('999'), 'IRT')
        with pytest.raises(ValidationError):
            validate_and_convert_to_gateway_amount(Decimal('9990'), 'IRR')

        # Enforces maximum 50,000,000 Tomans
        with pytest.raises(ValidationError):
            validate_and_convert_to_gateway_amount(Decimal('50000001'), 'IRT')

        # 2. Process refund under pessimistic lock
        store = test_setup['store']
        customer = Customer.objects.create(store=store, full_name='Buyer', phone_number='09120000001')
        wh = Warehouse.objects.create(store=store, name='Main WH')
        order = Order.objects.create(
            store=store,
            order_number='ORD-REFUND-1',
            customer=customer,
            warehouse=wh,
            grand_total=Decimal('100000')
        )
        payment = PaymentTransaction.objects.create(
            store=store,
            order=order,
            method=PaymentMethod.ONLINE_GATEWAY,
            amount=Decimal('100000'),
            status=PaymentVerificationStatus.VERIFIED
        )
        order.payment_status = PaymentStatus.PAID
        order.save()

        # Cannot refund more than payment amount
        with pytest.raises(ValidationError):
            process_payment_refund(payment, amount=Decimal('150000'), user=test_setup['owner'])

        # Valid refund
        refunded = process_payment_refund(payment, amount=Decimal('100000'), reason='Customer requested cancellation', user=test_setup['owner'])
        assert refunded.status == PaymentVerificationStatus.REFUNDED
        order.refresh_from_db()
        assert order.payment_status == PaymentStatus.REFUNDED

    def test_automation_idempotency_concurrency(self, test_setup):
        store = test_setup['store']
        rule = AutomationRule.objects.create(
            store=store,
            name='Order SMS Alert',
            trigger=TriggerEvent.ORDER_CREATED,
            actions=[{'type': 'NOTIFY_TEAM', 'message': 'New order created'}]
        )

        payload = {'idempotency_key': 'EVENT-IDEMP-XYZ-999', 'order_number': 'ORD-123', 'customer_phone': '09121112233'}

        # First trigger executes
        count1 = trigger_automation(store, TriggerEvent.ORDER_CREATED, payload)
        assert count1 == 1

        # Second trigger with same idempotency key is skipped idempotently
        count2 = trigger_automation(store, TriggerEvent.ORDER_CREATED, payload)
        assert count2 == 0

        # Only 1 execution log created
        logs = AutomationExecutionLog.objects.filter(rule=rule, idempotency_key='EVENT-IDEMP-XYZ-999')
        assert logs.count() == 1
        assert logs.first().status == ExecutionStatus.SUCCESS

    def test_returns_concurrency_and_inventory_tenant_isolation(self, test_setup):
        store = test_setup['store']
        other_store = test_setup['other_store']

        # 1. Tenant isolation in inventory
        prod = Product.objects.create(store=store, name='Sneakers')
        var = ProductVariant.objects.create(store=store, product=prod, name='Size 42', sku='SNK-42', retail_price=Decimal('200000'))


        wh = Warehouse.objects.create(store=store, name='Central WH')

        other_wh = Warehouse.objects.create(store=other_store, name='Foreign WH')

        # Attempting to associate warehouse from another store raises ValidationError
        with pytest.raises((ValidationError, DjangoValidationError)):
            get_or_create_balance(store, other_wh, var)

        # Cross-store transfer raises ValidationError
        with pytest.raises((ValidationError, DjangoValidationError)):
            transfer_stock(store, wh, other_wh, var, 1)

        # 2. Returns remaining quantity check under lock
        customer = Customer.objects.create(store=store, full_name='Buyer 2', phone_number='09120000002')
        order = Order.objects.create(
            store=store,
            order_number='ORD-RETURN-TEST',
            customer=customer,
            warehouse=wh,
            order_status=OrderStatus.COMPLETED,
            fulfillment_status=FulfillmentStatus.FULFILLED,
            grand_total=Decimal('400000')
        )
        item = OrderItem.objects.create(
            order=order,
            variant=var,
            variant_sku=var.sku,
            variant_name=var.sku,
            quantity=2,
            unit_price=Decimal('200000'),
            cost_price_snapshot=Decimal('100000'),
            total_price=Decimal('400000')
        )

        rma1 = create_return_request(order, [{'order_item': item, 'quantity': 1, 'reason': 'DEFECT'}])
        assert rma1.status == ReturnStatus.REQUESTED

        # Second RMA for 1 more is allowed (1 + 1 == 2)
        rma2 = create_return_request(order, [{'order_item': item, 'quantity': 1, 'reason': 'WRONG_SIZE'}])
        assert rma2.status == ReturnStatus.REQUESTED

        # Third RMA for 1 more must be rejected (would exceed purchased 2)
        with pytest.raises((ValidationError, DjangoValidationError)):
            create_return_request(order, [{'order_item': item, 'quantity': 1, 'reason': 'NOT_NEEDED'}])


    def test_social_proof_verification_integrity(self, test_setup):
        store = test_setup['store']
        user = test_setup['owner']
        manager = test_setup['staff']

        content = SocialContent.objects.create(
            store=store,
            title='Teaser Reel',
            content_type=ContentType.REEL,
            creator=user,
            status=ContentStatus.APPROVED
        )

        # Submitting proof must set PENDING_PROOF_VERIFICATION (not PUBLISHED)
        SocialService.submit_proof(content, proof_url='https://instagram.com/p/proof123', user=user)
        content.refresh_from_db()
        assert content.status == ContentStatus.PENDING_PROOF_VERIFICATION
        assert content.published_at is None

        # Manager verification moves it to PUBLISHED
        SocialService.verify_proof(content, manager_user=manager, approved=True)
        content.refresh_from_db()
        assert content.status == ContentStatus.PUBLISHED
        assert content.approved_by == manager
        assert content.published_at is not None
