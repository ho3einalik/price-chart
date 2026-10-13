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

class StockTransferSerializer(serializers.Serializer):
    source_warehouse_id = serializers.UUIDField()
    dest_warehouse_id = serializers.UUIDField()
    variant_id = serializers.UUIDField()
    quantity = serializers.IntegerField(min_value=1)
    reason = serializers.CharField(max_length=255, required=False, allow_blank=True)


class StockCycleCountItemSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source='variant.sku', read_only=True)
    variant_name = serializers.CharField(source='variant.name', read_only=True)
    product_name = serializers.CharField(source='variant.product.name', read_only=True)
    variance = serializers.IntegerField(read_only=True)

    class Meta:
        from .models import StockCycleCountItem
        model = StockCycleCountItem
        fields = [
            'id', 'variant', 'variant_sku', 'variant_name', 'product_name',
            'system_quantity', 'counted_quantity', 'variance', 'is_reconciled', 'notes'
        ]
        read_only_fields = ['id', 'variant_sku', 'variant_name', 'product_name', 'variance', 'is_reconciled']


class StockCycleCountSerializer(serializers.ModelSerializer):
    warehouse_name = serializers.CharField(source='warehouse.name', read_only=True)
    counted_by_name = serializers.CharField(source='counted_by.full_name', read_only=True)
    reconciled_by_name = serializers.CharField(source='reconciled_by.full_name', read_only=True)
    status_display = serializers.CharField(source='get_status_display', read_only=True)
    items = StockCycleCountItemSerializer(many=True, read_only=True)
    total_items = serializers.SerializerMethodField()
    uncounted_items = serializers.SerializerMethodField()
    variance_items = serializers.SerializerMethodField()

    class Meta:
        from .models import StockCycleCount
        model = StockCycleCount
        fields = [
            'id', 'warehouse', 'warehouse_name', 'count_number', 'status', 'status_display',
            'started_at', 'completed_at', 'counted_by', 'counted_by_name',
            'reconciled_by', 'reconciled_by_name', 'notes', 'total_items',
            'uncounted_items', 'variance_items', 'items', 'created_at'
        ]
        read_only_fields = ['id', 'count_number', 'status', 'started_at', 'completed_at', 'created_at']

    def get_total_items(self, obj):
        return obj.items.count()

    def get_uncounted_items(self, obj):
        return obj.items.filter(counted_quantity__isnull=True).count()

    def get_variance_items(self, obj):
        return [i for i in obj.items.all() if i.counted_quantity is not None and i.variance != 0].__len__()


class StockCycleCountCreateSerializer(serializers.Serializer):
    warehouse_id = serializers.UUIDField()
    variant_ids = serializers.ListField(child=serializers.UUIDField(), required=False)
    notes = serializers.CharField(max_length=500, required=False, allow_blank=True)


class CountItemResultSerializer(serializers.Serializer):
    variant_id = serializers.UUIDField()
    counted_quantity = serializers.IntegerField(min_value=0)
    notes = serializers.CharField(max_length=255, required=False, allow_blank=True)


class RecordCountResultsSerializer(serializers.Serializer):
    items = CountItemResultSerializer(many=True)

