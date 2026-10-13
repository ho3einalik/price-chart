from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import permissions, status
from rest_framework.exceptions import PermissionDenied

from apps.tenancy.permissions import IsStoreMemberPermission, IsStoreAdminOrOwnerPermission, get_request_store
from .services import FeatureService
from .adapters import IntegrationRegistry
from .serializers import (
    FeatureItemSerializer,
    FeatureToggleInputSerializer,
    SubscriptionTierUpdateInputSerializer,
    IntegrationConfigInputSerializer
)


class FeatureCatalogView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get(self, request):
        store = get_request_store(request)
        catalog = FeatureService.get_store_feature_catalog(store)
        settings = FeatureService.get_or_create_settings(store)
        return Response({
            'tier': settings.tier,
            'tier_display': settings.get_tier_display(),
            'features': FeatureItemSerializer(catalog, many=True).data
        })


class FeatureToggleView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission]

    def post(self, request):
        store = get_request_store(request)
        serializer = FeatureToggleInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = FeatureService.toggle_feature(
            store=store,
            feature_key=serializer.validated_data['feature'],
            enable=serializer.validated_data['enabled'],
            actor=request.user
        )
        return Response(result, status=status.HTTP_200_OK)


from django.conf import settings as django_settings
from django.utils import timezone
from decimal import Decimal
import uuid
from .models import SubscriptionTier, SubscriptionInvoice, InvoiceStatus, IntegrationState
from .serializers import (
    FeatureItemSerializer,
    FeatureToggleInputSerializer,
    SubscriptionTierUpdateInputSerializer,
    IntegrationConfigInputSerializer,
    SubscriptionInvoiceSerializer,
    CreateInvoiceInputSerializer
)

class SubscriptionTierView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission]

    def post(self, request):
        store = get_request_store(request)
        serializer = SubscriptionTierUpdateInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        settings = FeatureService.get_or_create_settings(store)
        old_tier = settings.tier
        new_tier = serializer.validated_data['tier']

        tier_hierarchy = {
            SubscriptionTier.FREE: 1,
            SubscriptionTier.STARTER: 2,
            SubscriptionTier.PRO: 3,
            SubscriptionTier.ENTERPRISE: 4
        }
        current_rank = tier_hierarchy.get(old_tier, 1)
        new_rank = tier_hierarchy.get(new_tier, 1)

        # In production, upgrading to a higher tier requires superuser, platform staff, or verified paid invoice
        payment_reference = serializer.validated_data.get('payment_reference')
        if new_rank > current_rank and not (request.user.is_superuser or request.user.is_staff or django_settings.DEBUG):
            invoice = None
            if payment_reference:
                invoice = SubscriptionInvoice.objects.filter(
                    store=store,
                    tier=new_tier,
                    status=InvoiceStatus.PAID,
                    payment_reference=payment_reference
                ).first()

            if not invoice:
                raise PermissionDenied("ارتقای پلن اشتراک مستلزم تسویه فاکتور اشتراک معتبر (SubscriptionInvoice) یا تأیید مدیر سامانه است.")

        settings.tier = new_tier
        settings.save()

        return Response({
            'message': f"سطح اشتراک فروشگاه از {old_tier} به {settings.tier} تغییر یافت.",
            'tier': settings.tier,
            'tier_display': settings.get_tier_display()
        })


class SubscriptionInvoiceListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission]

    def get(self, request):
        store = get_request_store(request)
        invoices = SubscriptionInvoice.objects.filter(store=store)
        serializer = SubscriptionInvoiceSerializer(invoices, many=True)
        return Response(serializer.data)

    def post(self, request):
        store = get_request_store(request)
        serializer = CreateInvoiceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        tier = serializer.validated_data['tier']
        billing_cycle = serializer.validated_data.get('billing_cycle', 'MONTHLY')

        from .services import SubscriptionPaymentService
        invoice = SubscriptionPaymentService.create_subscription_invoice(
            store=store,
            tier=tier,
            billing_cycle=billing_cycle
        )
        return Response(SubscriptionInvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


class SubscriptionInvoiceCheckoutView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission]

    def post(self, request, pk):
        store = get_request_store(request)
        try:
            invoice = SubscriptionInvoice.objects.get(id=pk, store=store)
        except (SubscriptionInvoice.DoesNotExist, ValueError):
            return Response({'error': 'صورتحساب یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CheckoutInvoiceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        callback_url = serializer.validated_data.get('callback_url') or request.build_absolute_uri('/api/v1/features/invoices/verify/')
        gateway_name = serializer.validated_data.get('gateway', 'zarinpal')

        from .services import SubscriptionPaymentService
        res = SubscriptionPaymentService.initiate_subscription_payment(
            invoice=invoice,
            store=store,
            callback_url=callback_url,
            gateway_name=gateway_name
        )

        if not res.get('success'):
            status_code = status.HTTP_400_BAD_REQUEST if res.get('status') in ['REQUIRES_GATEWAY_CONFIG', 'INVALID_AMOUNT'] else status.HTTP_502_BAD_GATEWAY
            return Response(res, status=status_code)

        return Response({
            'success': True,
            'invoice_id': str(invoice.id),
            'authority': res.get('authority'),
            'payment_url': res.get('payment_url'),
            'amount': invoice.amount
        }, status=status.HTTP_200_OK)


class SubscriptionInvoiceVerifyView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        return self._handle_verify(request)

    def post(self, request):
        return self._handle_verify(request)

    def _handle_verify(self, request):
        authority = (
            request.data.get('authority')
            or request.data.get('Authority')
            or request.query_params.get('Authority')
            or request.query_params.get('authority')
        )
        gateway_name = request.data.get('gateway', 'zarinpal')

        if not authority:
            return Response({'error': 'شناسه Authority درگاه ارسال نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        from .services import SubscriptionPaymentService
        success, invoice, message = SubscriptionPaymentService.verify_subscription_payment(
            authority=authority,
            gateway_name=gateway_name
        )

        if success:
            return Response({
                'success': True,
                'message': message,
                'tracking_code': invoice.gateway_tracking_code,
                'invoice': SubscriptionInvoiceSerializer(invoice).data
            }, status=status.HTTP_200_OK)
        else:
            return Response({
                'success': False,
                'error': message,
                'invoice': SubscriptionInvoiceSerializer(invoice).data if invoice else None
            }, status=status.HTTP_400_BAD_REQUEST)


class SubscriptionInvoiceManualApproveView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, pk):
        if not (request.user.is_staff or request.user.is_superuser):
            raise PermissionDenied("تنها مدیران ارشد سامانه مجاز به تأیید دستی صورتحساب اشتراک هستند.")

        serializer = ManualApproveInvoiceInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from .services import SubscriptionPaymentService
        try:
            invoice = SubscriptionPaymentService.admin_manual_override_invoice(
                invoice_id=pk,
                actor=request.user,
                reason=serializer.validated_data['reason'],
                tracking_code=serializer.validated_data.get('tracking_code', '')
            )
        except SubscriptionInvoice.DoesNotExist:
            return Response({'error': 'صورتحساب یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            'message': f"صورتحساب با موفقیت توسط مدیر سامانه تأیید شد و پلن فروشگاه ارتقا یافت.",
            'invoice': SubscriptionInvoiceSerializer(invoice).data
        }, status=status.HTTP_200_OK)


class SubscriptionInvoicePayView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission]

    def post(self, request, pk):
        store = get_request_store(request)
        try:
            invoice = SubscriptionInvoice.objects.get(id=pk, store=store)
        except (SubscriptionInvoice.DoesNotExist, ValueError):
            return Response({'error': 'صورتحساب یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if invoice.status == InvoiceStatus.PAID:
            return Response({'message': 'این صورتحساب قبلاً پرداخت شده است.'}, status=status.HTTP_200_OK)

        # Free tier invoices can be activated directly
        if invoice.amount == Decimal('0') or invoice.tier == SubscriptionTier.FREE:
            from .services import SubscriptionPaymentService
            invoice.status = InvoiceStatus.PAID
            invoice.paid_at = timezone.now()
            invoice.save()
            SubscriptionPaymentService.apply_paid_subscription_invoice(invoice)
            return Response({
                'message': 'پلن رایگان با موفقیت فعال شد.',
                'invoice': SubscriptionInvoiceSerializer(invoice).data
            })

        # Disallow arbitrary client string approvals for paid tiers!
        if request.user.is_staff or request.user.is_superuser:
            reason = request.data.get('reason')
            if not reason:
                return Response(
                    {'error': 'برای تأیید دستی صورتحساب‌های مالی توسط مدیر، ذکر پارامتر reason الزامی است.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            from .services import SubscriptionPaymentService
            invoice = SubscriptionPaymentService.admin_manual_override_invoice(
                invoice_id=pk,
                actor=request.user,
                reason=reason,
                tracking_code=request.data.get('tracking_code', '')
            )
            return Response({
                'message': f"صورتحساب توسط مدیر سامانه با موفقیت تأیید شد.",
                'invoice': SubscriptionInvoiceSerializer(invoice).data
            })

        return Response(
            {
                'error': 'امکان ثبت پرداخت ساختگی بدون استعلام درگاه بانکی وجود ندارد. لطفاً از طریق درگاه پرداخت آنلاین (/checkout/) پرداخت را انجام دهید.'
            },
            status=status.HTTP_400_BAD_REQUEST
        )



class IntegrationListView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get(self, request):
        store = get_request_store(request)
        integrations = IntegrationRegistry.get_store_integration_statuses(store)
        return Response(integrations)


class IntegrationConfigView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission]

    def post(self, request):
        store = get_request_store(request)
        serializer = IntegrationConfigInputSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        name = serializer.validated_data['name']
        new_state = serializer.validated_data['state']

        # Prevent users from manually setting status to CONNECTED without a successful live health check
        if new_state == IntegrationState.CONNECTED:
            adapter = IntegrationRegistry.get_adapter(name)
            if not adapter:
                return Response(
                    {'error': f"سرویس '{name}' در سامانه یافت نشد."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            health = adapter.health_check(store)
            if health.state != IntegrationState.CONNECTED:
                return Response(
                    {
                        'error': "امکان تغییر وضعیت به CONNECTED وجود ندارد؛ تست سلامت سرویس موفق نبود.",
                        'health_status': health.state,
                        'message': health.message
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )

        settings = FeatureService.get_or_create_settings(store)
        states = dict(settings.integration_states or {})
        states[name] = new_state
        settings.integration_states = states
        settings.save()

        return Response({
            'name': name,
            'state': new_state,
            'message': f"وضعیت اتصال سرویس '{name}' بروزرسانی شد."
        })
