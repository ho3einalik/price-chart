from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.tenancy.permissions import IsStoreMemberPermission, TenantFilterBackend, Role, user_has_store_permission
from apps.orders.models import Order
from .models import PaymentTransaction, PaymentVerificationStatus
from .serializers import (
    PaymentTransactionSerializer, CreatePaymentInputSerializer, RejectPaymentInputSerializer
)
from .services import verify_payment_transaction, reject_payment_transaction

from decimal import Decimal
from django.db import transaction

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

        verified = verify_payment_transaction(payment=payment, user=request.user)
        return Response(PaymentTransactionSerializer(verified).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        membership = getattr(request, 'membership', None)
        if not (request.user.is_superuser or (membership and (membership.role in [Role.OWNER, Role.ADMIN, Role.BUSINESS_MANAGER] or user_has_store_permission(membership, 'payments.verify')))):
            return Response({'detail': 'شما مجوز رد فیش‌های واریزی و تراکنش‌های مالی را ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        payment = self.get_object()
        serializer = RejectPaymentInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        rejected = reject_payment_transaction(
            payment=payment,
            reason=serializer.validated_data['reason'],
            user=request.user
        )
        return Response(PaymentTransactionSerializer(rejected).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='online-checkout')
    def online_checkout(self, request):
        """Initiates online payment gateway checkout (e.g. Zarinpal)"""
        order_id = request.data.get('order_id')
        callback_url = request.data.get('callback_url', '')
        gateway_name = request.data.get('gateway', 'zarinpal')

        store = request.store
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

        from .gateways import get_payment_gateway
        from .models import PaymentMethod
        gateway = get_payment_gateway(gateway_name)
        if not gateway:
            return Response({'error': f'درگاه پرداخت {gateway_name} پشتیبانی نمی‌شود.'}, status=status.HTTP_400_BAD_REQUEST)

        desc = f"پرداخت سفارش {order.order_number} در فروشگاه {store.name}"
        result = gateway.request_payment(
            amount=remaining_payable,
            callback_url=callback_url,
            description=desc,
            order_id=str(order.id),
            store=store
        )

        if not result.get('success'):
            status_code = status.HTTP_400_BAD_REQUEST if result.get('status') == 'REQUIRES_GATEWAY_CONFIG' else status.HTTP_502_BAD_GATEWAY
            return Response(result, status=status_code)

        payment = PaymentTransaction.objects.create(
            store=store,
            order=order,
            method=PaymentMethod.ONLINE_GATEWAY,
            amount=remaining_payable,
            currency=order.currency,
            reference_number=result.get('authority', ''),
            status=PaymentVerificationStatus.PENDING_VERIFICATION
        )

        return Response({
            'payment_id': str(payment.id),
            'authority': result.get('authority'),
            'payment_url': result.get('payment_url'),
            'amount': remaining_payable
        }, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'], url_path='online-verify')
    def online_verify(self, request):
        """Verifies online payment callback with the payment gateway"""
        authority = request.data.get('authority') or request.query_params.get('Authority')
        gateway_name = request.data.get('gateway', 'zarinpal')

        if not authority:
            return Response({'error': 'پارامتر authority یا شناسه ارجاع الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        store = request.store
        payment = PaymentTransaction.objects.filter(
            store=store,
            reference_number=authority,
            status=PaymentVerificationStatus.PENDING_VERIFICATION
        ).first()

        if not payment:
            return Response({'error': 'تراکنش در انتظار برای این شناسه ارجاع یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        from .gateways import get_payment_gateway
        gateway = get_payment_gateway(gateway_name)
        if not gateway:
            return Response({'error': 'درگاه پرداخت نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        res = gateway.verify_payment(authority=authority, amount=payment.amount, store=store)
        if res.success:
            payment.tracking_code = res.tracking_code
            payment.save(update_fields=['tracking_code'])
            verified = verify_payment_transaction(payment=payment, user=request.user)
            return Response({
                'success': True,
                'message': res.message,
                'tracking_code': res.tracking_code,
                'payment': PaymentTransactionSerializer(verified).data
            }, status=status.HTTP_200_OK)
        else:
            return Response(res.to_dict(), status=status.HTTP_400_BAD_REQUEST)
