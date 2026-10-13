from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from .models import (
    Coupon,
    CustomerLoyaltyAccount,
    LoyaltyPointsLedger,
    LoyaltyActionType,
    ProductBundle,
    ProductBundleItem,
    AbandonedCart,
    AbandonedCartStatus,
    CustomerReferral,
    ReferralStatus,
    ProductRecommendation,
    CampaignAttribution
)
from .serializers import (
    CouponSerializer,
    CustomerLoyaltyAccountSerializer,
    ProductBundleSerializer,
    AbandonedCartSerializer,
    CustomerReferralSerializer,
    ProductRecommendationSerializer,
    CampaignAttributionSerializer
)
from apps.catalog.models import ProductVariant
from apps.tenancy.permissions import IsStoreMemberPermission, IsStoreAdminOrOwnerPermission
from .services import calculate_loyalty_tier

class CouponViewSet(viewsets.ModelViewSet):
    serializer_class = CouponSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsStoreAdminOrOwnerPermission()]
        return [permissions.IsAuthenticated(), IsStoreMemberPermission()]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return Coupon.objects.none()
        qs = Coupon.objects.filter(store=store)
        code = self.request.query_params.get('code')
        if code:
            qs = qs.filter(code__iexact=code)
        return qs

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)

    @action(detail=False, methods=['post'], url_path='validate')
    def validate_coupon(self, request):
        code = request.data.get('code', '').strip()
        already_applied_codes = request.data.get('already_applied_codes', [])
        amount_raw = request.data.get('order_amount', 0)
        try:
            order_amount = Decimal(str(amount_raw))
        except:
            order_amount = Decimal('0')

        if not code:
            return Response({'is_valid': False, 'message': 'کد تخفیف وارد نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        coupon = Coupon.objects.filter(store=request.store, code__iexact=code).first()
        if not coupon:
            return Response({'is_valid': False, 'message': 'کد تخفیف یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        # Stacking protection: if other coupons are applied and this one is not stackable, reject
        if already_applied_codes and not coupon.is_stackable:
            return Response({
                'is_valid': False,
                'message': 'این کد تخفیف امکان ترکیب و استفاده همزمان با کدهای دیگر را ندارد.'
            })

        is_valid, msg = coupon.is_valid(order_amount)
        if not is_valid:
            return Response({'is_valid': False, 'message': msg})

        discount = coupon.calculate_discount(order_amount)
        return Response({
            'is_valid': True,
            'message': msg,
            'code': coupon.code,
            'discount_type': coupon.discount_type,
            'discount_value': str(coupon.discount_value),
            'calculated_discount': str(discount),
            'is_stackable': coupon.is_stackable,
            'final_amount': str(max(Decimal('0'), order_amount - discount))
        })


class CustomerLoyaltyAccountViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerLoyaltyAccountSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return CustomerLoyaltyAccount.objects.none()
        return CustomerLoyaltyAccount.objects.filter(store=store).select_related('customer')

    @action(detail=True, methods=['post'], url_path='adjust-points', permission_classes=[permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission])
    def adjust_points(self, request, pk=None):
        account = self.get_object()
        try:
            diff = int(request.data.get('points', 0))
        except (ValueError, TypeError):
            return Response({'error': 'مقدار تغییر امتیاز نامعتبر است.'}, status=status.HTTP_400_BAD_REQUEST)

        note = request.data.get('note', 'تعدیل دستی توسط مدیر').strip()

        with transaction.atomic():
            account = CustomerLoyaltyAccount.objects.select_for_update().get(id=account.id)
            if account.points_balance + diff < 0:
                return Response({'error': 'موجودی امتیاز نمی‌تواند منفی شود.'}, status=status.HTTP_400_BAD_REQUEST)

            account.points_balance += diff
            if diff > 0:
                account.lifetime_points += diff
            account.tier = calculate_loyalty_tier(account.lifetime_points)
            account.save(update_fields=['points_balance', 'lifetime_points', 'tier'])

            LoyaltyPointsLedger.objects.create(
                store=account.store,
                account=account,
                points_delta=diff,
                action_type=LoyaltyActionType.ADMIN_ADJUSTMENT,
                staff_user=request.user,
                note=note
            )

        return Response(CustomerLoyaltyAccountSerializer(account).data)


class ProductBundleViewSet(viewsets.ModelViewSet):
    serializer_class = ProductBundleSerializer

    def get_permissions(self):
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAuthenticated(), IsStoreAdminOrOwnerPermission()]
        return [permissions.IsAuthenticated(), IsStoreMemberPermission()]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return ProductBundle.objects.none()
        return ProductBundle.objects.filter(store=store).prefetch_related('items__variant__product')

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)


class AbandonedCartViewSet(viewsets.ModelViewSet):
    serializer_class = AbandonedCartSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return AbandonedCart.objects.none()
        return AbandonedCart.objects.filter(store=store).select_related('customer', 'recovery_coupon')

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)

    @action(detail=True, methods=['post'], url_path='trigger-recovery')
    def trigger_recovery(self, request, pk=None):
        from apps.features.adapters import get_integration_adapter
        cart = self.get_object()

        if cart.status == AbandonedCartStatus.RECOVERED:
            return Response(
                {'error': 'این سبد خرید پیش‌تر بازیابی و تکمیل شده است.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # 2-hour anti-spam cooldown check
        if cart.recovery_sms_sent_at and (timezone.now() - cart.recovery_sms_sent_at).total_seconds() < 7200:
            return Response(
                {'error': 'پیامک یادآوری اخیراً ارسال شده است. لطفاً حداقل ۲ ساعت بین پیامک‌ها فاصله بگذارید.'},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )

        target_phone = cart.phone_or_email
        if not target_phone or '@' in target_phone:
            if cart.customer and cart.customer.phone_number:
                target_phone = cart.customer.phone_number

        if not target_phone or '@' in target_phone:
            return Response(
                {'error': 'شماره موبایل معتبر برای ارسال پیامک یادآوری یافت نشد.'},
                status=status.HTTP_400_BAD_REQUEST
            )

        sms_adapter = get_integration_adapter('sms_gateway')
        msg = f"سلام! سبد خرید شما در فروشگاه {cart.store.name} در انتظار شماست. برای تکمیل خرید به وبسایت مراجعه فرمایید."
        if cart.recovery_coupon:
            msg += f" کد تخفیف ویژه شما: {cart.recovery_coupon.code}"

        sms_res = sms_adapter.send_sms(to=target_phone, message=msg, store=cart.store)
        if sms_res.get('status') == 'FAILED':
            return Response({
                'error': f"ارسال پیامک با خطا مواجه شد: {sms_res.get('error', 'خطای درگاه پیامک')}",
                'sms_status': sms_res.get('status')
            }, status=status.HTTP_502_BAD_GATEWAY)

        cart.recovery_sms_sent_at = timezone.now()
        cart.save(update_fields=['recovery_sms_sent_at'])

        return Response({
            'message': f"درخواست ارسال پیامک یادآوری به {target_phone} با موفقیت ثبت شد.",
            'cart_id': str(cart.id),
            'sent_at': cart.recovery_sms_sent_at,
            'sms_status': sms_res.get('status')
        })


class CustomerReferralViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerReferralSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return CustomerReferral.objects.none()
        return CustomerReferral.objects.filter(store=store).select_related('referrer', 'referred_customer')

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)

    @action(detail=True, methods=['post'], url_path='convert', permission_classes=[permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission])
    def convert_referral(self, request, pk=None):
        with transaction.atomic():
            ref = CustomerReferral.objects.select_for_update().get(id=self.get_object().id)
            if ref.status == ReferralStatus.CONVERTED:
                return Response({'error': 'این معرفی پیش‌تر تبدیل شده است.'}, status=status.HTTP_400_BAD_REQUEST)
            if ref.status == ReferralStatus.CANCELLED:
                return Response({'error': 'این معرفی لغو شده است و قابل تبدیل نیست.'}, status=status.HTTP_400_BAD_REQUEST)

            ref.status = ReferralStatus.CONVERTED
            ref.save(update_fields=['status'])

            # Award points to referrer loyalty account
            loyalty, _ = CustomerLoyaltyAccount.objects.select_for_update().get_or_create(
                store=ref.store,
                customer=ref.referrer,
                defaults={'referral_code': ref.referral_code}
            )
            loyalty.points_balance += ref.points_awarded
            loyalty.lifetime_points += ref.points_awarded
            loyalty.tier = calculate_loyalty_tier(loyalty.lifetime_points)
            loyalty.save(update_fields=['points_balance', 'lifetime_points', 'tier'])

            LoyaltyPointsLedger.objects.create(
                store=ref.store,
                account=loyalty,
                points_delta=ref.points_awarded,
                action_type=LoyaltyActionType.REFERRAL,
                note=f"پاداش معرفی دوست با شماره {ref.referee_phone}"
            )

        return Response({
            'message': f"معرفی مشتری تبدیل شد و {ref.points_awarded} امتیاز به {ref.referrer.full_name} تعلق گرفت.",
            'status': ref.status
        })


class ProductRecommendationViewSet(viewsets.ModelViewSet):
    serializer_class = ProductRecommendationSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return ProductRecommendation.objects.none()
        qs = ProductRecommendation.objects.filter(store=store).select_related('source_variant__product', 'recommended_variant__product')
        source_id = self.request.query_params.get('source_variant_id')
        if source_id:
            qs = qs.filter(source_variant_id=source_id)
        return qs

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)


class CampaignAttributionViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CampaignAttributionSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return CampaignAttribution.objects.none()
        return CampaignAttribution.objects.filter(order__store=store).select_related('order', 'campaign')
