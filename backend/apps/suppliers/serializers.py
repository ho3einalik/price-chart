from rest_framework import serializers
from .models import Supplier, PurchaseOrder, PurchaseOrderItem
from apps.catalog.serializers import ProductVariantSerializer

class SupplierSerializer(serializers.ModelSerializer):
    class Meta:
        model = Supplier
        fields = [
            'id', 'name', 'contact_name', 'phone_number', 'email',
            'address', 'tax_id', 'lead_time_days', 'payment_terms',
            'notes', 'is_active', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class PurchaseOrderItemSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source='variant.sku', read_only=True)
    variant_name = serializers.CharField(source='variant.product.name', read_only=True)
    remaining_quantity = serializers.IntegerField(read_only=True)
    is_fully_received = serializers.BooleanField(read_only=True)

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'id', 'variant', 'variant_sku', 'variant_name',
            'quantity_ordered', 'quantity_received', 'remaining_quantity',
            'is_fully_received', 'unit_cost', 'total_cost'
        ]
        read_only_fields = ['id', 'total_cost', 'quantity_received']


class PurchaseOrderSerializer(serializers.ModelSerializer):
    supplier_name = serializers.CharField(source='supplier.name', read_only=True)
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    items = PurchaseOrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = PurchaseOrder
        fields = [
            'id', 'po_number', 'supplier', 'supplier_name',
            'warehouse', 'warehouse_name', 'status', 'status_display',
            'currency', 'total_amount', 'expected_delivery_date',
            'notes', 'items', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'po_number', 'total_amount', 'status', 'created_at', 'updated_at']
