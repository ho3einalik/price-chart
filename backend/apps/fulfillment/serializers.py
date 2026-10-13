from rest_framework import serializers
from .models import Shipment, ShipmentTrackingEvent
from .services import get_carrier_adapter

class ShipmentTrackingEventSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = ShipmentTrackingEvent
        fields = [
            'id', 'status', 'status_display', 'location', 'description',
            'source', 'occurred_at', 'created_at'
        ]


class ShipmentSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='order.customer.full_name', read_only=True)
    customer_phone = serializers.CharField(source='order.customer.phone_number', read_only=True)
    destination_city = serializers.CharField(source='order.customer.city', read_only=True)
    destination_address = serializers.CharField(source='order.customer.address_line', read_only=True)
    carrier_display = serializers.CharField(source='get_carrier_display', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    tracking_url = serializers.SerializerMethodField()
    tracking_events = ShipmentTrackingEventSerializer(many=True, read_only=True)

    class Meta:
        model = Shipment
        fields = [
            'id', 'order', 'order_number', 'customer_name', 'customer_phone',
            'destination_city', 'destination_address', 'tracking_number',
            'carrier', 'carrier_display', 'status', 'status_display',
            'shipping_cost', 'shipping_label_url', 'failed_reason', 'notes',
            'tracking_url', 'tracking_events', 'shipped_at', 'delivered_at'
        ]
        read_only_fields = [
            'id', 'order_number', 'customer_name', 'customer_phone',
            'destination_city', 'destination_address', 'carrier_display',
            'status_display', 'tracking_url', 'shipped_at'
        ]

    def get_tracking_url(self, obj):
        adapter = get_carrier_adapter(obj.carrier)
        return adapter.get_tracking_url(obj.tracking_number)
