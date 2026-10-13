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
from .models import SubscriptionTier

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

        # In production, upgrading to a higher tier requires superuser, platform staff, or payment confirmation
        payment_reference = serializer.validated_data.get('payment_reference')
        if new_rank > current_rank and not (request.user.is_superuser or request.user.is_staff or django_settings.DEBUG or payment_reference):
            raise PermissionDenied("ارتقای پلن اشتراک مستلزم تسویه فاکتور اشتراک یا تأیید مدیر سامانه است.")

        settings.tier = new_tier
        settings.save()

        return Response({
            'message': f"سطح اشتراک فروشگاه از {old_tier} به {settings.tier} تغییر یافت.",
            'tier': settings.tier,
            'tier_display': settings.get_tier_display()
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
