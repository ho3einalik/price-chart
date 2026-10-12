from rest_framework import serializers
from .models import CustomerFeedback, CompetitorPriceTrack
from apps.catalog.serializers import ProductVariantSerializer

class CustomerFeedbackSerializer(serializers.ModelSerializer):
    customer_name = serializers.CharField(source='customer.full_name', read_only=True)
    customer_phone = serializers.CharField(source='customer.phone', read_only=True)
    order_number = serializers.CharField(source='order.order_number', read_only=True)
    category_display = serializers.CharField(source='get_category_display', read_only=True)
    sentiment_display = serializers.CharField(source='get_sentiment_display', read_only=True)

    class Meta:
        model = CustomerFeedback
        fields = [
            'id', 'customer', 'customer_name', 'customer_phone',
            'order', 'order_number', 'rating',
            'category', 'category_display',
            'sentiment', 'sentiment_display',
            'comment', 'is_resolved', 'resolution_notes',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class CompetitorPriceTrackSerializer(serializers.ModelSerializer):
    variant_sku = serializers.CharField(source='variant.sku', read_only=True)
    variant_title = serializers.CharField(source='variant.name', read_only=True)
    our_price = serializers.DecimalField(source='variant.retail_price', max_digits=14, decimal_places=0, read_only=True)

    class Meta:
        model = CompetitorPriceTrack
        fields = [
            'id', 'variant', 'variant_sku', 'variant_title', 'our_price',
            'competitor_name', 'competitor_url', 'competitor_price',
            'price_difference_percent', 'last_checked_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'price_difference_percent', 'last_checked_at', 'created_at', 'updated_at']
