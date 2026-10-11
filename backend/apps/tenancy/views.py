from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from .models import Business, Store, StoreMembership, Role
from .serializers import BusinessSerializer, StoreSerializer, StoreMembershipSerializer
from .permissions import IsStoreMemberPermission, IsStoreAdminOrOwnerPermission

class BusinessViewSet(viewsets.ModelViewSet):
    serializer_class = BusinessSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Business.objects.filter(owner=self.request.user)

    def perform_create(self, serializer):
        serializer.save(owner=self.request.user)

class StoreViewSet(viewsets.ModelViewSet):
    serializer_class = StoreSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Store.objects.filter(
            memberships__user=self.request.user,
            memberships__is_active=True
        ).distinct()

    def perform_create(self, serializer):
        store = serializer.save()
        StoreMembership.objects.create(
            store=store,
            user=self.request.user,
            role=Role.OWNER,
            is_active=True
        )

class StoreMembershipViewSet(viewsets.ModelViewSet):
    serializer_class = StoreMembershipSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreAdminOrOwnerPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return StoreMembership.objects.none()
        return StoreMembership.objects.filter(store=store)

    def perform_create(self, serializer):
        store = getattr(self.request, 'store', None)
        serializer.save(store=store)
