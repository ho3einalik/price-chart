from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from .models import Supplier, PurchaseOrder
from .serializers import SupplierSerializer, PurchaseOrderSerializer
from .services import (
    create_purchase_order,
    approve_purchase_order,
    mark_purchase_order_sent,
    receive_po_goods
)
from apps.catalog.models import ProductVariant
from apps.inventory.models import Warehouse
from apps.tenancy.permissions import IsStoreMemberPermission

class SupplierViewSet(viewsets.ModelViewSet):
    serializer_class = SupplierSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return Supplier.objects.none()
        qs = Supplier.objects.filter(store=store)
        search = self.request.query_params.get('search')
        if search:
            qs = qs.filter(name__icontains=search)
        return qs

    def perform_create(self, serializer):
        serializer.save(store=self.request.store)


class PurchaseOrderViewSet(viewsets.ModelViewSet):
    serializer_class = PurchaseOrderSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return PurchaseOrder.objects.none()
        qs = PurchaseOrder.objects.filter(store=store).select_related('supplier', 'warehouse').prefetch_related('items__variant__product')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def create(self, request, *args, **kwargs):
        store = request.store
        data = request.data
        supplier_id = data.get('supplier')
        warehouse_id = data.get('warehouse')
        items = data.get('items', [])
        notes = data.get('notes', '')
        delivery_date = data.get('expected_delivery_date')

        if not supplier_id or not warehouse_id:
            return Response({'error': 'انتخاب تامین‌کننده و انبار مقصد الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            supplier = Supplier.objects.get(id=supplier_id, store=store)
            warehouse = Warehouse.objects.get(id=warehouse_id, store=store)
        except (Supplier.DoesNotExist, Warehouse.DoesNotExist):
            return Response({'error': 'تامین‌کننده یا انبار یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        formatted_items = []
        for item in items:
            try:
                variant = ProductVariant.objects.get(id=item['variant_id'], store=store)
                formatted_items.append({
                    'variant': variant,
                    'quantity_ordered': item['quantity_ordered'],
                    'unit_cost': item['unit_cost']
                })
            except ProductVariant.DoesNotExist:
                return Response({'error': f"تنوع کالای {item.get('variant_id')} یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        try:
            po = create_purchase_order(
                store=store,
                supplier=supplier,
                warehouse=warehouse,
                items_data=formatted_items,
                user=request.user,
                notes=notes,
                expected_delivery_date=delivery_date
            )
            return Response(PurchaseOrderSerializer(po).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        po = self.get_object()
        try:
            po = approve_purchase_order(po, user=request.user)
            return Response(PurchaseOrderSerializer(po).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='send')
    def send_order(self, request, pk=None):
        po = self.get_object()
        try:
            po = mark_purchase_order_sent(po, user=request.user)
            return Response(PurchaseOrderSerializer(po).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='receive-goods')
    def receive_goods(self, request, pk=None):
        po = self.get_object()
        receipts = request.data.get('receipts', [])
        if not receipts:
            return Response({'error': 'لیست اقلام دریافتی جهت رسید انبار ارسال نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            po = receive_po_goods(po, receipts, user=request.user)
            return Response({
                'message': 'کالاها با موفقیت در انبار رسید شدند و موجودی فیزیکی به‌روزرسانی شد.',
                'purchase_order': PurchaseOrderSerializer(po).data
            })
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
