from rest_framework import serializers
from .models import Shipment

class ShipmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.customer.full_name', read_only=True)
    customer_phone = serializers.CharField(source='order.customer.phone_number', read_only=True)
    destination_city = serializers.CharField(source='order.customer.city', read_only=True)
    destination_address = serializers.CharField(source='order.customer.address_line', read_only=True)
    carrier_display = serializers.CharField(source='get_carrier_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = Shipment
        fields = [
            'id', 'order', 'order_number', 'customer_name', 'customer_phone',
            'destination_city', 'destination_address', 'tracking_number',
            'carrier', 'carrier_display', 'status', 'status_display',
            'shipping_cost', 'shipped_at', 'delivered_at'
        ]
        read_only_fields = [
            'id', 'order_number', 'customer_name', 'customer_phone',
            'destination_city', 'destination_address', 'carrier_display',
            'status_display', 'shipped_at'
        ]
