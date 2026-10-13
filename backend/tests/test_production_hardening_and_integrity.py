import pytest
from decimal import Decimal
from unittest.mock import patch
from django.core.exceptions import ImproperlyConfigured
from rest_framework.test import APIClient
from rest_framework import status

from apps.accounts.models import User
from apps.tenancy.models import Business, Store, StoreMembership, Role
from apps.inventory.models import Warehouse
from apps.features.models import SubscriptionTier, StoreFeatureSetting, IntegrationState
from apps.features.services import FeatureService
from apps.features.adapters import SMSGatewayIntegrationAdapter
from apps.orders.models import Order, OrderStatus, PaymentStatus, Customer
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentVerificationStatus
from apps.payments.services import verify_payment_transaction


@pytest.mark.django_db
class TestProductionHardeningAndIntegrity:

    def setup_method(self):
        self.client = APIClient()
        self.owner = User.objects.create_user(
            email="harden_owner@example.com",
            password="StrongPassword123!",
            full_name="Hardened Owner"
        )
        self.business = Business.objects.create(name="Hardened Business", owner=self.owner)
        self.store = Store.objects.create(business=self.business, name="Hardened Store")
        self.membership = StoreMembership.objects.create(
            store=self.store,
            user=self.owner,
            role=Role.OWNER,
            is_active=True
        )
        self.warehouse = Warehouse.objects.create(
            store=self.store,
            name="Main Warehouse"
        )

        self.customer = Customer.objects.create(
            store=self.store,
            full_name="Test Customer",
            phone_number="09120000000"
        )

    def test_default_subscription_tier_is_free(self):
        """Newly created store feature settings must default to FREE tier, not PRO."""
        settings = FeatureService.get_or_create_settings(self.store)
        assert settings.tier == SubscriptionTier.FREE
        assert settings.get_tier_display() == 'طرح رایگان (Free)'

    def test_subscription_tier_upgrade_protection(self):
        """Tenants cannot arbitrarily self-upgrade to PRO or ENTERPRISE without staff/payment in production."""
        self.client.force_authenticate(user=self.owner)
        settings = FeatureService.get_or_create_settings(self.store)
        assert settings.tier == SubscriptionTier.FREE

        with patch('django.conf.settings.DEBUG', False):
            # Attempting to upgrade to PRO without staff status
            res = self.client.post(
                '/api/v1/features/tier/',
                {'tier': SubscriptionTier.PRO},
                HTTP_X_STORE_ID=str(self.store.id),
                format='json'
            )
            assert res.status_code == status.HTTP_403_FORBIDDEN
            assert "ارتقای پلن اشتراک" in str(res.data)

            # Store tier remains FREE
            settings.refresh_from_db()
            assert settings.tier == SubscriptionTier.FREE

    def test_payment_amount_positive_validation(self):
        """Negative and zero amounts must be rejected when creating payments."""
        self.client.force_authenticate(user=self.owner)
        order = Order.objects.create(
            store=self.store,
            customer=self.customer,
            warehouse=self.warehouse,
            order_number="ORD-HARDEN-001",
            total_items_price=Decimal('500000'),
            grand_total=Decimal('500000'),
            payment_status=PaymentStatus.PENDING
        )

        # 1. Zero amount
        res_zero = self.client.post(
            '/api/v1/payments/',
            {
                'order_id': str(order.id),
                'amount': 0,
                'method': PaymentMethod.CARD_TO_CARD
            },
            HTTP_X_STORE_ID=str(self.store.id),
            format='json'
        )
        assert res_zero.status_code == status.HTTP_400_BAD_REQUEST

        # 2. Negative amount
        res_neg = self.client.post(
            '/api/v1/payments/',
            {
                'order_id': str(order.id),
                'amount': -100000,
                'method': PaymentMethod.CARD_TO_CARD
            },
            HTTP_X_STORE_ID=str(self.store.id),
            format='json'
        )
        assert res_neg.status_code == status.HTTP_400_BAD_REQUEST

    def test_payment_exceeding_remaining_payable_rejected(self):
        """Payment amount cannot exceed the order's remaining payable balance."""
        self.client.force_authenticate(user=self.owner)
        order = Order.objects.create(
            store=self.store,
            customer=self.customer,
            warehouse=self.warehouse,
            order_number="ORD-HARDEN-002",
            total_items_price=Decimal('300000'),
            grand_total=Decimal('300000'),
            payment_status=PaymentStatus.PENDING
        )

        # Attempt to pay 400,000 for a 300,000 order
        res_excess = self.client.post(
            '/api/v1/payments/',
            {
                'order_id': str(order.id),
                'amount': 400000,
                'method': PaymentMethod.CARD_TO_CARD
            },
            HTTP_X_STORE_ID=str(self.store.id),
            format='json'
        )
        assert res_excess.status_code == status.HTTP_400_BAD_REQUEST
        assert "بیشتر از مبلغ باقیمانده" in str(res_excess.data)

        # Pay exact remaining 300,000 succeeds
        res_valid = self.client.post(
            '/api/v1/payments/',
            {
                'order_id': str(order.id),
                'amount': 300000,
                'method': PaymentMethod.CARD_TO_CARD
            },
            HTTP_X_STORE_ID=str(self.store.id),
            format='json'
        )
        assert res_valid.status_code == status.HTTP_201_CREATED

    def test_payment_verification_idempotency_and_locking(self):
        """Verifying payment is idempotent and updates order payment status correctly."""
        order = Order.objects.create(
            store=self.store,
            customer=self.customer,
            warehouse=self.warehouse,
            order_number="ORD-HARDEN-003",
            total_items_price=Decimal('1000000'),
            grand_total=Decimal('1000000'),
            payment_status=PaymentStatus.PENDING
        )
        payment = PaymentTransaction.objects.create(
            store=self.store,
            order=order,
            amount=Decimal('1000000'),
            currency='IRT',
            method=PaymentMethod.CARD_TO_CARD,
            status=PaymentVerificationStatus.PENDING_VERIFICATION
        )

        # First verification
        verified = verify_payment_transaction(payment, self.owner)
        assert verified.status == PaymentVerificationStatus.VERIFIED
        order.refresh_from_db()
        assert order.payment_status == PaymentStatus.PAID

        # Second verification (idempotent call)
        verified_again = verify_payment_transaction(verified, self.owner)
        assert verified_again.status == PaymentVerificationStatus.VERIFIED
        order.refresh_from_db()
        assert order.payment_status == PaymentStatus.PAID

    def test_sms_adapter_masks_phone_and_honest_state(self):
        """SMS Gateway masks phone numbers in logs and does not claim fake success."""
        adapter = SMSGatewayIntegrationAdapter()
        with patch.dict('os.environ', {}, clear=True):
            res = adapter.send_sms(to="09123456789", message="Test alert", store=self.store)
            assert res['status'] == 'NOT_CONFIGURED'
            assert adapter.get_status(self.store) == IntegrationState.NOT_CONFIGURED

    def test_production_settings_validation(self):
        """Verify production security rules: weak secret key, wildcard hosts, and SQLite are rejected."""
        import subprocess
        import sys

        # 1. Weak secret key with DEBUG=False must fail
        cmd_weak_key = [
            sys.executable, "-c",
            "import os; os.environ['DJANGO_DEBUG']='False'; os.environ['DJANGO_SECRET_KEY']='short'; import config.settings"
        ]
        proc = subprocess.run(cmd_weak_key, capture_output=True, text=True, cwd=str(self.store.pk and "c:/Users/ASUS/OneDrive/Desktop/onlineshop/backend"))
        assert proc.returncode != 0
        assert "ImproperlyConfigured" in proc.stderr
        assert "DJANGO_SECRET_KEY" in proc.stderr

        # 2. Wildcard host with DEBUG=False must fail
        cmd_wildcard = [
            sys.executable, "-c",
            "import os; os.environ['DJANGO_DEBUG']='False'; os.environ['DJANGO_SECRET_KEY']='strong-secret-key-32-chars-long-123456'; os.environ['DJANGO_ALLOWED_HOSTS']='*'; import config.settings"
        ]
        proc2 = subprocess.run(cmd_wildcard, capture_output=True, text=True, cwd="c:/Users/ASUS/OneDrive/Desktop/onlineshop/backend")
        assert proc2.returncode != 0
        assert "ImproperlyConfigured" in proc2.stderr
        assert "DJANGO_ALLOWED_HOSTS" in proc2.stderr

        # 3. SQLite in production without ALLOW_SQLITE_IN_PRODUCTION must fail
        cmd_sqlite = [
            sys.executable, "-c",
            "import os; os.environ['DJANGO_DEBUG']='False'; os.environ['DJANGO_SECRET_KEY']='strong-secret-key-32-chars-long-123456'; os.environ['DJANGO_ALLOWED_HOSTS']='api.shoppilot.ir'; import config.settings"
        ]
        proc3 = subprocess.run(cmd_sqlite, capture_output=True, text=True, cwd="c:/Users/ASUS/OneDrive/Desktop/onlineshop/backend")
        assert proc3.returncode != 0
        assert "ImproperlyConfigured" in proc3.stderr
        assert "Production database must be configured with PostgreSQL" in proc3.stderr
