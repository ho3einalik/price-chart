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

        prices = {
            SubscriptionTier.FREE: Decimal('0'),
            SubscriptionTier.STARTER: Decimal('290000'),
            SubscriptionTier.PRO: Decimal('590000'),
            SubscriptionTier.ENTERPRISE: Decimal('1490000'),
        }
        amount = prices.get(tier, Decimal('0'))

        invoice = SubscriptionInvoice.objects.create(
            store=store,
            tier=tier,
            amount=amount,
            status=InvoiceStatus.PAID if amount == 0 else InvoiceStatus.PENDING,
            payment_reference=f"INV-REF-{uuid.uuid4().hex[:12].upper()}"
        )
        return Response(SubscriptionInvoiceSerializer(invoice).data, status=status.HTTP_201_CREATED)


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

        tracking_code = request.data.get('tracking_code', f"TRK-{uuid.uuid4().hex[:8].upper()}")
        invoice.status = InvoiceStatus.PAID
        invoice.paid_at = timezone.now()
        invoice.gateway_tracking_code = tracking_code
        invoice.save()

        # Automatically upgrade store feature settings tier
        settings = FeatureService.get_or_create_settings(store)
        settings.tier = invoice.tier
        settings.save()

        return Response({
            'message': f"صورتحساب با موفقیت پرداخت شد و پلن فروشگاه به {invoice.get_tier_display()} ارتقا یافت.",
            'invoice': SubscriptionInvoiceSerializer(invoice).data
        })


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
