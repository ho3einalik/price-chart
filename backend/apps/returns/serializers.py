from rest_framework import serializers
from .models import ReturnRequest, ReturnItem

class ReturnItemSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source='variant.sku', read_only=True)
    variant_name = serializers.CharField(source='variant.product.name', read_only=True)
    reason_display = serializers.CharField(source='get_reason_display', read_only=True)
    condition_display = serializers.CharField(source='get_condition_display', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = ReturnItem
        fields = [
            'id', 'order_item', 'variant', 'variant_sku', 'variant_name',
            'quantity', 'reason', 'reason_display', 'condition',
            'condition_display', 'action', 'action_display',
            'is_inspected', 'inspection_notes'
        ]
        read_only_fields = ['id', 'variant_sku', 'variant_name', 'reason_display', 'condition_display', 'action_display']


class ReturnRequestSerializer(serializers.ModelSerializer):
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone_number', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    refund_status_display = serializers.CharField(source='get_refund_status_display', read_only=True)
    exchange_variant_sku = serializers.CharField(source='exchange_variant.sku', read_only=True)
    items = ReturnItemSerializer(many=True, read_only=True)

    class Meta:
        model = ReturnRequest
        fields = [
            'id', 'rma_number', 'order', 'order_number', 'customer',
            'customer_name', 'customer_phone', 'status', 'status_display',
            'refund_status', 'refund_status_display', 'refund_amount',
            'customer_notes', 'staff_notes',
            'is_exchange', 'exchange_variant', 'exchange_variant_sku',
            'exchange_quantity', 'exchange_price_difference',
            'items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'rma_number', 'status', 'refund_amount', 'exchange_variant_sku', 'created_at', 'updated_at']

