import pytest
from decimal import Decimal
from django.utils import timezone
from rest_framework.test import APIClient
from rest_framework.exceptions import ValidationError

from apps.accounts.models import User
from apps.tenancy.models import Store, StoreMembership, Role
from apps.orders.models import Order, Customer, OrderStatus, PaymentStatus, FulfillmentStatus
from apps.inventory.models import Warehouse
from apps.payments.models import PaymentTransaction, PaymentMethod, PaymentVerificationStatus
from apps.payments.services import verify_payment_transaction, reject_payment_transaction, process_payment_refund
from apps.payments.gateways import get_payment_gateway


@pytest.mark.django_db
class TestPhase1FinancialIntegrity:
    def setup_method(self):
        from apps.tenancy.models import Business, MembershipStatus
        self.client = APIClient()
        self.owner = User.objects.create_user(phone_number='09121111111', email='owner@test.com', full_name='Owner User')
        self.staff = User.objects.create_user(phone_number='09122222222', email='staff@test.com', full_name='Staff User')
        self.biz = Business.objects.create(name='Test Biz', owner=self.owner)
        self.store = Store.objects.create(business=self.biz, name='Test Store', currency='IRT')
        StoreMembership.objects.create(user=self.owner, store=self.store, role=Role.OWNER, status=MembershipStatus.ACTIVE, is_active=True)
        StoreMembership.objects.create(user=self.staff, store=self.store, role=Role.ADMIN, status=MembershipStatus.ACTIVE, is_active=True)

        self.warehouse = Warehouse.objects.create(store=self.store, name='Main Warehouse', is_default=True)
        self.customer = Customer.objects.create(store=self.store, phone_number='09123333333', full_name='Customer Test')
        self.order = Order.objects.create(
            store=self.store,
            order_number='ORD-TEST-001',
            customer=self.customer,
            warehouse=self.warehouse,
            total_items_price=Decimal('100000'),
            grand_total=Decimal('100000'),
            order_status=OrderStatus.CONFIRMED,
            payment_status=PaymentStatus.PENDING,
            fulfillment_status=FulfillmentStatus.UNFULFILLED,
        )

    def test_reject_pending_payment_succeeds(self):
        payment = PaymentTransaction.objects.create(
            store=self.store,
            order=self.order,
            method=PaymentMethod.CARD_TO_CARD,
            amount=Decimal('100000'),
            status=PaymentVerificationStatus.PENDING_VERIFICATION,
        )
        rejected = reject_payment_transaction(payment, reason='فیش نامعتبر است', user=self.owner)
        assert rejected.status == PaymentVerificationStatus.REJECTED
        assert rejected.rejection_reason == 'فیش نامعتبر است'
        # Re-reject is idempotent
        re_rejected = reject_payment_transaction(rejected, reason='دلیل تکراری', user=self.owner)
        assert re_rejected.status == PaymentVerificationStatus.REJECTED

    def test_reject_verified_payment_strictly_forbidden(self):
        payment = PaymentTransaction.objects.create(
            store=self.store,
            order=self.order,
            method=PaymentMethod.CARD_TO_CARD,
            amount=Decimal('100000'),
            status=PaymentVerificationStatus.PENDING_VERIFICATION,
        )
        verify_payment_transaction(payment, user=self.owner)
        payment.refresh_from_db()
        assert payment.status == PaymentVerificationStatus.VERIFIED

        with pytest.raises(ValidationError) as exc:
            reject_payment_transaction(payment, reason='کنسلی بعد از واریز', user=self.owner)
        assert "رد کردن تراکنش" in str(exc.value) and "مستردشده" in str(exc.value)

    def test_reject_refunded_payment_strictly_forbidden(self):
        payment = PaymentTransaction.objects.create(
            store=self.store,
            order=self.order,
            method=PaymentMethod.CARD_TO_CARD,
            amount=Decimal('100000'),
            status=PaymentVerificationStatus.PENDING_VERIFICATION,
        )
        verify_payment_transaction(payment, user=self.owner)
        process_payment_refund(payment, amount=Decimal('100000'), reason='استرداد وجه', user=self.owner)
        payment.refresh_from_db()
        assert payment.status == PaymentVerificationStatus.REFUNDED

        with pytest.raises(ValidationError) as exc:
            reject_payment_transaction(payment, reason='تلاش برای رد بعد از ریفاند', user=self.owner)
        assert "رد کردن تراکنش" in str(exc.value) and "مستردشده" in str(exc.value)

    def test_re_verify_refunded_payment_strictly_forbidden(self):
        payment = PaymentTransaction.objects.create(
            store=self.store,
            order=self.order,
            method=PaymentMethod.CARD_TO_CARD,
            amount=Decimal('100000'),
            status=PaymentVerificationStatus.PENDING_VERIFICATION,
        )
        verify_payment_transaction(payment, user=self.owner)
        process_payment_refund(payment, amount=Decimal('100000'), reason='استرداد کامل', user=self.owner)
        payment.refresh_from_db()
        assert payment.status == PaymentVerificationStatus.REFUNDED

        with pytest.raises(ValidationError) as exc:
            verify_payment_transaction(payment, user=self.owner)
        assert "تراکنش مستردشده قابل تأیید مجدد نیست" in str(exc.value)

    def test_re_verify_verified_payment_idempotent(self):
        payment = PaymentTransaction.objects.create(
            store=self.store,
            order=self.order,
            method=PaymentMethod.CARD_TO_CARD,
            amount=Decimal('100000'),
            status=PaymentVerificationStatus.PENDING_VERIFICATION,
        )
        verified1 = verify_payment_transaction(payment, user=self.owner)
        verified2 = verify_payment_transaction(verified1, user=self.owner)
        assert verified2.status == PaymentVerificationStatus.VERIFIED

    def test_online_checkout_idempotency_and_pending_prevention(self):
        self.client.force_authenticate(user=self.owner)

        # Mock Zarinpal gateway to avoid live external HTTP requests in tests
        from unittest.mock import patch
        with patch('apps.payments.gateways.ZarinpalGatewayAdapter.request_payment') as mock_req:
            mock_req.return_value = {
                'success': True,
                'status': 'INITIATED',
                'authority': 'A00000000000000000000000000123456789',
                'payment_url': 'https://www.zarinpal.com/pg/StartPay/A00000000000000000000000000123456789'
            }

            # 1. First checkout request with idempotency key
            res1 = self.client.post(
                '/api/v1/payments/online-checkout/',
                {
                    'order_id': str(self.order.id),
                    'idempotency_key': 'chk-idem-key-1001',
                    'gateway': 'zarinpal'
                },
                HTTP_X_STORE_ID=str(self.store.id),
                format='json'
            )
            assert res1.status_code == 200
            data1 = res1.json()
            assert data1['authority'] == 'A00000000000000000000000000123456789'
            assert mock_req.call_count == 1

            # 2. Replaying the EXACT SAME idempotency key must return 200 OK without calling gateway again
            res2 = self.client.post(
                '/api/v1/payments/online-checkout/',
                {
                    'order_id': str(self.order.id),
                    'idempotency_key': 'chk-idem-key-1001',
                    'gateway': 'zarinpal'
                },
                HTTP_X_STORE_ID=str(self.store.id),
                format='json'
            )
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2['authority'] == data1['authority']
            assert data2.get('idempotent_replayed') is True
            # Gateway was NOT called a second time
            assert mock_req.call_count == 1

            # 3. Sending a DIFFERENT idempotency key while an active pending payment exists must be rejected
            res3 = self.client.post(
                '/api/v1/payments/online-checkout/',
                {
                    'order_id': str(self.order.id),
                    'idempotency_key': 'chk-idem-key-DIFFERENT-2002',
                    'gateway': 'zarinpal'
                },
                HTTP_X_STORE_ID=str(self.store.id),
                format='json'
            )
            assert res3.status_code == 400
            assert "یک پرداخت آنلاین در حال پردازش برای این سفارش وجود دارد" in res3.json()['error']
            assert mock_req.call_count == 1

    def test_unsupported_gateway_handled_honestly(self):
        gw = get_payment_gateway('mellat')
        res = gw.request_payment(amount=Decimal('50000'), callback_url='https://app.shoppilot.ir', description='test', order_id='123')
        assert res['success'] is False
        assert res['status'] == 'UNSUPPORTED'
