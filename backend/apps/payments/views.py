from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.tenancy.permissions import IsStoreMemberPermission, TenantFilterBackend, Role, user_has_store_permission
from apps.orders.models import Order
from .models import PaymentTransaction, PaymentVerificationStatus, PaymentMethod
from .serializers import (
    PaymentTransactionSerializer, CreatePaymentInputSerializer, RejectPaymentInputSerializer
)
from .services import verify_payment_transaction, reject_payment_transaction

from decimal import Decimal
from datetime import timedelta
from django.utils import timezone
from django.db import transaction
from rest_framework.exceptions import ValidationError

class PaymentTransactionViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'method', 'order']
    search_fields = ['reference_number', 'tracking_code', 'order__order_number', 'payer_card_mask']
    ordering_fields = ['created_at', 'amount']
    queryset = PaymentTransaction.objects.all().select_related('order', 'order__customer', 'verified_by')

    def get_serializer_class(self):
        if self.action == 'create':
            return CreatePaymentInputSerializer
        return PaymentTransactionSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = CreatePaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = request.store
        data = serializer.validated_data

        try:
            order = Order.objects.select_for_update().get(id=data['order_id'], store=store)
        except Order.DoesNotExist:
            return Response({'error': 'سفارش یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        # Authoritative server-side remaining payable validation
        verified_sum = sum(
            p.amount for p in order.payments.filter(status=PaymentVerificationStatus.VERIFIED)
        )
        remaining_payable = max(Decimal('0'), order.grand_total - verified_sum)
        if data['amount'] > remaining_payable:
            return Response(
                {'error': f'مبلغ پرداختی ({data["amount"]}) بیشتر از مبلغ باقیمانده سفارش ({remaining_payable}) است.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        payment = PaymentTransaction.objects.create(
            store=store,
            order=order,
            method=data['method'],
            amount=data['amount'],
            currency=order.currency,
            reference_number=data.get('reference_number', ''),
            tracking_code=data.get('tracking_code', ''),
            payer_card_mask=data.get('payer_card_mask', ''),
            receipt_image_url=data.get('receipt_image_url', ''),
            status=PaymentVerificationStatus.PENDING_VERIFICATION
        )
        return Response(PaymentTransactionSerializer(payment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def verify(self, request, pk=None):
        membership = getattr(request, 'membership', None)
        if not (request.user.is_superuser or (membership and (membership.role in [Role.OWNER, Role.ADMIN, Role.BUSINESS_MANAGER] or user_has_store_permission(membership, 'payments.verify')))):
            return Response({'detail': 'شما مجوز تأیید فیش‌های واریزی و تراکنش‌های مالی را ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        payment = self.get_object()
        if payment.status == PaymentVerificationStatus.VERIFIED:
            return Response({'message': 'تراکنش از قبل تأیید شده است.'}, status=status.HTTP_200_OK)

        try:
            verified = verify_payment_transaction(payment=payment, user=request.user)
        except ValidationError as e:
            return Response({'error': e.detail if hasattr(e, 'detail') else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentTransactionSerializer(verified).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        membership = getattr(request, 'membership', None)
        if not (request.user.is_superuser or (membership and (membership.role in [Role.OWNER, Role.ADMIN, Role.BUSINESS_MANAGER] or user_has_store_permission(membership, 'payments.verify')))):
            return Response({'detail': 'شما مجوز رد فیش‌های واریزی و تراکنش‌های مالی را ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        payment = self.get_object()
        serializer = RejectPaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            rejected = reject_payment_transaction(
                payment=payment,
                reason=serializer.validated_data['reason'],
                user=request.user
            )
        except ValidationError as e:
            return Response({'error': e.detail if hasattr(e, 'detail') else str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(PaymentTransactionSerializer(rejected).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def refund(self, request, pk=None):
        membership = getattr(request, 'membership', None)
        if not (request.user.is_superuser or (membership and (membership.role in [Role.OWNER, Role.ADMIN, Role.BUSINESS_MANAGER] or user_has_store_permission(membership, 'payments.verify')))):
            return Response({'detail': 'شما مجوز استرداد تراکنش‌های مالی را ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        payment = self.get_object()
        amount = request.data.get('amount')
        reason = request.data.get('reason', '')

        from .services import process_payment_refund
        try:
            refunded = process_payment_refund(payment=payment, amount=amount, reason=reason, user=request.user)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(PaymentTransactionSerializer(refunded).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='online-checkout')
    def online_checkout(self, request):
        """Initiates online payment gateway checkout (e.g. Zarinpal) without holding open DB transactions during network calls"""
        order_id = request.data.get('order_id')
        callback_url = request.data.get('callback_url', '')
        gateway_name = request.data.get('gateway', 'zarinpal')
        idempotency_key = (request.data.get('idempotency_key') or request.headers.get('X-Idempotency-Key') or '').strip()
        store = request.store

        # 1. Short atomic lock to validate order, verify active pending payments, and pre-claim transaction
        with transaction.atomic():
            try:
                order = Order.objects.select_for_update().get(id=order_id, store=store)
            except (Order.DoesNotExist, ValueError):
                return Response({'error': 'سفارش یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

            verified_sum = sum(
                p.amount for p in order.payments.filter(status=PaymentVerificationStatus.VERIFIED)
            )
            remaining_payable = max(Decimal('0'), order.grand_total - verified_sum)
            if remaining_payable <= 0:
                return Response({'error': 'این سفارش قبلاً به طور کامل تسویه شده است.'}, status=status.HTTP_400_BAD_REQUEST)

            active_pending = order.payments.select_for_update().filter(
                status=PaymentVerificationStatus.PENDING_VERIFICATION,
                method=PaymentMethod.ONLINE_GATEWAY,
                created_at__gte=timezone.now() - timedelta(minutes=15)
            ).first()

            if active_pending:
                # If same idempotency key, replay existing payment idempotently
                if idempotency_key and active_pending.idempotency_key == idempotency_key:
                    from .gateways import get_payment_gateway
                    gateway = get_payment_gateway(gateway_name)
                    payment_url = f"https://www.zarinpal.com/pg/StartPay/{active_pending.reference_number}" if active_pending.reference_number else ""
                    return Response({
                        'payment_id': str(active_pending.id),
                        'authority': active_pending.reference_number,
                        'payment_url': payment_url,
                        'amount': active_pending.amount,
                        'idempotent_replayed': True
                    }, status=status.HTTP_200_OK)

                return Response({
                    'error': 'یک پرداخت آنلاین در حال پردازش برای این سفارش وجود دارد. برای جلوگیری از پرداخت تکراری، لطفاً ابتدا آن را تکمیل یا تعیین تکلیف کنید.',
                    'active_payment_id': str(active_pending.id),
                    'active_authority': active_pending.reference_number
                }, status=status.HTTP_400_BAD_REQUEST)

            payment = PaymentTransaction.objects.create(
                store=store,
                order=order,
                method=PaymentMethod.ONLINE_GATEWAY,
                amount=remaining_payable,
                currency=order.currency,
                reference_number='',
                idempotency_key=idempotency_key,
                status=PaymentVerificationStatus.PENDING_VERIFICATION
            )
            order_number = order.order_number
            order_currency = order.currency
            order_pk = str(order.id)
            payment_pk = str(payment.id)

        # 2. Callback URL allowlisting & safe resolution
        safe_callback = self._resolve_safe_callback_url(request, callback_url)

        from .gateways import get_payment_gateway
        gateway = get_payment_gateway(gateway_name)
        if not gateway:
            return Response({'error': f'درگاه پرداخت {gateway_name} پشتیبانی نمی‌شود.'}, status=status.HTTP_400_BAD_REQUEST)

        # 3. Gateway network call OUTSIDE of database transaction
        desc = f"پرداخت سفارش {order_number} در فروشگاه {store.name}"
        result = gateway.request_payment(
            amount=remaining_payable,
            callback_url=safe_callback,
            description=desc,
            order_id=order_pk,
            store=store,
            currency=order_currency
        )

        if not result.get('success'):
            with transaction.atomic():
                p = PaymentTransaction.objects.select_for_update().get(id=payment_pk)
                p.status = PaymentVerificationStatus.REJECTED
                p.rejection_reason = result.get('message', 'خطا در ارتباط با درگاه پرداخت')
                p.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            status_code = status.HTTP_400_BAD_REQUEST if result.get('status') in ['REQUIRES_GATEWAY_CONFIG', 'INVALID_AMOUNT'] else status.HTTP_502_BAD_GATEWAY
            return Response(result, status=status_code)

        # 4. Attach confirmed gateway authority to pre-reserved transaction
        with transaction.atomic():
            p = PaymentTransaction.objects.select_for_update().get(id=payment_pk)
            p.reference_number = result.get('authority', '')
            p.save(update_fields=['reference_number', 'updated_at'])

        return Response({
            'payment_id': payment_pk,
            'authority': result.get('authority'),
            'payment_url': result.get('payment_url'),
            'amount': remaining_payable
        }, status=status.HTTP_200_OK)

    def _resolve_safe_callback_url(self, request, callback_url: str) -> str:
        fallback = request.build_absolute_uri('/api/v1/payments/online-verify/')
        if not callback_url:
            return fallback

        from urllib.parse import urlsplit
        from django.conf import settings

        try:
            parsed = urlsplit(callback_url.strip())
        except Exception:
            return fallback

        # 1. Strict scheme check: only https (or http in dev/debug)
        allowed_schemes = ['https', 'http'] if getattr(settings, 'DEBUG', False) else ['https']
        if not parsed.scheme or parsed.scheme.lower() not in allowed_schemes:
            return fallback

        # 2. Block userinfo (username / password in URL e.g. user:pass@host)
        if parsed.username or parsed.password:
            return fallback

        # 3. Check hostname
        hostname = parsed.hostname
        if not hostname:
            return fallback
        hostname = hostname.lower()

        # 4. Check port: must be standard or match current host port
        current_split = urlsplit(request.build_absolute_uri())
        current_port = current_split.port
        if parsed.port is not None:
            if parsed.scheme == 'https' and parsed.port not in [443, current_port]:
                return fallback
            if parsed.scheme == 'http' and parsed.port not in [80, 8000, 3000, current_port]:
                return fallback

        # 5. Allowed hostnames matching
        allowed_hostnames = set()
        if current_split.hostname:
            allowed_hostnames.add(current_split.hostname.lower())

        for h in getattr(settings, 'ALLOWED_HOSTS', []):
            if h and h != '*':
                allowed_hostnames.add(h.lower().lstrip('.'))

        for origin in list(getattr(settings, 'CORS_ALLOWED_ORIGINS', [])) + list(getattr(settings, 'CSRF_TRUSTED_ORIGINS', [])):
            try:
                sp = urlsplit(origin)
                if sp.hostname:
                    allowed_hostnames.add(sp.hostname.lower())
            except Exception:
                pass

        store = getattr(request, 'store', None)
        if store and hasattr(store, 'custom_domain') and store.custom_domain:
            allowed_hostnames.add(store.custom_domain.lower())

        if hostname not in allowed_hostnames:
            return fallback

        return callback_url.strip()

    @action(detail=False, methods=['get', 'post'], url_path='online-verify')
    def online_verify(self, request):
        """Verifies online payment callback with the payment gateway idempotently"""
        authority = (
            request.data.get('authority')
            or request.data.get('Authority')
            or request.query_params.get('Authority')
            or request.query_params.get('authority')
        )
        status_param = (
            request.data.get('Status')
            or request.query_params.get('Status')
            or request.data.get('status')
            or request.query_params.get('status')
        )
        gateway_name = request.data.get('gateway', 'zarinpal')

        if not authority:
            return Response({'error': 'پارامتر authority یا شناسه ارجاع الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        # Lookup payment primarily by authority / reference_number
        payment = PaymentTransaction.objects.filter(
            reference_number=authority
        ).select_related('store', 'order').first()

        if not payment:
            return Response({'error': 'تراکنش برای این شناسه ارجاع یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        store = payment.store
        req_store = getattr(request, 'store', None)
        if req_store and req_store.id != store.id and not (request.user and (request.user.is_superuser or request.user.is_staff)):
            return Response({'error': 'عدم تطابق فروشگاه تراکنش با درخواست.'}, status=status.HTTP_403_FORBIDDEN)

        if payment.status == PaymentVerificationStatus.VERIFIED:
            return Response({
                'success': True,
                'message': 'تراکنش از قبل تأیید شده است.',
                'tracking_code': payment.tracking_code,
                'payment': PaymentTransactionSerializer(payment).data
            }, status=status.HTTP_200_OK)

        if payment.status == PaymentVerificationStatus.REFUNDED:
            return Response({
                'error': 'این تراکنش قبلاً مسترد شده است و امکان تأیید مجدد آن وجود ندارد.'
            }, status=status.HTTP_400_BAD_REQUEST)

        if status_param and str(status_param).upper() in ['NOK', 'CANCELLED', 'CANCELED']:
            with transaction.atomic():
                p = PaymentTransaction.objects.select_for_update().get(id=payment.id)
                if p.status != PaymentVerificationStatus.VERIFIED:
                    p.rejection_reason = "تراکنش توسط کاربر در صفحه درگاه لغو شد."
                    p.status = PaymentVerificationStatus.REJECTED
                    p.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            return Response({
                'success': False,
                'status': 'CANCELLED_BY_USER',
                'message': 'پرداخت توسط کاربر لغو شد.',
                'payment': PaymentTransactionSerializer(payment).data
            }, status=status.HTTP_400_BAD_REQUEST)

        from .gateways import get_payment_gateway
        gateway = get_payment_gateway(gateway_name)
        if not gateway:
            return Response({'error': 'درگاه پرداخت نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        # Call gateway verify outside DB lock
        res = gateway.verify_payment(
            authority=authority,
            amount=payment.amount,
            store=store,
            currency=payment.currency
        )
        if res.success:
            with transaction.atomic():
                p = PaymentTransaction.objects.select_for_update().get(id=payment.id)
                if p.status != PaymentVerificationStatus.VERIFIED:
                    p.tracking_code = res.tracking_code
                    p.save(update_fields=['tracking_code'])
                    verified = verify_payment_transaction(payment=p, user=request.user if request.user.is_authenticated else None)
                else:
                    verified = p

            return Response({
                'success': True,
                'message': res.message,
                'tracking_code': res.tracking_code,
                'payment': PaymentTransactionSerializer(verified).data
            }, status=status.HTTP_200_OK)
        else:
            # If communication error/timeout, do not permanently reject; keep in PENDING_VERIFICATION for retry/reconciliation
            if res.status != 'COMMUNICATION_ERROR':
                with transaction.atomic():
                    p = PaymentTransaction.objects.select_for_update().get(id=payment.id)
                    if p.status != PaymentVerificationStatus.VERIFIED:
                        p.status = PaymentVerificationStatus.REJECTED
                        p.rejection_reason = res.message
                        p.save(update_fields=['status', 'rejection_reason', 'updated_at'])
            return Response(res.to_dict(), status=status.HTTP_400_BAD_REQUEST)

