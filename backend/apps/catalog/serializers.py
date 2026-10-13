from rest_framework import serializers
from django.db import transaction
from django.utils.text import slugify
from .models import Category, Product, ProductVariant, ProductImage

class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ['id', 'name', 'slug', 'parent', 'created_at']
        read_only_fields = ['id', 'created_at']

    def validate_parent(self, value):
        if value:
            store = getattr(self.context.get('request'), 'store', None)
            if store and value.store_id != store.id:
                raise serializers.ValidationError("دسته‌بندی والد باید متعلق به همین فروشگاه باشد.")
        return value

    def create(self, validated_data):
        store = self.context['request'].store
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data['name'], allow_unicode=True) or validated_data['name']
        return Category.objects.create(store=store, **validated_data)

class ProductVariantSerializer(serializers.ModelSerializer):
    total_on_hand = serializers.SerializerMethodField()
    total_available = serializers.SerializerMethodField()

    class Meta:
        model = ProductVariant
        fields = [
            'id', 'product', 'name', 'sku', 'barcode',
            'cost_price', 'retail_price', 'wholesale_price',
            'weight_grams', 'is_active', 'total_on_hand', 'total_available'
        ]
        read_only_fields = ['id', 'product', 'total_on_hand', 'total_available']

    def get_total_on_hand(self, obj):
        from apps.inventory.models import InventoryBalance
        from django.db.models import Sum
        total = InventoryBalance.objects.filter(variant=obj).aggregate(s=Sum('on_hand_quantity'))['s']
        return total or 0

    def get_total_available(self, obj):
        from apps.inventory.models import InventoryBalance
        from django.db.models import Sum, F
        balances = InventoryBalance.objects.filter(variant=obj)
        total = sum(b.available for b in balances)
        return total

class ProductImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = ProductImage
        fields = ['id', 'image_url', 'is_primary', 'sort_order']

class ProductDetailSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    variants = ProductVariantSerializer(many=True, read_only=True)
    images = ProductImageSerializer(many=True, read_only=True)

    class Meta:
        model = Product
        fields = [
            'id', 'name', 'slug', 'category', 'category_name',
            'brand', 'description', 'status', 'variants', 'images', 'created_at'
        ]
        read_only_fields = ['id', 'category_name', 'created_at']

class ProductCreateUpdateSerializer(serializers.ModelSerializer):
    variants_data = serializers.ListField(child=serializers.DictField(), write_only=True, required=False)

    class Meta:
        model = Product
        fields = ['id', 'name', 'slug', 'category', 'brand', 'description', 'status', 'variants_data']

    def validate_category(self, value):
        if value:
            store = getattr(self.context.get('request'), 'store', None)
            if store and value.store_id != store.id:
                raise serializers.ValidationError("دسته‌بندی انتخابی باید متعلق به همین فروشگاه باشد.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        variants_data = validated_data.pop('variants_data', [])
        store = self.context['request'].store
        if not validated_data.get('slug'):
            validated_data['slug'] = slugify(validated_data['name'], allow_unicode=True) or validated_data['name']
        product = Product.objects.create(store=store, **validated_data)

        if not variants_data:
            # Create a default variant if none specified
            ProductVariant.objects.create(
                store=store,
                product=product,
                name="تنوع پیش‌فرض",
                sku=f"SKU-{str(product.id)[:8].upper()}",
                retail_price=0,
                cost_price=0
            )
        else:
            for v_data in variants_data:
                ProductVariant.objects.create(
                    store=store,
                    product=product,
                    **v_data
                )
        return product
