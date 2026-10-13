from rest_framework import serializers
from decimal import Decimal
from .models import Order, OrderItem, Customer, OrderChannel, OrderStatus, PaymentStatus, FulfillmentStatus
from apps.catalog.models import ProductVariant
from apps.inventory.models import Warehouse

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['id', 'full_name', 'phone_number', 'email', 'province', 'city', 'postal_code', 'address_line', 'marketing_opt_in', 'created_at']
        read_only_fields = ['id', 'created_at']

class OrderItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = [
            'id', 'variant', 'variant_sku', 'variant_name',
            'quantity', 'unit_price', 'cost_price_snapshot',
            'unit_discount', 'total_price'
        ]
        read_only_fields = ['id', 'variant_sku', 'variant_name', 'cost_price_snapshot', 'total_price']

class OrderDetailSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    items = OrderItemSerializer(many=True, read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    order_status_display = serializers.CharField(source='get_order_status_display', read_only=True)
    payment_status_display = serializers.CharField(source='get_payment_status_display', read_only=True)
    fulfillment_status_display = serializers.CharField(source='get_fulfillment_status_display', read_only=True)
    channel_display = serializers.CharField(source='get_channel_display', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'order_number', 'channel', 'channel_display',
            'customer', 'warehouse', 'warehouse_name',
            'order_status', 'order_status_display',
            'payment_status', 'payment_status_display',
            'fulfillment_status', 'fulfillment_status_display',
            'currency', 'total_items_price', 'discount_amount',
            'shipping_cost', 'tax_amount', 'grand_total',
            'utm_source', 'utm_medium', 'utm_campaign',
            'notes', 'items', 'created_at'
        ]
        read_only_fields = ['id', 'order_number', 'created_at']

class CreateOrderItemInputSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    unit_price = serializers.DecimalField(max_digits=14, decimal_places=0, required=False)
    unit_discount = serializers.DecimalField(max_digits=14, decimal_places=0, required=False, default=Decimal('0'))

class OrderCreateSerializer(serializers.Serializer):
    customer_name = serializers.CharField(max_length=150)
    customer_phone = serializers.CharField(max_length=30)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    province = serializers.CharField(max_length=100, required=False, allow_blank=True)
    address_line = serializers.CharField(required=False, allow_blank=True)
    marketing_opt_in = serializers.BooleanField(required=False, default=True)
    warehouse_id = serializers.UUIDField(required=False)
    channel = serializers.ChoiceField(choices=OrderChannel.choices, default=OrderChannel.MANUAL)
    shipping_cost = serializers.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'))
    discount_amount = serializers.DecimalField(max_digits=14, decimal_places=0, default=Decimal('0'))
    utm_source = serializers.CharField(max_length=100, required=False, allow_blank=True)
    utm_medium = serializers.CharField(max_length=100, required=False, allow_blank=True)
    utm_campaign = serializers.CharField(max_length=150, required=False, allow_blank=True)
    notes = serializers.CharField(required=False, allow_blank=True)
    items = CreateOrderItemInputSerializer(many=True)

class OrderCancelSerializer(serializers.Serializer):
    reason = serializers.CharField(required=False, allow_blank=True)

class OrderFulfillSerializer(serializers.Serializer):
    tracking_number = serializers.CharField(max_length=100, required=False, allow_blank=True)
    shipping_cost = serializers.DecimalField(max_digits=14, decimal_places=0, required=False)
