from rest_framework import serializers
from .models import CustomerProfile, CustomerInteraction
from apps.orders.serializers import CustomerSerializer

class CustomerInteractionSerializer(serializers.ModelSerializer):
    created_by_name = serializers.CharField(source='created_by.full_name', read_only=True)
    interaction_type_display = serializers.CharField(source='get_interaction_type_display', read_only=True)

    class Meta:
        model = CustomerInteraction
        fields = [
            'id', 'profile', 'interaction_type', 'interaction_type_display',
            'summary', 'details', 'created_by_name', 'follow_up_needed',
            'follow_up_date', 'created_at'
        ]
        read_only_fields = ['id', 'created_by_name', 'created_at']


class CustomerProfileSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer(read_only=True)
    segment_display = serializers.CharField(source='get_segment_display', read_only=True)
    interactions = CustomerInteractionSerializer(many=True, read_only=True)

    class Meta:
        model = CustomerProfile
        fields = [
            'id', 'customer', 'segment', 'segment_display',
            'recency_days', 'frequency_orders_count', 'monetary_total_spent',
            'average_order_value', 'tags', 'internal_notes',
            'preferred_channel', 'instagram_handle', 'telegram_handle',
            'last_interaction_at', 'interactions', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'recency_days', 'frequency_orders_count',
            'monetary_total_spent', 'average_order_value', 'created_at', 'updated_at'
        ]
