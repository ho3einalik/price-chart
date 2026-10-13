from rest_framework import viewsets, filters, status
from rest_framework.views import APIView
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.db.models import F
from apps.tenancy.permissions import IsStoreMemberPermission, TenantFilterBackend, Role, user_has_store_permission
from apps.catalog.models import ProductVariant
from .models import Warehouse, InventoryBalance, InventoryMovement
from .serializers import (
    WarehouseSerializer, InventoryBalanceSerializer,
    InventoryMovementSerializer, StockAdjustmentSerializer, StockTransferSerializer
)
from .services import adjust_stock, transfer_stock

class WarehouseViewSet(viewsets.ModelViewSet):
    serializer_class = WarehouseSerializer
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend]
    queryset = Warehouse.objects.all()

class InventoryBalanceViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventoryBalanceSerializer
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['warehouse']
    search_fields = ['variant__sku', 'variant__name', 'variant__product__name']
    queryset = InventoryBalance.objects.all().select_related('warehouse', 'variant', 'variant__product')

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get('low_stock') == 'true':
            qs = qs.filter(on_hand_quantity__lte=F('reorder_point') + F('reserved_quantity'))
        return qs

class InventoryMovementViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = InventoryMovementSerializer
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['warehouse', 'movement_type', 'variant']
    search_fields = ['variant__sku', 'reference', 'reason']
    queryset = InventoryMovement.objects.all().select_related('warehouse', 'variant', 'user')

class StockAdjustmentAPIView(APIView):
    permission_classes = [IsStoreMemberPermission]

    def post(self, request):
        membership = getattr(request, 'membership', None)
        if not (request.user.is_superuser or request.user.is_staff or (membership and (membership.role in [Role.OWNER, Role.ADMIN, Role.BUSINESS_MANAGER, Role.OPS_MANAGER, Role.INVENTORY_MANAGER] or user_has_store_permission(membership, 'inventory.adjust')))):
            return Response({'error': 'شما مجوز تعدیل موجودی انبار را ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = StockAdjustmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = request.store
        data = serializer.validated_data

        try:
            warehouse = Warehouse.objects.get(id=data['warehouse_id'], store=store)
            variant = ProductVariant.objects.get(id=data['variant_id'], store=store)
        except (Warehouse.DoesNotExist, ProductVariant.DoesNotExist):
            return Response({'error': 'انبار یا تنوع کالا یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        balance = adjust_stock(
            store=store,
            warehouse=warehouse,
            variant=variant,
            new_on_hand=data['new_on_hand'],
            reason=data.get('reason', ''),
            user=request.user
        )
        return Response(InventoryBalanceSerializer(balance).data, status=status.HTTP_200_OK)

class StockTransferAPIView(APIView):
    permission_classes = [IsStoreMemberPermission]

    def post(self, request):
        membership = getattr(request, 'membership', None)
        if not (request.user.is_superuser or request.user.is_staff or (membership and (membership.role in [Role.OWNER, Role.ADMIN, Role.OPS_MANAGER, Role.INVENTORY_MANAGER] or user_has_store_permission(membership, 'inventory.transfer')))):
            return Response({'error': 'شما مجوز انتقال موجودی بین انبارها را ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        serializer = StockTransferSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = request.store
        data = serializer.validated_data

        if data['source_warehouse_id'] == data['dest_warehouse_id']:
            return Response({'error': 'انبار مبدأ و مقصد نمی‌توانند یکسان باشند.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            source_warehouse = Warehouse.objects.get(id=data['source_warehouse_id'], store=store)
            dest_warehouse = Warehouse.objects.get(id=data['dest_warehouse_id'], store=store)
            variant = ProductVariant.objects.get(id=data['variant_id'], store=store)
        except (Warehouse.DoesNotExist, ProductVariant.DoesNotExist):
            return Response({'error': 'انبار یا تنوع کالا یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            source_bal, dest_bal = transfer_stock(
                store=store,
                source_warehouse=source_warehouse,
                dest_warehouse=dest_warehouse,
                variant=variant,
                quantity=data['quantity'],
                reason=data.get('reason', ''),
                user=request.user
            )
            return Response({
                'message': 'انتقال موجودی بین انبارها با موفقیت انجام شد.',
                'source_balance': InventoryBalanceSerializer(source_bal).data,
                'dest_balance': InventoryBalanceSerializer(dest_bal).data,
            }, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

class ReorderSuggestionsAPIView(APIView):
    permission_classes = [IsStoreMemberPermission]

    def get(self, request):
        store = request.store
        low_stock_balances = InventoryBalance.objects.filter(
            store=store,
            on_hand_quantity__lte=F('reorder_point') + F('reserved_quantity')
        ).select_related('warehouse', 'variant', 'variant__product')

        suggestions = []
        for b in low_stock_balances:
            suggested_order_qty = max(20, (b.reorder_point * 3) - b.available)
            suggestions.append({
                'variant_id': str(b.variant.id),
                'variant_name': b.variant.name,
                'product_name': b.variant.product.name,
                'sku': b.variant.sku,
                'warehouse_name': b.warehouse.name,
                'current_on_hand': b.on_hand_quantity,
                'available': b.available,
                'reorder_point': b.reorder_point,
                'suggested_quantity': suggested_order_qty,
                'estimated_cost': int(b.variant.cost_price * suggested_order_qty),
            })
        return Response(suggestions)
