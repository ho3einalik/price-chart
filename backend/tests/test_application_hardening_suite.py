import pytest
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role, MembershipStatus
from apps.catalog.models import Category, Product, ProductVariant
from apps.inventory.models import Warehouse, InventoryBalance
from apps.inventory.services import get_or_create_balance
from apps.orders.models import Order, OrderItem, Customer, OrderStatus, PaymentStatus, FulfillmentStatus
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentVerificationStatus
from apps.payments.services import process_payment_refund
from apps.wholesale_pos.models import B2BClientProfile, ProformaInvoice, ProformaStatus, B2BTier
from apps.wholesale_pos.services import convert_proforma_to_order
from apps.marketing.models import CustomerLoyaltyAccount, CustomerReferral, LoyaltyPointsLedger, LoyaltyTier, LoyaltyActionType, ReferralStatus


@pytest.mark.django_db
class TestApplicationHardeningSuite:
    @pytest.fixture
    def setup_data(self):
        owner = User.objects.create_user(email="owner_h@test.com", password="password123", full_name="Owner H")
        business = Business.objects.create(name="Hardening Biz", owner=owner)
        store = Store.objects.create(business=business, name="Hardening Store", currency="IRR")
        StoreMembership.objects.create(store=store, user=owner, role=Role.OWNER, status=MembershipStatus.ACTIVE)

        # Another store for tenant isolation checks
        other_owner = User.objects.create_user(email="other_h@test.com", password="password123", full_name="Other H")
        other_biz = Business.objects.create(name="Other Biz", owner=other_owner)
        other_store = Store.objects.create(business=other_biz, name="Other Store", currency="IRR")
        StoreMembership.objects.create(store=other_store, user=other_owner, role=Role.OWNER, status=MembershipStatus.ACTIVE)

        # Read only user
        read_only_user = User.objects.create_user(email="readonly@test.com", password="password123", full_name="Read Only User")
        StoreMembership.objects.create(store=store, user=read_only_user, role=Role.READ_ONLY, status=MembershipStatus.ACTIVE)

        category = Category.objects.create(store=store, name="Main Cat", slug="main-cat")
        product = Product.objects.create(store=store, category=category, name="Test Phone", slug="test-phone")
        variant = ProductVariant.objects.create(
            store=store, product=product, sku="PHONE-01", retail_price=Decimal("1000000"), cost_price=Decimal("800000")
        )

        wh1 = Warehouse.objects.create(store=store, name="Central Warehouse", code="WH-CENTRAL")
        wh2 = Warehouse.objects.create(store=store, name="Branch Warehouse", code="WH-BRANCH")
        other_wh = Warehouse.objects.create(store=other_store, name="Other Warehouse", code="WH-OTHER")

        # Initial stock in WH1
        bal = get_or_create_balance(store=store, warehouse=wh1, variant=variant)
        bal.on_hand_quantity = 100
        bal.save()

        customer = Customer.objects.create(store=store, full_name="John Doe", phone_number="09121112233")

        return {
            'owner': owner,
            'store': store,
            'other_store': other_store,
            'read_only_user': read_only_user,
            'category': category,
            'product': product,
            'variant': variant,
            'wh1': wh1,
            'wh2': wh2,
            'other_wh': other_wh,
            'customer': customer
        }

    def test_read_only_role_denied_mutating_actions(self, setup_data):
        client = APIClient()
        client.force_authenticate(user=setup_data['read_only_user'])
        store = setup_data['store']

        # GET is allowed
        res_get = client.get('/api/v1/catalog/products/', HTTP_X_STORE_ID=str(store.id))
        assert res_get.status_code == status.HTTP_200_OK

        # POST is denied
        res_post = client.post(
            '/api/v1/catalog/products/',
            {
                'name': 'Hacker Product',
                'category': str(setup_data['category'].id),
                'description': 'Attempt'
            },
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_post.status_code == status.HTTP_403_FORBIDDEN

    def test_inter_warehouse_stock_transfer_and_cross_store_denial(self, setup_data):
        client = APIClient()
        client.force_authenticate(user=setup_data['owner'])
        store = setup_data['store']
        wh1 = setup_data['wh1']
        wh2 = setup_data['wh2']
        other_wh = setup_data['other_wh']
        variant = setup_data['variant']

        # 1. Cross-store transfer denied
        res_cross = client.post(
            '/api/v1/inventory/transfers/',
            {
                'source_warehouse_id': str(wh1.id),
                'dest_warehouse_id': str(other_wh.id),
                'variant_id': str(variant.id),
                'quantity': 10
            },
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_cross.status_code in [status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND]

        # 2. Same-store transfer succeeds atomically
        res_valid = client.post(
            '/api/v1/inventory/transfers/',
            {
                'source_warehouse_id': str(wh1.id),
                'dest_warehouse_id': str(wh2.id),
                'variant_id': str(variant.id),
                'quantity': 25,
                'reason': 'Rebalancing store branches'
            },
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_valid.status_code == status.HTTP_200_OK

        # Verify balances
        bal1 = InventoryBalance.objects.get(warehouse=wh1, variant=variant)
        bal2 = InventoryBalance.objects.get(warehouse=wh2, variant=variant)
        assert bal1.on_hand_quantity == 75
        assert bal2.on_hand_quantity == 25

    def test_partial_payment_refund_and_cumulative_cap(self, setup_data):
        store = setup_data['store']
        customer = setup_data['customer']
        user = setup_data['owner']
        wh1 = setup_data['wh1']

        order = Order.objects.create(
            store=store,
            order_number="ORD-REFUND-01",
            customer=customer,
            warehouse=wh1,
            grand_total=Decimal("1000000"),
            payment_status=PaymentStatus.PAID
        )

        tx = PaymentTransaction.objects.create(
            store=store,
            order=order,
            method=PaymentMethod.ONLINE_GATEWAY,
            amount=Decimal("1000000"),
            status=PaymentVerificationStatus.VERIFIED,
            reference_number="TX-100",
            tracking_code="TRK-100"
        )

        # First partial refund: 400,000
        refund1 = process_payment_refund(
            payment=tx,
            amount=Decimal("400000"),
            reason="Partial return of 1 item",
            user=user
        )
        tx.refresh_from_db()
        order.refresh_from_db()
        assert tx.refunded_amount == Decimal("400000")
        assert order.payment_status == PaymentStatus.PARTIALLY_PAID

        # Second partial refund: 600,000 (remaining balance)
        refund2 = process_payment_refund(
            payment=tx,
            amount=Decimal("600000"),
            reason="Return second item",
            user=user
        )
        tx.refresh_from_db()
        order.refresh_from_db()
        assert tx.refunded_amount == Decimal("1000000")
        assert tx.status == PaymentVerificationStatus.REFUNDED
        assert order.payment_status == PaymentStatus.REFUNDED

        # Third refund attempt exceeds net paid: must raise Exception
        with pytest.raises(Exception):
            process_payment_refund(
                payment=tx,
                amount=Decimal("50000"),
                reason="Excess refund",
                user=user
            )

    def test_proforma_to_order_concurrency_and_idempotency(self, setup_data):
        store = setup_data['store']
        customer = setup_data['customer']
        user = setup_data['owner']
        variant = setup_data['variant']

        client_profile = B2BClientProfile.objects.create(
            store=store,
            customer=customer,
            company_name="Mega Corp",
            credit_limit=Decimal("50000000"),
            tier=B2BTier.GOLD
        )

        proforma = ProformaInvoice.objects.create(
            store=store,
            client=client_profile,
            invoice_number="PI-9900",
            subtotal=Decimal("5000000"),
            discount=Decimal("500000"),
            tax=Decimal("0"),
            grand_total=Decimal("4500000"),
            valid_until=timezone.now() + timezone.timedelta(days=7),
            items=[{
                'variant_id': str(variant.id),
                'quantity': 5,
                'unit_price': 900000
            }]
        )

        # Ensure stock in warehouses
        bal1 = get_or_create_balance(store=store, warehouse=setup_data['wh1'], variant=variant)
        bal1.on_hand_quantity = 50
        bal1.save()
        bal2 = get_or_create_balance(store=store, warehouse=setup_data['wh2'], variant=variant)
        bal2.on_hand_quantity = 50
        bal2.save()

        # 1. First conversion succeeds
        order = convert_proforma_to_order(proforma=proforma, user=user)
        assert order is not None
        assert order.grand_total == Decimal("4500000")
        proforma.refresh_from_db()
        assert proforma.status == ProformaStatus.CONVERTED

        # 2. Second conversion attempt must raise ValidationError
        with pytest.raises(ValidationError) as exc:
            convert_proforma_to_order(proforma=proforma, user=user)
        assert "قبلاً" in str(exc.value)

    def test_customer_loyalty_adjust_points_and_ledger(self, setup_data):
        client = APIClient()
        client.force_authenticate(user=setup_data['owner'])
        store = setup_data['store']
        customer = setup_data['customer']

        account = CustomerLoyaltyAccount.objects.create(
            store=store,
            customer=customer,
            points_balance=0,
            lifetime_points=0,
            tier=LoyaltyTier.BRONZE
        )

        # 1. Adjust +600 points -> upgrades to SILVER tier
        res1 = client.post(
            f'/api/v1/marketing/loyalty/{account.id}/adjust-points/',
            {'points': 600, 'note': 'Bonus VIP customer'},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res1.status_code == status.HTTP_200_OK
        account.refresh_from_db()
        assert account.points_balance == 600
        assert account.lifetime_points == 600
        assert account.tier == LoyaltyTier.SILVER

        ledger_entry = LoyaltyPointsLedger.objects.filter(account=account).first()
        assert ledger_entry is not None
        assert ledger_entry.points_delta == 600
        assert ledger_entry.action_type == LoyaltyActionType.ADMIN_ADJUSTMENT
        assert ledger_entry.staff_user == setup_data['owner']

        # 2. Adjust points negatively below 0 is denied
        res_neg = client.post(
            f'/api/v1/marketing/loyalty/{account.id}/adjust-points/',
            {'points': -1000},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_neg.status_code == status.HTTP_400_BAD_REQUEST

    def test_customer_referral_conversion_and_idempotency(self, setup_data):
        client = APIClient()
        client.force_authenticate(user=setup_data['owner'])
        store = setup_data['store']
        customer = setup_data['customer']

        referral = CustomerReferral.objects.create(
            store=store,
            referrer=customer,
            referee_phone="09351234567",
            referral_code="REF-JOHN",
            status=ReferralStatus.INVITED,
            points_awarded=75
        )

        # 1. Convert referral
        res = client.post(
            f'/api/v1/marketing/referrals/{referral.id}/convert/',
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res.status_code == status.HTTP_200_OK

        referral.refresh_from_db()
        assert referral.status == ReferralStatus.CONVERTED

        loyalty = CustomerLoyaltyAccount.objects.get(store=store, customer=customer)
        assert loyalty.points_balance == 75

        ledger = LoyaltyPointsLedger.objects.filter(account=loyalty, action_type=LoyaltyActionType.REFERRAL).first()
        assert ledger is not None
        assert ledger.points_delta == 75

        # 2. Converting again is rejected
        res_again = client.post(
            f'/api/v1/marketing/referrals/{referral.id}/convert/',
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_again.status_code == status.HTTP_400_BAD_REQUEST

    def test_social_publishing_evidence_and_self_approval_denial(self, setup_data):
        from apps.social.models import SocialContent, SocialPlatform, ContentType, ContentStatus, PublishingMode
        from apps.features.models import StoreFeatureSetting, SubscriptionTier
        store = setup_data['store']
        owner = setup_data['owner']
        StoreFeatureSetting.objects.create(store=store, tier=SubscriptionTier.PRO)
        creator = User.objects.create_user(email="creator@test.com", password="pass", full_name="Creator User")
        StoreMembership.objects.create(
            store=store,
            user=creator,
            role=Role.CONTENT_CREATOR,
            custom_permissions=['content.create', 'content.submit', 'content.publish'],
            status=MembershipStatus.ACTIVE
        )

        content = SocialContent.objects.create(
            store=store,
            creator=creator,
            title="Spring Promo",
            content_type=ContentType.POST,
            publishing_mode=PublishingMode.MANUAL_REMINDER,
            status=ContentStatus.READY_FOR_REVIEW
        )

        creator_client = APIClient()
        creator_client.force_authenticate(user=creator)

        # 1. Creator cannot self-approve or publish without independent manager review
        res_self_pub = creator_client.post(
            f'/api/v1/social/contents/{content.id}/publish/',
            {'published_url': 'https://instagram.com/p/123/'},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_self_pub.status_code == status.HTTP_403_FORBIDDEN

        # 2. Manager cannot publish without evidence
        owner_client = APIClient()
        owner_client.force_authenticate(user=owner)

        res_no_evidence = owner_client.post(
            f'/api/v1/social/contents/{content.id}/publish/',
            {},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_no_evidence.status_code == status.HTTP_400_BAD_REQUEST

        # 3. Manager publishes with valid evidence -> succeeds and sets approved_by
        res_valid_pub = owner_client.post(
            f'/api/v1/social/contents/{content.id}/publish/',
            {'published_url': 'https://instagram.com/p/valid_post/'},
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_valid_pub.status_code == status.HTTP_200_OK
        content.refresh_from_db()
        assert content.status == ContentStatus.PUBLISHED
        assert content.approved_by == owner
        assert content.published_url == 'https://instagram.com/p/valid_post/'

    def test_subscription_checkout_arbitrary_callback_rejection(self, setup_data):
        from apps.features.models import SubscriptionInvoice, InvoiceStatus, SubscriptionTier
        store = setup_data['store']
        owner = setup_data['owner']

        invoice = SubscriptionInvoice.objects.create(
            store=store,
            tier=SubscriptionTier.PRO,
            amount=Decimal('490000'),
            status=InvoiceStatus.PENDING,
            payment_reference="INV-TEST-CB"
        )

        client = APIClient()
        client.force_authenticate(user=owner)

        # 1. Arbitrary attacker callback is rejected
        res_evil = client.post(
            f'/api/v1/features/invoices/{invoice.id}/checkout/',
            {
                'callback_url': 'https://evil-phishing-site.com/steal-token',
                'gateway': 'zarinpal'
            },
            HTTP_X_STORE_ID=str(store.id)
        )
        assert res_evil.status_code == status.HTTP_400_BAD_REQUEST
        assert 'callback_url' in res_evil.data

        # 2. Cross-store invoice access is denied (404)
        other_store = setup_data['other_store']
        other_owner = setup_data['other_store'].business.owner
        other_client = APIClient()
        other_client.force_authenticate(user=other_owner)

        res_cross = other_client.post(
            f'/api/v1/features/invoices/{invoice.id}/checkout/',
            {},
            HTTP_X_STORE_ID=str(other_store.id)
        )
        assert res_cross.status_code == status.HTTP_404_NOT_FOUND

    def test_abandoned_cart_sms_status_distinction_and_retry(self, setup_data):
        from unittest import mock
        from apps.marketing.models import AbandonedCart, AbandonedCartStatus, RecoveryDeliveryStatus
        from apps.marketing.tasks import check_abandoned_carts_and_notify

        store = setup_data['store']
        customer = setup_data['customer']
        owner = setup_data['owner']

        cart = AbandonedCart.objects.create(
            store=store,
            customer=customer,
            phone_or_email="09123334455",
            total_amount=150000,
            status=AbandonedCartStatus.PENDING,
            created_at=timezone.now() - timezone.timedelta(hours=3)
        )
        # Update created_at to bypass auto_now_add in test
        AbandonedCart.objects.filter(id=cart.id).update(created_at=timezone.now() - timezone.timedelta(hours=3))

        client = APIClient()
        client.force_authenticate(user=owner)

        # 1. Unconfigured gateway does NOT stamp recovery_sms_sent_at and returns 400
        with mock.patch('apps.features.adapters.SMSGateway.send_sms', return_value={'status': 'NOT_CONFIGURED', 'message': 'API key missing'}):
            res_unconf = client.post(
                f'/api/v1/marketing/abandoned-carts/{cart.id}/trigger-recovery/',
                HTTP_X_STORE_ID=str(store.id)
            )
            assert res_unconf.status_code == status.HTTP_400_BAD_REQUEST
            cart.refresh_from_db()
            assert cart.delivery_status == RecoveryDeliveryStatus.NOT_CONFIGURED
            assert cart.recovery_sms_sent_at is None

        # 2. Failed gateway does NOT stamp recovery_sms_sent_at and returns 502
        with mock.patch('apps.features.adapters.SMSGateway.send_sms', return_value={'status': 'FAILED', 'error': 'Provider down'}):
            res_fail = client.post(
                f'/api/v1/marketing/abandoned-carts/{cart.id}/trigger-recovery/',
                HTTP_X_STORE_ID=str(store.id)
            )
            assert res_fail.status_code == status.HTTP_502_BAD_GATEWAY
            cart.refresh_from_db()
            assert cart.delivery_status == RecoveryDeliveryStatus.FAILED
            assert cart.recovery_sms_sent_at is None

        # 3. Accepted gateway stamps recovery_sms_sent_at and returns 200
        with mock.patch('apps.features.adapters.SMSGateway.send_sms', return_value={'status': 'ACCEPTED', 'message_id': 'ACK_999'}):
            res_ok = client.post(
                f'/api/v1/marketing/abandoned-carts/{cart.id}/trigger-recovery/',
                HTTP_X_STORE_ID=str(store.id)
            )
            assert res_ok.status_code == status.HTTP_200_OK
            cart.refresh_from_db()
            assert cart.delivery_status == RecoveryDeliveryStatus.SENT
            assert cart.recovery_sms_sent_at is not None

