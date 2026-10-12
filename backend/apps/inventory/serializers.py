from rest_framework import serializers
from .models import Warehouse, InventoryBalance, InventoryMovement

class WarehouseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Warehouse
        fields = ['id', 'name', 'code', 'address', 'is_default', 'is_active', 'created_at']
        read_only_fields = ['id', 'created_at']

    def create(self, validated_data):
        store = self.context['request'].store
        return Warehouse.objects.create(store=store, **validated_data)

class InventoryBalanceSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    variant_sku = serializers.CharField(source='variant.sku', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    product_name = serializers.CharField(source='variant.product.name', read_only=True)
    available = serializers.IntegerField(read_only=True)

    class Meta:
        model = InventoryBalance
        fields = [
            'id', 'warehouse', 'warehouse_name', 'variant', 'variant_sku',
            'variant_name', 'product_name', 'on_hand_quantity', 'reserved_quantity',
            'quarantined_quantity', 'incoming_quantity', 'available', 'reorder_point'
        ]
        read_only_fields = ['id', 'warehouse_name', 'variant_sku', 'variant_name', 'product_name', 'available']

class InventoryMovementSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    variant_sku = serializers.CharField(source='variant.sku', read_only=True)
    movement_type_display = serializers.CharField(source='get_movement_type_display', read_only=True)
    user_name = serializers.CharField(source='user.full_name', read_only=True)

    class Meta:
        model = InventoryMovement
        fields = [
            'id', 'warehouse', 'warehouse_name', 'variant', 'variant_sku',
            'movement_type', 'movement_type_display', 'quantity', 'balance_after',
            'reference', 'reason', 'user_name', 'created_at'
        ]
        read_only_fields = ['id', 'warehouse_name', 'variant_sku', 'movement_type_display', 'user_name', 'created_at']

class StockAdjustmentSerializer(serializers.Serializer):
    warehouse_id = serializers.UUIDField()
    variant_id = serializers.UUIDField()
    new_on_hand = serializers.IntegerField(min_value=0)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)
