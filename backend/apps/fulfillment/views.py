from rest_framework import viewsets, filters, status
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from apps.tenancy.permissions import IsStoreMemberPermission, TenantFilterBackend
from .models import Shipment
from .serializers import ShipmentSerializer

class ShipmentViewSet(viewsets.ModelViewSet):
    serializer_class = ShipmentSerializer
    permission_classes = [IsStoreMemberPermission]
    filter_backends = [TenantFilterBackend, DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['status', 'carrier']
    search_fields = ['tracking_number', 'order__order_number', 'order__customer__full_name', 'order__customer__phone_number']
    ordering_fields = ['shipped_at']
    queryset = Shipment.objects.all().select_related('order', 'order__customer')

    @action(detail=True, methods=['get'], url_path='packing-slip')
    def packing_slip(self, request, pk=None):
        shipment = self.get_object()
        order = shipment.order
        items_data = [
            {
                'sku': item.variant_sku,
                'name': item.variant_name,
                'quantity': item.quantity,
                'unit_price': int(item.unit_price),
                'total_price': int(item.total_price),
            }
            for item in order.items.all()
        ]
        return Response({
            'shipment_id': str(shipment.id),
            'tracking_number': shipment.tracking_number,
            'carrier': shipment.get_carrier_display(),
            'order_number': order.order_number,
            'order_date': order.created_at.strftime('%Y/%m/%d %H:%M'),
            'store_name': order.store.name,
            'currency': order.currency,
            'customer': {
                'name': order.customer.full_name,
                'phone': order.customer.phone_number,
                'city': order.customer.city,
                'province': order.customer.province,
                'address': order.customer.address_line,
                'postal_code': order.customer.postal_code,
            },
            'items': items_data,
            'total_items_price': int(order.total_items_price),
            'shipping_cost': int(order.shipping_cost),
            'discount_amount': int(order.discount_amount),
            'grand_total': int(order.grand_total),
            'notes': order.notes,
        })
