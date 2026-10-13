from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django.core.exceptions import ValidationError
from .models import ReturnRequest, ReturnItem, RefundStatus
from .serializers import ReturnRequestSerializer
from .services import (
    create_return_request,
    approve_return_request,
    inspect_and_process_return
)
from apps.orders.models import Order, OrderItem
from apps.inventory.models import Warehouse
from apps.tenancy.permissions import IsStoreMemberPermission, Role, user_has_store_permission

class ReturnRequestViewSet(viewsets.ModelViewSet):
    serializer_class = ReturnRequestSerializer
    permission_classes = [permissions.IsAuthenticated, IsStoreMemberPermission]

    def get_queryset(self):
        store = getattr(self.request, 'store', None)
        if not store:
            return ReturnRequest.objects.none()
        qs = ReturnRequest.objects.filter(store=store).select_related('order', 'customer').prefetch_related('items__variant__product')
        status_filter = self.request.query_params.get('status')
        if status_filter:
            qs = qs.filter(status=status_filter)
        return qs

    def create(self, request, *args, **kwargs):
        store = request.store
        data = request.data
        order_id = data.get('order_id')
        items = data.get('items', [])
        notes = data.get('customer_notes', '')

        if not order_id:
            return Response({'error': 'شناسه سفارش الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.get(id=order_id, store=store)
        except Order.DoesNotExist:
            return Response({'error': 'سفارش مورد نظر یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        formatted_items = []
        for item in items:
            try:
                order_item = OrderItem.objects.get(id=item['order_item_id'], order=order)
                formatted_items.append({
                    'order_item': order_item,
                    'quantity': item.get('quantity', 1),
                    'reason': item.get('reason', 'CUSTOMER_REMORSE')
                })
            except OrderItem.DoesNotExist:
                return Response({'error': f"ردیف سفارش {item.get('order_item_id')} یافت نشد."}, status=status.HTTP_404_NOT_FOUND)

        is_exchange = bool(data.get('is_exchange', False))
        exchange_variant = None
        exchange_quantity = int(data.get('exchange_quantity', 0))
        exchange_price_difference = Decimal(str(data.get('exchange_price_difference', 0)))

        exchange_variant_id = data.get('exchange_variant_id') or data.get('exchange_variant')
        if is_exchange and exchange_variant_id:
            from apps.catalog.models import ProductVariant
            try:
                exchange_variant = ProductVariant.objects.get(id=exchange_variant_id, store=store)
            except ProductVariant.DoesNotExist:
                return Response({'error': 'کالای انتخابی جهت تعویض یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        try:
            rma = create_return_request(
                order=order,
                items_data=formatted_items,
                customer_notes=notes,
                user=request.user,
                is_exchange=is_exchange,
                exchange_variant=exchange_variant,
                exchange_quantity=exchange_quantity,
                exchange_price_difference=exchange_price_difference
            )
            return Response(ReturnRequestSerializer(rma).data, status=status.HTTP_201_CREATED)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        membership = getattr(request, 'membership', None)
        if not (request.user.is_superuser or request.user.is_staff or (membership and (membership.role in [Role.OWNER, Role.ADMIN, Role.BUSINESS_MANAGER, Role.OPS_MANAGER] or user_has_store_permission(membership, 'returns.approve')))):
            return Response({'error': 'شما مجوز تأیید درخواست‌های مرجوعی را ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        rma = self.get_object()
        staff_notes = request.data.get('staff_notes', '')
        try:
            rma = approve_return_request(rma, user=request.user, staff_notes=staff_notes)
            return Response(ReturnRequestSerializer(rma).data)
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], url_path='inspect-and-process')
    def inspect_and_process(self, request, pk=None):
        membership = getattr(request, 'membership', None)
        if not (request.user.is_superuser or request.user.is_staff or (membership and (membership.role in [Role.OWNER, Role.ADMIN, Role.BUSINESS_MANAGER, Role.OPS_MANAGER, Role.INVENTORY_MANAGER] or user_has_store_permission(membership, 'returns.process')))):
            return Response({'error': 'شما مجوز بازرسی و پردازش انبارداری مرجوعی را ندارید.'}, status=status.HTTP_403_FORBIDDEN)

        rma = self.get_object()
        data = request.data
        inspection_items = data.get('inspection_items', [])
        warehouse_id = data.get('warehouse_id')
        refund_status = data.get('refund_status', RefundStatus.REFUNDED)
        staff_notes = data.get('staff_notes', '')

        if not warehouse_id:
            # fallback to default warehouse
            warehouse = Warehouse.objects.filter(store=request.store, is_default=True).first()
            if not warehouse:
                warehouse = Warehouse.objects.filter(store=request.store).first()
        else:
            try:
                warehouse = Warehouse.objects.get(id=warehouse_id, store=request.store)
            except Warehouse.DoesNotExist:
                return Response({'error': 'انبار مقصد انتخابی یافت نشد.'}, status=status.HTTP_404_NOT_FOUND)

        if not warehouse:
            return Response({'error': 'هیچ انباری برای دریافت مرجوعی تعریف نشده است.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            rma = inspect_and_process_return(
                rma=rma,
                inspection_items_data=inspection_items,
                warehouse=warehouse,
                user=request.user,
                refund_status=refund_status,
                staff_notes=staff_notes
            )
            return Response({
                'message': 'مرجوعی کارشناسی شد و اقلام به گردش انبار اضافه شدند.',
                'return_request': ReturnRequestSerializer(rma).data
            })
        except ValidationError as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
