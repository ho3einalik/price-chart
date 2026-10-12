from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.tenancy.permissions import IsStoreMemberPermission, TenantFilterBackend
from apps.inventory.models import Warehouse
from .models import Order, Customer
from .serializers import (
    OrderDetailSerializer, OrderCreateSerializer,
    OrderCancelSerializer, OrderFulfillSerializer, CustomerSerializer
)
from .services import create_order, cancel_order, fulfill_order, import_orders_from_csv

class CustomerViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = CustomerSerializer
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, filters.SearchFilter]
    search_fields = ['full_name', 'phone_number', 'city']
    queryset = Customer.objects.all()

class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['order_status', 'payment_status', 'fulfillment_status', 'channel']
    search_fields = ['order_number', 'customer__full_name', 'customer__phone_number', 'items__variant_sku']
    ordering_fields = ['created_at', 'grand_total']
    queryset = Order.objects.all().select_related('customer', 'warehouse').prefetch_related('items')

    def get_serializer_class(self):
        if self.action == 'create':
            return OrderCreateSerializer
        return OrderDetailSerializer

    def create(self, request, *args, **kwargs):
        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        store = request.store
        data = serializer.validated_data

        warehouse_id = data.get('warehouse_id')
        if warehouse_id:
            warehouse = Warehouse.objects.filter(id=warehouse_id, store=store).first()
        else:
            warehouse = Warehouse.objects.filter(store=store, is_active=True).first()

        if not warehouse:
            warehouse = Warehouse.objects.create(store=store, name="انبار پیش‌فرض", is_default=True)

        try:
            order = create_order(
                store=store,
                customer_data={
                    'full_name': data['customer_name'],
                    'phone_number': data['customer_phone'],
                    'city': data.get('city', ''),
                    'province': data.get('province', ''),
                    'address_line': data.get('address_line', ''),
                },
                items_data=data['items'],
                warehouse=warehouse,
                channel=data.get('channel'),
                shipping_cost=data.get('shipping_cost', 0),
                discount_amount=data.get('discount_amount', 0),
                notes=data.get('notes', ''),
                user=request.user
            )
            return Response(OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        order = self.get_object()
        serializer = OrderCancelSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            cancelled_order = cancel_order(
                order=order,
                reason=serializer.validated_data.get('reason', ''),
                user=request.user
            )
            return Response(OrderDetailSerializer(cancelled_order).data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def fulfill(self, request, pk=None):
        order = self.get_object()
        serializer = OrderFulfillSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            fulfilled_order, shipment = fulfill_order(
                order=order,
                tracking_number=serializer.validated_data.get('tracking_number', ''),
                shipping_cost=serializer.validated_data.get('shipping_cost'),
                user=request.user
            )
            return Response({
                'order': OrderDetailSerializer(fulfilled_order).data,
                'tracking_number': shipment.tracking_number,
            })
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=False, methods=['post'], url_path='import-csv')
    def import_csv(self, request):
        uploaded_file = request.FILES.get('file')
        if not uploaded_file:
            return Response({'error': 'فایل CSV الزامی است.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            result = import_orders_from_csv(
                store=request.store,
                file_content=uploaded_file.read(),
                user=request.user
            )
            return Response(result, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
